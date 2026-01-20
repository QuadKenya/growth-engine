from app.core.config import settings
from app.models.domain import Lead
from typing import Dict, Any

class ScoringService:
    def __init__(self):
        self.config = settings.RULES_CONFIG
        self.territories = settings.TERRITORIES

    def calculate_score(self, lead: Lead) -> Dict[str, Any]:
        """
        Iterates through the 'gate_1' scoring model defined in JSON.
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
                # Try exact match, then default
                points = mapping.get(user_input, mapping.get("_default", 0.0))
            
            # Logic Type B: Territory Match (e.g., Lives in Nairobi)
            elif criterion.get("logic_type") == "territory_match":
                # Check if input matches a key in territories.json
                if user_input in self.territories:
                    points = 1.0
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
        text = text.lower()
        maps = self.config["readiness_maps"][category]
        
        if any(k in text for k in maps["ready"]):
            return "🟢 Ready"
        if any(k in text for k in maps["nurture"]):
            return "🟠 Nurture"
        return "🔴 Not Ready"

# Singleton
scorer = ScoringService()