import sys
import os
import json
from datetime import datetime, timedelta
import random

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.services.workflow_service import workflow
from app.db.supabase import db
from app.models.domain import Lead, PipelineStage, FinancialAssessmentData

# --- CONFIG ---
# We will create a "Q1 2026 High Velocity" Cohort
COHORT_START = datetime(2026, 1, 1)

def inject_time_traveler(name, role, timeline_days, final_stage):
    """
    timeline_days: Dict of how many days AFTER application they reached a stage.
    e.g. {'FAQ_SENT': 1, 'KYC_SCREENING': 5, 'CONTRACT_CLOSED': 30}
    """
    
    # 1. Base Application Date (Randomized within Jan 2026)
    days_offset = random.randint(0, 10)
    app_date = COHORT_START + timedelta(days=days_offset)
    
    # 2. Basic Lead Data
    lead_data = {
        "lead_id": f"{name.lower().replace(' ', '.')}@test.com",
        "email": f"{name.lower().replace(' ', '.')}@test.com",
        "first_name": name.split(" ")[0],
        "last_name": name.split(" ")[1],
        "phone": "254700000000",
        "current_profession": role,
        "experience_years": "3-4+ Years",
        "has_business_exp": "Yes",
        "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Nairobi",
        "location_status_input": "Yes, I own or lease a location",
        "timestamp": app_date.strftime("%Y-%m-%d %H:%M:%S")
    }

    print(f"⏳ Injecting {name} (Applied: {app_date.date()})...")
    lead = workflow.process_incoming_lead(lead_data)
    
    # 3. OVERRIDE HISTORY (The Time Travel Logic)
    # Reset history to start at app_date
    lead.timestamp = app_date
    lead.stage_history = {
        "EXPRESSED_INTEREST": app_date.isoformat()
    }

    # 4. Apply Milestones based on input timeline
    for stage_key, days in timeline_days.items():
        milestone_date = app_date + timedelta(days=days)
        lead.stage_history[stage_key] = milestone_date.isoformat()
        
        # If this is the final stage requested, update the actual lead status
        if stage_key == final_stage:
            lead.stage = final_stage
            
            # Add dummy data to satisfy logic gates if we jumped ahead
            if final_stage in ["FINANCIAL_ASSESSMENT", "ASSESSMENT_PSYCH", "CONTRACT_CLOSED"]:
                lead.financial_data = FinancialAssessmentData(statement_rows=[{}], abb_grid={})
                lead.verified_financial_capital = 500000
            
            if final_stage == "CONTRACT_CLOSED":
                lead.contract_generated_date = milestone_date.strftime("%Y-%m-%d")

    # 5. Save Modified Lead
    db.upsert_lead(lead)

# --- EXECUTION ---

print("⚠️  Wiping Database...")
file_path = os.path.join(os.path.dirname(__file__), "data/local_db.json")
with open(file_path, "w") as f: json.dump([], f)

print("🚀 Starting Time Travel Injection...")

# 1. The "Speedster" (Fastest possible route)
# App -> Eng(1) -> KYC(2) -> Fin(3) -> Psych(4) -> Contract(7)
inject_time_traveler(
    "Flash Gordon", "Medical Doctor",
    timeline_days={
        "FAQ_SENT": 1, 
        "KYC_SCREENING": 2,
        "ASSESSMENT_PSYCH": 4, 
        "CONTRACT_CLOSED": 7
    },
    final_stage="CONTRACT_CLOSED"
)

# 2. The "Average Joe" (Standard 30 day cycle)
# App -> Eng(2) -> KYC(7) -> Fin(10) -> Psych(14) -> Site(20) -> Contract(30)
inject_time_traveler(
    "Joe Normal", "Clinical Officer",
    timeline_days={
        "FAQ_SENT": 2, 
        "KYC_SCREENING": 7,
        "ASSESSMENT_PSYCH": 14, 
        "CONTRACT_CLOSED": 30
    },
    final_stage="CONTRACT_CLOSED"
)

# 3. The "Compliance Stuck" (Dragging the average up)
# App -> Eng(1) -> KYC(5) ... Still stuck at KYC 20 days later
inject_time_traveler(
    "Stuck Stacy", "Nurse",
    timeline_days={
        "FAQ_SENT": 1, 
        "KYC_SCREENING": 5
    },
    final_stage="KYC_SCREENING"
)

# 4. The "Bottleneck" (Took forever to get to Psych)
# App -> Eng(2) -> KYC(10) -> Fin(25) -> Psych(40) ... Not contracted yet
inject_time_traveler(
    "Slow Sam", "Shopkeeper",
    timeline_days={
        "FAQ_SENT": 2, 
        "KYC_SCREENING": 10,
        "ASSESSMENT_PSYCH": 40
    },
    final_stage="ASSESSMENT_PSYCH"
)

# 5. The "Drop Off" (Rejected at Vetting)
inject_time_traveler(
    "Reject Ralph", "Other",
    timeline_days={},
    final_stage="NO_FIT"
)

print("\n✅ Simulation Complete.")
print("Go to Dashboard -> KPI Reports.")
print("Select 'All Time' or Create a Cohort for 'Jan 2026'.")