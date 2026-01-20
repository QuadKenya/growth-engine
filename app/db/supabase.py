import json
import os
from typing import List, Optional
from app.models.domain import Lead
from app.core.config import settings

# Local File Path simulating the DB table
DB_PATH = settings.BASE_DIR / "data" / "local_db.json"

class SupabaseClient:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        """Ensure data directory and JSON file exist."""
        if not os.path.exists(DB_PATH.parent):
            os.makedirs(DB_PATH.parent)
        if not os.path.exists(DB_PATH):
            with open(DB_PATH, "w") as f:
                json.dump([], f)

    def _read_file(self) -> List[dict]:
        with open(DB_PATH, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _write_file(self, data: List[dict]):
        with open(DB_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)

    # --- Public Methods (Mimicking Supabase SDK) ---

    def upsert_lead(self, lead: Lead) -> Lead:
        """Insert or Update a Lead based on lead_id."""
        data = self._read_file()
        
        # Remove existing entry if it exists
        data = [item for item in data if item["lead_id"] != lead.lead_id]
        
        # Add new/updated entry
        data.append(lead.dict())
        self._write_file(data)
        return lead

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        data = self._read_file()
        for item in data:
            if item["lead_id"] == lead_id:
                return Lead(**item)
        return None

    def fetch_all_leads(self) -> List[Lead]:
        data = self._read_file()
        # Sort by timestamp descending (newest first)
        data.sort(key=lambda x: x["timestamp"], reverse=True)
        return [Lead(**item) for item in data]

# Singleton
db = SupabaseClient()