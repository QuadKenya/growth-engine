from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
from app.models.domain import Lead, PipelineStage

class ReportingService:
    """
    Handles all KPI calculations: Funnels, Cycle Times, and Forecasting.
    Designed to work with a filtered list of leads (e.g., specific Cohort).
    """

    def calculate_general_stats(self, leads: List[Lead]) -> Dict[str, Any]:
        """Basic counts for the top-level KPI cards."""
        total = len(leads)
        if total == 0:
            return {
                "total": 0, 
                "hot_count": 0, 
                "warm_count": 0, 
                "hot_warm_ratio": "0:0", 
                "hard_reject_count": 0, 
                "rejection_rate": "0.0%"
            }

        hot_leads = len([l for l in leads if l.priority_rank == 1 and l.stage not in ["TURNED_DOWN", "NO_FIT", "INACTIVE"]])
        warm_leads = len([l for l in leads if l.stage == "WARM_LEAD"])
        hard_rejects = len([l for l in leads if l.stage in ["NO_FIT", "TURNED_DOWN"] and l.rejection_type == "Hard"])
        
        ratio = f"{hot_leads}:{warm_leads}" if warm_leads > 0 else f"{hot_leads}:0"
        rej_rate = (hard_rejects / total) * 100

        return {
            "total": total,
            "hot_count": hot_leads,
            "warm_count": warm_leads,
            "hot_warm_ratio": ratio,
            "hard_reject_count": hard_rejects,
            "rejection_rate": f"{rej_rate:.1f}%"
        }

    def calculate_funnel(self, leads: List[Lead]) -> Dict[str, Any]:
        """
        Calculates the conversion funnel.
        Empty-Safe: Returns 0s if no leads provided.
        """
        labels = ["Applied", "Qualified", "Engaged", "Interviewed", "Contracted"]
        total = len(leads)
        
        if total == 0:
            return {
                "counts": [0, 0, 0, 0, 0],
                "labels": labels,
                "percentages": [0.0, 0.0, 0.0, 0.0, 0.0],
                "overall_conversion": 0.0
            }

        # 1. Applied
        c_applied = total
        
        # 2. Qualified
        c_qualified = len([l for l in leads if not (l.stage == "NO_FIT" and l.rejection_type == "Hard")])
        
        # 3. Engaged
        c_engaged = len([l for l in leads if "FAQ_SENT" in (l.stage_history or {}) or l.stage in [
            "READY_FOR_CALL", "KYC_SCREENING", "FINANCIAL_ASSESSMENT", "ASSESSMENT_PSYCH", 
            "ASSESSMENT_INTERVIEW", "SITE_SEARCH", "SITE_VETTING", "CONTRACTING", "CONTRACT_CLOSED"
        ]])

        # 4. Interviewed
        c_interview = len([l for l in leads if "ASSESSMENT_INTERVIEW" in (l.stage_history or {}) or l.stage in [
            "SITE_SEARCH", "SITE_VETTING", "CONTRACTING", "CONTRACT_CLOSED"
        ]])

        # 5. Contracted
        c_contracted = len([l for l in leads if l.stage == "CONTRACT_CLOSED"])

        return {
            "counts": [c_applied, c_qualified, c_engaged, c_interview, c_contracted],
            "labels": labels,
            "percentages": [
                100.0, 
                (c_qualified/total)*100, 
                (c_engaged/total)*100, 
                (c_interview/total)*100, 
                (c_contracted/total)*100
            ],
            "overall_conversion": (c_contracted/total)*100
        }

    def calculate_cycle_times(self, leads: List[Lead]) -> Dict[str, Any]:
        """
        Calculates average days from Application to various milestones.
        """
        # Durations lists
        to_engagement = []
        to_compliance = []
        to_psych = []
        to_contract = []
        
        for l in leads:
            history = l.stage_history or {}
            start_str = history.get("EXPRESSED_INTEREST")
            if not start_str:
                start_dt = l.timestamp
            else:
                start_dt = datetime.fromisoformat(start_str)

            # 1. Time to Engagement (Replied YES)
            if "FAQ_SENT" in history:
                end_dt = datetime.fromisoformat(history["FAQ_SENT"])
                to_engagement.append((end_dt - start_dt).days)
            
            # 2. Time to Compliance (Started KYC)
            if "KYC_SCREENING" in history:
                end_dt = datetime.fromisoformat(history["KYC_SCREENING"])
                to_compliance.append((end_dt - start_dt).days)

            # 3. SECONDARY METRIC: Time to Psychometric
            if "ASSESSMENT_PSYCH" in history:
                end_dt = datetime.fromisoformat(history["ASSESSMENT_PSYCH"])
                to_psych.append((end_dt - start_dt).days)
            
            # 4. PRIMARY METRIC: Total Cycle to Contract
            if "CONTRACT_CLOSED" in history:
                end_dt = datetime.fromisoformat(history["CONTRACT_CLOSED"])
                to_contract.append((end_dt - start_dt).days)

        def avg(lst): return round(sum(lst)/len(lst), 1) if lst else 0

        return {
            "avg_to_engagement": avg(to_engagement),
            "avg_to_compliance": avg(to_compliance),
            "avg_to_psych": avg(to_psych), # Secondary
            "avg_to_contract": avg(to_contract), # Primary
            "milestone_labels": ["Engagement", "Compliance", "Psychometric", "Contract"],
            "milestone_values": [avg(to_engagement), avg(to_compliance), avg(to_psych), avg(to_contract)]
        }

    def generate_forecast(self, leads: List[Lead], target_contracts: int) -> Dict[str, Any]:
        """Reverse Calculator: How many leads needed to hit X contracts?"""
        if not leads:
            return {"required_leads": "N/A", "current_rate": 0.0}

        funnel = self.calculate_funnel(leads)
        conversion_rate = funnel.get("overall_conversion", 0.0) / 100.0 
        
        if conversion_rate <= 0:
            return {"required_leads": "N/A", "current_rate": 0.0}
        
        required_leads = int(target_contracts / conversion_rate)
        
        return {
            "required_leads": required_leads,
            "current_rate": round(conversion_rate * 100, 2)
        }

reporter = ReportingService()