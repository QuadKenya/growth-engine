import sys
import os
import json
from datetime import date, datetime, timedelta
import random

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.services.workflow_service import workflow
from app.db.supabase import db
from app.models.domain import Lead, PipelineStage, FinancialAssessmentData, SiteAssessmentData

# --- HELPERS ---
def backdate_timestamp(days_ago):
    return (datetime.now() - timedelta(days=days_ago))

def inject_and_progress(lead_data, target_stage=None, history_days=0, fail_reason=None):
    """
    1. Injects lead (Gate 1).
    2. Fast-forwards to target_stage.
    3. Backdates timestamps to simulate realistic cycle times.
    """
    # 1. Initial Injection
    print(f"Injecting: {lead_data['first_name']} {lead_data['last_name']}...")
    lead = workflow.process_incoming_lead(lead_data)
    
    # 2. Backdate the Application Date (Critical for Cohorts)
    lead.timestamp = datetime.strptime(lead_data['timestamp'], "%Y-%m-%d %H:%M:%S")
    
    # 3. Initialize History
    base_date = lead.timestamp
    lead.stage_history = {
        "EXPRESSED_INTEREST": base_date.isoformat()
    }

    # 4. State Jumping (Simulating User Actions)
    if target_stage:
        # Move to Engaged
        if target_stage in [PipelineStage.FAQ_SENT, PipelineStage.READY_FOR_CALL, PipelineStage.KYC_SCREENING, PipelineStage.FINANCIAL_ASSESSMENT, PipelineStage.CONTRACTING, PipelineStage.CONTRACT_CLOSED]:
            lead.stage = PipelineStage.FAQ_SENT
            lead.stage_history["FAQ_SENT"] = (base_date + timedelta(days=1)).isoformat()
        
        # Move to Compliance
        if target_stage in [PipelineStage.KYC_SCREENING, PipelineStage.FINANCIAL_ASSESSMENT, PipelineStage.CONTRACTING, PipelineStage.CONTRACT_CLOSED]:
            lead.stage = PipelineStage.KYC_SCREENING
            lead.checklist_status = {"ID Copy": True, "KRA PIN": True, "Police Clearance": True, "Academic Certs": True}
            lead.stage_history["KYC_SCREENING"] = (base_date + timedelta(days=3)).isoformat()

        # Move to Financials
        if target_stage in [PipelineStage.FINANCIAL_ASSESSMENT, PipelineStage.CONTRACTING, PipelineStage.CONTRACT_CLOSED]:
            lead.stage = PipelineStage.FINANCIAL_ASSESSMENT
            lead.stage_history["FINANCIAL_ASSESSMENT"] = (base_date + timedelta(days=5)).isoformat()
            
            # If we want them to pass financials
            if target_stage != PipelineStage.WARM_LEAD:
                lead.financial_data = FinancialAssessmentData(
                    statement_rows=[{"date": str(date.today()), "credit_amount": 350000, "include_deposit": True}],
                    abb_grid={"Month 1": {"5th": 100000}}
                )
                lead.verified_financial_capital = 350000

        # Move to Psych/Site
        if target_stage in [PipelineStage.SITE_SEARCH, PipelineStage.SITE_VETTING, PipelineStage.CONTRACTING, PipelineStage.CONTRACT_CLOSED]:
            lead.stage = PipelineStage.ASSESSMENT_PSYCH
            lead.stage_history["ASSESSMENT_PSYCH"] = (base_date + timedelta(days=7)).isoformat()
            # Fast forward to Site Search
            lead.stage = PipelineStage.SITE_SEARCH
            lead.stage_history["SITE_SEARCH"] = (base_date + timedelta(days=10)).isoformat()

        # Move to Contracted
        if target_stage == PipelineStage.CONTRACT_CLOSED:
            lead.stage = PipelineStage.CONTRACT_CLOSED
            lead.stage_history["CONTRACT_CLOSED"] = (base_date + timedelta(days=history_days)).isoformat() # Use the full duration provided
            lead.contract_generated_date = str(date.today())

        # Handle Specific Fail States
        if fail_reason == "hard_reject":
            lead.stage = PipelineStage.NO_FIT
            lead.rejection_type = "Hard"
        elif fail_reason == "financial_fail":
            lead.stage = PipelineStage.WARM_LEAD
            lead.soft_rejection_reason = "Financial Threshold Not Met (Rev: KES 100,000)"
            lead.stage_history["WARM_LEAD"] = (base_date + timedelta(days=6)).isoformat()

    # Save final state
    db.upsert_lead(lead)

