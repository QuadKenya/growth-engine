import json
import os
from typing import List, Optional
from app.models.domain import Lead, Cohort
from app.core.config import settings

# Paths for local simulation
LEAD_DB_PATH = settings.BASE_DIR / "data" / "local_db.json"
COHORT_DB_PATH = settings.BASE_DIR / "data" / "cohort_db.json"

class SupabaseClient:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        """Ensure data directory and JSON files exist."""
        if not os.path.exists(LEAD_DB_PATH.parent):
            os.makedirs(LEAD_DB_PATH.parent)
        
        for path in [LEAD_DB_PATH, COHORT_DB_PATH]:
            if not os.path.exists(path):
                with open(path, "w") as f:
                    json.dump([], f)

    # --- LEAD METHODS ---
    def _read_leads(self) -> List[dict]:
        with open(LEAD_DB_PATH, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _write_leads(self, data: List[dict]):
        with open(LEAD_DB_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def reset_db(self):
        """Safely clears the database."""
        self._write_file([])

    def upsert_lead(self, lead: Lead) -> Lead:
        data = self._read_leads()
        data = [item for item in data if item["lead_id"] != lead.lead_id]
        data.append(lead.dict())
        self._write_leads(data)
        return lead

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        data = self._read_leads()
        for item in data:
            if item["lead_id"] == lead_id:
                return Lead(**item)
        return None

    def fetch_all_leads(self) -> List[Lead]:
        data = self._read_leads()
        data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return [Lead(**item) for item in data]

    # --- NEW: COHORT METHODS ---
    def _read_cohorts(self) -> List[dict]:
        with open(COHORT_DB_PATH, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _write_cohorts(self, data: List[dict]):
        with open(COHORT_DB_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def upsert_cohort(self, cohort: Cohort) -> Cohort:
        data = self._read_cohorts()
        # Remove if existing name
        data = [c for c in data if c["name"] != cohort.name]
        data.append(cohort.dict())
        self._write_cohorts(data)
        return cohort

    def fetch_all_cohorts(self) -> List[Cohort]:
        data = self._read_cohorts()
        return [Cohort(**item) for item in data]

    def delete_cohort(self, cohort_name: str):
        data = self._read_cohorts()
        data = [c for c in data if c["name"] != cohort_name]
        self._write_cohorts(data)

# Singleton
db = SupabaseClient()