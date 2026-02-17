import json
import os
from typing import List, Optional
from app.models.domain import Lead, Cohort
from supabase import create_client, Client
import streamlit as st

class DatabaseClient:
    def __init__(self):
        self.use_cloud = False
        self.client: Optional[Client] = None
        
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        # Try loading from Streamlit secrets (Cloud Mode) safely
        if not url:
            try:
                if "SUPABASE_URL" in st.secrets:
                    url = st.secrets["SUPABASE_URL"]
                    key = st.secrets["SUPABASE_KEY"]
                    print("🔍 Found credentials in Streamlit Secrets.")
            except Exception:
                pass

        # If credentials exist and point to a real Supabase instance
        if url and key and "127.0.0.1" not in url:
            try:
                self.client = create_client(url, key)
                self.use_cloud = True
                print(f"✅ Connected to Supabase Cloud: {url}")
            except Exception as e:
                print(f"⚠️ Failed to connect to Supabase: {e}. Falling back to local JSON.")
        
        if not self.use_cloud:
            self._init_local_db()

    def _init_local_db(self):
        from app.core.config import settings
        self.LEAD_PATH = settings.BASE_DIR / "data" / "local_db.json"
        self.COHORT_PATH = settings.BASE_DIR / "data" / "cohort_db.json"
        
        if not os.path.exists(self.LEAD_PATH.parent):
            os.makedirs(self.LEAD_PATH.parent)
        
        for p in [self.LEAD_PATH, self.COHORT_PATH]:
            if not os.path.exists(p):
                with open(p, "w") as f: json.dump([], f)

    # --- LEAD METHODS ---
    def upsert_lead(self, lead: Lead) -> Lead:
        # FIXED: Use model_dump(mode='json') to serialize datetime objects to strings
        lead_dict = lead.model_dump(mode='json')
        
        if self.use_cloud:
            payload = {"id": lead.lead_id, "data": lead_dict}
            self.client.table("leads").upsert(payload).execute()
        else:
            data = self._read_json(self.LEAD_PATH)
            data = [i for i in data if i["lead_id"] != lead.lead_id]
            data.append(lead_dict)
            self._write_json(self.LEAD_PATH, data)
        return lead

    def fetch_all_leads(self) -> List[Lead]:
        if self.use_cloud:
            response = self.client.table("leads").select("data").execute()
            return [Lead(**row['data']) for row in response.data]
        else:
            data = self._read_json(self.LEAD_PATH)
            return [Lead(**i) for i in data]

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        if self.use_cloud:
            response = self.client.table("leads").select("data").eq("id", lead_id).execute()
            if response.data:
                return Lead(**response.data[0]['data'])
            return None
        else:
            data = self._read_json(self.LEAD_PATH)
            for i in data:
                if i["lead_id"] == lead_id: return Lead(**i)
            return None

    # --- COHORT METHODS ---
    def upsert_cohort(self, cohort: Cohort) -> Cohort:
        # FIXED: Use model_dump(mode='json') here as well
        c_dict = cohort.model_dump(mode='json')
        
        if self.use_cloud:
            payload = {"name": cohort.name, "data": c_dict}
            self.client.table("cohorts").upsert(payload).execute()
        else:
            data = self._read_json(self.COHORT_PATH)
            data = [c for c in data if c["name"] != cohort.name]
            data.append(c_dict)
            self._write_json(self.COHORT_PATH, data)
        return cohort

    def fetch_all_cohorts(self) -> List[Cohort]:
        if self.use_cloud:
            response = self.client.table("cohorts").select("data").execute()
            return [Cohort(**row['data']) for row in response.data]
        else:
            data = self._read_json(self.COHORT_PATH)
            return [Cohort(**i) for i in data]

    def delete_cohort(self, name: str):
        if self.use_cloud:
            self.client.table("cohorts").delete().eq("name", name).execute()
        else:
            data = self._read_json(self.COHORT_PATH)
            data = [c for c in data if c["name"] != name]
            self._write_json(self.COHORT_PATH, data)

    # --- UTILS ---
    def reset_db(self):
        """Safely clears the database."""
        if self.use_cloud:
            print("⚠️ Reset DB ignored in Cloud Mode.")
        else:
            self._write_json(self.LEAD_PATH, [])
            self._write_json(self.COHORT_PATH, [])

    def _read_json(self, path):
        with open(path, "r") as f:
            try: return json.load(f)
            except: return []

    def _write_json(self, path, data):
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

db = DatabaseClient()