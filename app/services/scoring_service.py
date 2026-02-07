from app.core.config import settings
from app.models.domain import Lead, FinancialAssessmentData, FinancialAssessmentResults
from typing import Dict, Any, List, Optional
from datetime import datetime

class ScoringService:
    def __init__(self):
        self.config = settings.RULES_CONFIG
        self.territories = settings.TERRITORIES

    def check_hard_gates(self, lead: Lead) -> Dict[str, Any]:
        """Returns {passed: bool, reason: str}"""
        gates = self.config["hard_gates"]
        
        # 1. Business Exp
        if lead.has_business_exp == gates["biz_exp"]:
            return {"passed": False, "reason": "No Business Experience"}
            
        # 2. Financial Absolute Fail
        if lead.financial_readiness_input == gates["financial_status"]:
            return {"passed": False, "reason": "Lack of Capital (Hard No)"}
            
        # 3. Location Validity (NEW STRICT GATE)
        # Verify against territories.json
        valid_counties = self.territories.get("valid_counties", [])
        # Normalize input to Title Case to match list (e.g. "nairobi" -> "Nairobi")
        user_county = str(lead.location_county_input).strip().title()
        
        if user_county not in valid_counties:
            return {
                "passed": False, 
                "reason": f"Location '{user_county}' is outside operational areas"
            }

        # 4. Clinic Conversion Checks (Only if facility_meta exists)
        if lead.facility_meta.get("is_clinic_owner") == "Yes":
            conv_gates = gates["clinic_conversion_failures"]
            if lead.facility_meta.get("is_llc") == conv_gates["is_llc"]:
                return {"passed": False, "reason": "Clinic not LLC"}
            if lead.facility_meta.get("kmpdc_reg") == conv_gates["kmpdc"]:
                return {"passed": False, "reason": "Clinic not KMPDC Registered"}
            # Add other conversion checks as needed
        
        return {"passed": True, "reason": None}

    def determine_priority(self, lead: Lead) -> int:
        """Calculates Rank 1 (Hot), 2 (Funded), 3 (Standard)"""
        prio_config = self.config["prioritization"]
        
        # Rank 1: Site Ready
        if lead.location_status_input == prio_config["rank_1_criteria"]["location_status"]:
            return 1
            
        # Rank 2: Cash Ready (But no site)
        # Using simple string matching from config
        if prio_config["rank_2_criteria"]["financial_status"] in lead.financial_readiness_input:
            return 2
            
        return 3

    def is_soft_rejection(self, lead: Lead) -> Dict[str, Any]:
        """Checks if failure is due to Experience, Planning, or Location (Warm Lead)"""
        soft_logic = self.config["soft_rejection_logic"]
        
        # Exp Check
        if lead.experience_years in soft_logic["experience"]:
            return {"is_soft": True, "reason": "experience"}
            
        # Finance Check (Planning)
        if any(x in lead.financial_readiness_input for x in soft_logic["financial"]):
            return {"is_soft": True, "reason": "financial"}

        # Location Check (Searching)
        if any(x in lead.location_status_input for x in soft_logic["location"]):
            return {"is_soft": True, "reason": "location"}
            
        return {"is_soft": False, "reason": "hard"}

    def calculate_score(self, lead: Lead) -> Dict[str, Any]:
        model = self.config["scoring_model"]["gate_1"]
        total_score = 0.0
        
        lead_data = lead.dict()
        
        for criterion in model:
            input_val = lead_data.get(criterion["input_field"])
            points = 0.0
            
            if "mapping" in criterion:
                mapping = criterion["mapping"]
                points = mapping.get(input_val, mapping.get("_default", 0.0))
                
            elif criterion.get("logic_type") == "territory_match":
                clean_loc = str(input_val).title()
                if clean_loc in self.territories.get("location_map", {}) or \
                   clean_loc in self.territories.get("valid_counties", []):
                    points = 1.0
                    
            elif criterion.get("logic_type") == "pass_through":
                points = criterion.get("default_value", 1.0)
                
            total_score += (points * criterion["weight"])

        return {"score": round(total_score, 4)}

    def classify_score(self, score: float) -> str:
        for t in self.config["thresholds"]["classifications"]:
            if score >= t["min_score"]: return t["label"]
        return "Not A Fit"

# --- NEW: Financial Assessment Logic ---
class FinancialCalculator:
    @staticmethod
    def excel_datedif_m_plus_1(start_date: datetime, end_date: datetime) -> int:
        """Replicates Excel's DATEDIF(start, end, 'm') + 1 logic."""
        diff = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        if end_date.day < start_date.day:
            diff -= 1
        return diff + 1

    @staticmethod
    def excel_average(values: List[Optional[float]]) -> float:
        """Replicates Excel AVERAGE (ignores blanks/None)."""
        clean_values = [v for v in values if v is not None]
        if not clean_values:
            return 0.0
        return sum(clean_values) / len(clean_values)

    def calculate_assessment(self, data: FinancialAssessmentData) -> FinancialAssessmentResults:
        res = FinancialAssessmentResults()
        
        # --- 1. ABD CALCULATIONS ---
        if data.statement_rows:
            # Parse dates safely
            parsed_dates = []
            for r in data.statement_rows:
                d_str = r.get('date')
                if d_str:
                    try:
                        parsed_dates.append(datetime.strptime(str(d_str), "%Y-%m-%d"))
                    except: pass
            
            if parsed_dates:
                res.start_date = min(parsed_dates).strftime("%Y-%m-%d")
                res.end_date = max(parsed_dates).strftime("%Y-%m-%d")
                res.num_months = self.excel_datedif_m_plus_1(min(parsed_dates), max(parsed_dates))
                
                # Sum credits where include is True
                res.sum_deposits = sum(
                    float(r.get('credit_amount', 0) or 0) 
                    for r in data.statement_rows 
                    if r.get('include_deposit') in [True, "Yes", "yes"]
                )
                res.abd = res.sum_deposits / res.num_months if res.num_months > 0 else 0
        
        # --- 2. ABB CALCULATIONS ---
        checkpoints = ["5th", "10th", "15th", "20th", "25th", "30th"]
        for cp in checkpoints:
            cp_values = []
            for m_key in data.abb_grid:
                val = data.abb_grid[m_key].get(cp)
                cp_values.append(val)
            res.checkpoint_averages[cp] = self.excel_average(cp_values)
        
        # Overall ABB is average of the checkpoint averages
        res.abb = self.excel_average(list(res.checkpoint_averages.values()))

        # --- 3. CAPACITY & DECISIONS ---
        res.total_revenue = res.abd 
        res.net_income_amount = res.total_revenue * 0.5
        res.installment_capacity_amount = res.net_income_amount * 0.5 # 0.25 of Total Revenue
        
        # Thresholds (Greater than 240k and 60k)
        res.revenue_pass = res.total_revenue > 240000
        res.installment_pass = res.installment_capacity_amount > 60000
        res.overall_pass = res.revenue_pass and res.installment_pass
        
        return res

scorer = ScoringService()
fin_calc = FinancialCalculator()