# --- EXECUTION ---

# Reset DB for Clean Slate
print("⚠️  Resetting Database...")
file_path = os.path.join(os.path.dirname(__file__), "data/local_db.json")
with open(file_path, "w") as f: json.dump([], f)

# === COHORT 1: "Q4 2025 Call" (Past Data) ===
# Dates: Jan 1 - Jan 15
# Goal: Show closed contracts and high cycle times

inject_and_progress(
    {
        "lead_id": "winner.jan@test.com", "email": "winner.jan@test.com", "first_name": "Winner", "last_name": "Jan", "phone": "254700000001",
        "current_profession": "Clinical Officer", "experience_years": "3-4+ Years", "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Nairobi", "location_status_input": "Yes, I own or lease a location",
        "timestamp": "2025-01-01 10:00:00"
    },
    target_stage=PipelineStage.CONTRACT_CLOSED,
    history_days=25 # Took 25 days to close
)

inject_and_progress(
    {
        "lead_id": "failed.fin.jan@test.com", "email": "failed.fin.jan@test.com", "first_name": "Broke", "last_name": "Jan", "phone": "254700000002",
        "current_profession": "Nurse", "experience_years": "3-4+ Years", "has_business_exp": "No", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Kiambu", "location_status_input": "No",
        "timestamp": "2025-01-05 10:00:00"
    },
    target_stage=PipelineStage.WARM_LEAD, # Stuck at financials
    fail_reason="financial_fail"
)

inject_and_progress(
    {
        "lead_id": "reject.jan@test.com", "email": "reject.jan@test.com", "first_name": "Bad", "last_name": "Jan", "phone": "254700000003",
        "current_profession": "Shopkeeper", "experience_years": "None", "has_business_exp": "No", "financial_readiness_input": "I need a loan",
        "location_county_input": "Marsabit", "location_status_input": "No",
        "timestamp": "2025-01-10 10:00:00"
    },
    target_stage=None,
    fail_reason="hard_reject"
)

# === COHORT 2: "Q1 2026 Call" (Current Data) ===
# Dates: Feb 1 - Feb 15
# Goal: Show active pipeline

# 1. Inbox (Fresh)
inject_and_progress({
    "lead_id": "fresh.feb@test.com", "email": "fresh.feb@test.com", "first_name": "Fresh", "last_name": "Feb", "phone": "254700000004",
    "current_profession": "Medical Doctor", "experience_years": "3-4+ Years", "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
    "location_county_input": "Mombasa", "location_status_input": "Yes, I own or lease a location",
    "timestamp": "2025-02-01 09:00:00"
}) # Stays in Inbox

# 2. Compliance (Stuck) - Needs Nudge
inject_and_progress({
    "lead_id": "kyc.feb@test.com", "email": "kyc.feb@test.com", "first_name": "KYC", "last_name": "Stuck", "phone": "254700000005",
    "current_profession": "Nurse", "experience_years": "1-2 Years", "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
    "location_county_input": "Nakuru", "location_status_input": "No, but I have found ideal locations",
    "timestamp": "2025-02-02 14:00:00"
}, target_stage=PipelineStage.KYC_SCREENING)

# 3. Financials (Ready to Calculate)
inject_and_progress({
    "lead_id": "fin.feb@test.com", "email": "fin.feb@test.com", "first_name": "Finance", "last_name": "Ready", "phone": "254700000006",
    "current_profession": "Clinical Officer", "experience_years": "3-4+ Years", "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
    "location_county_input": "Nairobi", "location_status_input": "Yes, I own or lease a location",
    "timestamp": "2025-02-03 11:00:00"
}, target_stage=PipelineStage.FINANCIAL_ASSESSMENT)

# 4. Site Review (Ready for Pre-Visit Check)
inject_and_progress({
    "lead_id": "site.feb@test.com", "email": "site.feb@test.com", "first_name": "Site", "last_name": "Scout", "phone": "254700000007",
    "current_profession": "Medical Doctor", "experience_years": "3-4+ Years", "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
    "location_county_input": "Kiambu", "location_status_input": "Yes, I own or lease a location",
    "timestamp": "2025-02-01 08:00:00"
}, target_stage=PipelineStage.SITE_SEARCH)

print("✅ Seed Data Injection Complete.")
print("  - Cohort 1 (Jan): 3 Leads (1 Closed, 1 Warm, 1 Rejected)")
print("  - Cohort 2 (Feb): 4 Leads (Inbox, KYC, Finance, Site)")