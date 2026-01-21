import json
import os
from typing import List, Optional
from app.models.domain import Lead
from app.core.config import settings

DB_PATH = settings.BASE_DIR / "data" / "local_db.json"

class SupabaseClient:
    def __init__(self):
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Self-Healing: Creates the DB file if it's missing."""
        if not os.path.exists(DB_PATH.parent):
            os.makedirs(DB_PATH.parent, exist_ok=True)
        if not os.path.exists(DB_PATH):
            with open(DB_PATH, "w") as f:
                json.dump([], f)

    def _read_file(self) -> List[dict]:
        """Reads data, recreating DB if it was deleted."""
        if not os.path.exists(DB_PATH):
            self._ensure_db_exists()
            
        try:
            with open(DB_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_file(self, data: List[dict]):
        self._ensure_db_exists()
        with open(DB_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def reset_db(self):
        """Safely clears the database."""
        self._write_file([])

    def upsert_lead(self, lead: Lead) -> Lead:
        data = self._read_file()
        # Remove existing version
        data = [item for item in data if item["lead_id"] != lead.lead_id]
        # Add new version
        data.append(lead.dict(by_alias=True))
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
        # Sort by timestamp descending
        try:
            data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        except:
            pass
        return [Lead(**item) for item in data]

db = SupabaseClient()