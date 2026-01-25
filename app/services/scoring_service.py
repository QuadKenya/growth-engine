from app.core.config import settings
from app.models.domain import Lead
from typing import Dict, Any

class ScoringService:
    def __init__(self):
        self.config = settings.RULES_CONFIG
        self.territories = settings.TERRITORIES

    def calculate_score(self, lead: Lead) -> Dict[str, Any]:
        """
        Iterates through the scoring model defined in JSON.
        Returns total score and classification.
        """
        model = self.config["scoring_model"]["gate_1"]
        total_score = 0.0
        breakdown = []

        # Convert Pydantic model to dict for easy lookup
        lead_data = lead.dict()

        for criterion in model:
            field = criterion["input_field"]
            weight = criterion["weight"]
            user_input = lead_data.get(field)
            points = 0.0
            
            # Logic Type A: Direct Mapping (e.g., Nurse = 0.75)
            if "mapping" in criterion:
                mapping = criterion["mapping"]
                points = mapping.get(user_input, mapping.get("_default", 0.0))
            
            # Logic Type B: Territory Match (Active Gatekeeper)
            elif criterion.get("logic_type") == "territory_match":
                # Clean input (Title Case)
                clean_input = str(user_input).strip().title()
                
                # Check 1: Is it a valid County?
                if clean_input in self.territories.get("valid_counties", []):
                    points = 1.0
                # Check 2: Is it a valid Sub-County/Ward? (Reverse Lookup)
                elif clean_input in self.territories.get("location_map", {}):
                    points = 1.0
                    # (Optional) We could normalize the lead's county here if we wanted
                else:
                    points = 0.0
            
            # Logic Type C: Pass Through (Assumed 1.0 for MVP)
            elif criterion.get("logic_type") == "pass_through":
                points = criterion.get("default_value", 0.0)

            # Calculate Weighted Score
            weighted_points = points * weight
            total_score += weighted_points
            
            breakdown.append({
                "criterion": criterion.get("id"),
                "input": user_input,
                "points": points,
                "weighted": weighted_points
            })

        return {
            "score": round(total_score, 4),
            "breakdown": breakdown
        }

    def classify_score(self, score: float) -> str:
        """Determines 'Ideal Fit' vs 'No Fit' based on thresholds."""
        thresholds = self.config["thresholds"]["classifications"]
        # Sort by min_score descending to find the highest match
        thresholds.sort(key=lambda x: x["min_score"], reverse=True)
        
        for t in thresholds:
            if score >= t["min_score"]:
                return t["label"]
        return "Not A Fit"

    def determine_readiness(self, text: str, category: str) -> str:
        """Checks for keywords in text (Financial/Location)."""
        text = str(text).lower()
        maps = self.config["readiness_maps"][category]
        
        if any(k in text for k in maps["ready"]):
            return "🟢 Ready"
        if any(k in text for k in maps["nurture"]):
            return "🟠 Nurture"
        return "🔴 Not Ready"

# Singleton
scorer = ScoringService()