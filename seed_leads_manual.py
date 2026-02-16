import sys
import os
import json
from datetime import datetime, timedelta
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.services.workflow_service import workflow
from app.db.supabase import db

# --- SETUP ---
print("⚠️  Wiping Database for Clean Manual Test...")
file_path = os.path.join(os.path.dirname(__file__), "../data/local_db.json")
os.makedirs(os.path.dirname(file_path), exist_ok=True)
with open(file_path, "w") as f:
    json.dump([], f)

# --- LEAD PERMUTATIONS ---

leads = [
    # 1. THE UNICORN (Rank 1 - Hot Lead)
    # Expectation: Inbox -> POTENTIAL_FIT -> Priority Invite Draft
    {
        "lead_id": "unicorn@test.com", "email": "unicorn@test.com", 
        "first_name": "James", "last_name": "Mwangi", "phone": "254711000001",
        "current_profession": "Clinical Officer", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", # Critical Pass
        "financial_readiness_input": "I have adequate resources", 
        "location_county_input": "Nairobi", 
        "location_status_input": "Yes, I own or lease a location", # Triggers Rank 1
        "timestamp": (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 2. THE STANDARD CANDIDATE (Rank 2/3 - Good Fit)
    # Expectation: Inbox -> POTENTIAL_FIT -> Standard Interest Draft
    {
        "lead_id": "standard@test.com", "email": "standard@test.com", 
        "first_name": "Alice", "last_name": "Kamau", "phone": "254711000002",
        "current_profession": "Medical Doctor", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", 
        "financial_readiness_input": "I have adequate resources", 
        "location_county_input": "Kiambu", 
        "location_status_input": "No, but I have found ideal locations", # Not Rank 1
        "timestamp": (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 3. THE HARD REJECT (Business Exp)
    # Expectation: Inbox -> NO_FIT -> Rejection Draft
    {
        "lead_id": "no.biz@test.com", "email": "no.biz@test.com", 
        "first_name": "Peter", "last_name": "Otieno", "phone": "254711000003",
        "current_profession": "Nurse", "experience_years": "3-4+ Years",
        "has_business_exp": "No", # HARD GATE FAIL
        "financial_readiness_input": "I have adequate resources", 
        "location_county_input": "Nakuru", 
        "location_status_input": "Yes, I own or lease a location",
        "timestamp": (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 4. THE HARD REJECT (Financials)
    # Expectation: Inbox -> NO_FIT -> Rejection Draft
    {
        "lead_id": "no.money@test.com", "email": "no.money@test.com", 
        "first_name": "David", "last_name": "Koech", "phone": "254711000004",
        "current_profession": "Clinical Officer", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", 
        "financial_readiness_input": "No, I do not have the resources to cover the clinic's working capital", # HARD GATE FAIL
        "location_county_input": "Mombasa", 
        "location_status_input": "No",
        "timestamp": (datetime.now() - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 5. THE HARD REJECT (Location Invalid)
    # Expectation: Inbox -> NO_FIT -> Rejection Draft
    {
        "lead_id": "bad.loc@test.com", "email": "bad.loc@test.com", 
        "first_name": "Sarah", "last_name": "London", "phone": "254711000005",
        "current_profession": "Medical Doctor", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", 
        "financial_readiness_input": "I have adequate resources", 
        "location_county_input": "London", # HARD GATE FAIL (Not in territories.json)
        "location_status_input": "Yes, I own or lease a location",
        "timestamp": (datetime.now() - timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 6. THE SOFT REJECT (Experience)
    # Expectation: Warm Leads -> Soft Rejection (Exp) Draft
    {
        "lead_id": "junior@test.com", "email": "junior@test.com", 
        "first_name": "Junior", "last_name": "Nurse", "phone": "254711000006",
        "current_profession": "Nurse", "experience_years": "1-2 Years", # SOFT GATE FAIL
        "has_business_exp": "Yes", 
        "financial_readiness_input": "I have adequate resources", 
        "location_county_input": "Kisumu", 
        "location_status_input": "No",
        "timestamp": (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 7. THE SOFT REJECT (Financial Planning)
    # Expectation: Warm Leads -> Soft Rejection (Fin) Draft
    {
        "lead_id": "planner@test.com", "email": "planner@test.com", 
        "first_name": "Faith", "last_name": "Wanjiku", "phone": "254711000007",
        "current_profession": "Clinical Officer", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", 
        "financial_readiness_input": "I need a loan", # SOFT GATE FAIL
        "location_county_input": "Nyeri", 
        "location_status_input": "Yes, I own or lease a location",
        "timestamp": (datetime.now() - timedelta(minutes=35)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 8. THE SOFT REJECT (Location Scout)
    # Expectation: Warm Leads -> Soft Rejection (Loc) Draft
    {
        "lead_id": "scout@test.com", "email": "scout@test.com", 
        "first_name": "Brian", "last_name": "Ochieng", "phone": "254711000008",
        "current_profession": "Medical Doctor", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", 
        "financial_readiness_input": "I have adequate resources", 
        "location_county_input": "Machakos", 
        "location_status_input": "No, I would need assistance", # SOFT GATE FAIL
        "timestamp": (datetime.now() - timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 9. THE BORDERLINE (Conditional Fit)
    # Expectation: Inbox -> POTENTIAL_FIT (Low Score but Passed Gates)
    {
        "lead_id": "border@test.com", "email": "border@test.com", 
        "first_name": "Grace", "last_name": "Muthoni", "phone": "254711000009",
        "current_profession": "Nurse", # 0.75 points
        "experience_years": "2-3 years", # 0.75 points
        "has_business_exp": "Yes", # 1.0
        "financial_readiness_input": "I have adequate resources", 
        "location_county_input": "Kajiado", 
        "location_status_input": "Yes, I own or lease a location",
        "timestamp": (datetime.now() - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S")
    },
    
    # 10. THE CLINIC OWNER (Conversion)
    # Expectation: Inbox -> POTENTIAL_FIT
    {
        "lead_id": "owner@test.com", "email": "owner@test.com", 
        "first_name": "Dr. Yusuf", "last_name": "Ali", "phone": "254711000010",
        "current_profession": "Medical Doctor",
        "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", 
        "financial_readiness_input": "I have adequate resources", 
        "location_county_input": "Mombasa", 
        "location_status_input": "Yes, I own or lease a location",
        "facility_meta": {"is_clinic_owner": "Yes", "is_llc": "Yes", "kmpdc_reg": "Yes"},
        "timestamp": (datetime.now() - timedelta(minutes=50)).strftime("%Y-%m-%d %H:%M:%S")
    }
]

print("🚀 Injecting Leads into Gate 1 (Ingestion)...")
for l in leads:
    workflow.process_incoming_lead(l)
    print(f"-> {l['first_name']} {l['last_name']} ({l['current_profession']})")

print("\n✅ Done! Open Dashboard to test manual transitions.")