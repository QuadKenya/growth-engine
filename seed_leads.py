import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.services.workflow_service import workflow

now = datetime.now()

leads = [
    # 1. John (The Unicorn) - Ideal Fit
    {
        "lead_id": "john.kamau@test.com", "email": "john.kamau@test.com",
        "first_name": "John", "last_name": "Kamau", "phone": "254700000001",
        "current_profession": "Clinical Officer", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Nairobi", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=1, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 2. Sarah (The Planner) - Soft Reject (Finance)
    {
        "lead_id": "sarah.hassan@test.com", "email": "sarah.hassan@test.com",
        "first_name": "Sarah", "last_name": "Hassan", "phone": "254700000002",
        "current_profession": "Nurse", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I need a loan",
        "location_county_input": "Kiambu", "location_status_input": "No, but I have found ideal locations",
        "timestamp": (now - timedelta(days=2, hours=5)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 3. Peter (The Rookie) - Soft Reject (Experience) -> Overridden by Score
    {
        "lead_id": "peter.omondi@test.com", "email": "peter.omondi@test.com",
        "first_name": "Peter", "last_name": "Omondi", "phone": "254700000003",
        "current_profession": "Clinical Officer", "experience_years": "1-2 Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Mombasa", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=3, hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 4. David (The Shopkeeper) - Hard Reject
    {
        "lead_id": "david.lagat@test.com", "email": "david.lagat@test.com",
        "first_name": "David", "last_name": "Lagat", "phone": "254700000004",
        "current_profession": "Shopkeeper", "experience_years": "None",
        "has_business_exp": "No", "financial_readiness_input": "I need a loan",
        "location_county_input": "Nairobi", "location_status_input": "No",
        "timestamp": (now - timedelta(days=4, hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 5. Alice (The Cash Ready) - Hot Lead
    {
        "lead_id": "alice.mutua@test.com", "email": "alice.mutua@test.com",
        "first_name": "Alice", "last_name": "Mutua", "phone": "254700000005",
        "current_profession": "Nurse", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Nakuru", "location_status_input": "No, but I have found ideal locations",
        "timestamp": (now - timedelta(days=5, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 6. Grace (The Doctor) - Ideal Fit
    {
        "lead_id": "grace.soi@test.com", "email": "grace.soi@test.com",
        "first_name": "Grace", "last_name": "Soi", "phone": "254700000006",
        "current_profession": "Medical Doctor", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Nairobi", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=6, hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    },

    # 7. Brian (Early Career CO) - Low Experience + Loan + No location
    {
        "lead_id": "brian.bosire@test.com", "email": "brian.bosire@test.com",
        "first_name": "Brian", "last_name": "Bosire", "phone": "254700000007",
        "current_profession": "Clinical Officer", "experience_years": "1-2 Years",
        "has_business_exp": "No", "financial_readiness_input": "I need a loan",
        "location_county_input": "Kisumu", "location_status_input": "No",
        "timestamp": (now - timedelta(days=7, hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 8. Faith (Experienced Nurse, No Biz Exp) - Strong but no business exp
    {
        "lead_id": "faith.njeri@test.com", "email": "faith.njeri@test.com",
        "first_name": "Faith", "last_name": "Njeri", "phone": "254700000008",
        "current_profession": "Nurse", "experience_years": "3-4+ Years",
        "has_business_exp": "No", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Uasin Gishu", "location_status_input": "No, but I have found ideal locations",
        "timestamp": (now - timedelta(days=8, hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 9. Kelvin (Doctor, Great finance, no location) - Might be nurture for location
    {
        "lead_id": "kelvin.koinet@test.com", "email": "kelvin.koinet@test.com",
        "first_name": "Kelvin", "last_name": "Koinet", "phone": "254700000009",
        "current_profession": "Medical Doctor", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Machakos", "location_status_input": "No",
        "timestamp": (now - timedelta(days=9, hours=5)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 10. Miriam (Shopkeeper w/ capital + location) - Non-clinical but strong resources
    {
        "lead_id": "miriam.kilonzo@test.com", "email": "miriam.kilonzo@test.com",
        "first_name": "Miriam", "last_name": "Kilonzo", "phone": "254700000010",
        "current_profession": "Shopkeeper", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Nairobi", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=10, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 11. Daniel (CO, no experience, but has location) - Weird edge case
    {
        "lead_id": "daniel.kiptoo@test.com", "email": "daniel.kiptoo@test.com",
        "first_name": "Daniel", "last_name": "Kiptoo", "phone": "254700000011",
        "current_profession": "Clinical Officer", "experience_years": "None",
        "has_business_exp": "Yes", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Nakuru", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=11, hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 12. Ruth (Nurse, 1-2 years, found locations, needs loan) - borderline
    {
        "lead_id": "ruth.keya@test.com", "email": "ruth.keya@test.com",
        "first_name": "Ruth", "last_name": "Keya", "phone": "254700000012",
        "current_profession": "Nurse", "experience_years": "1-2 Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I need a loan",
        "location_county_input": "Kiambu", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=12, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 13. Hassan (Doctor, 1-2 years, no biz exp, capital, found locations)
    {
        "lead_id": "hassan.abdi@test.com", "email": "hassan.abdi@test.com",
        "first_name": "Hassan", "last_name": "Abdi", "phone": "254700000013",
        "current_profession": "Medical Doctor", "experience_years": "1-2 Years",
        "has_business_exp": "No", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Garissa", "location_status_input": "No, but I have found ideal locations",
        "timestamp": (now - timedelta(days=13, hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 14. Irene (Shopkeeper, none exp, biz exp yes, loan, found locations) - stress case
    {
        "lead_id": "irene.mwangi@test.com", "email": "irene.mwangi@test.com",
        "first_name": "Irene", "last_name": "Mwangi", "phone": "254700000014",
        "current_profession": "Shopkeeper", "experience_years": "None",
        "has_business_exp": "Yes", "financial_readiness_input": "I need a loan",
        "location_county_input": "Mombasa", "location_status_input": "No, but I have found ideal locations",
        "timestamp": (now - timedelta(days=14, hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 15. Samuel (CO, experienced, no biz exp, loan, has location) - mixed readiness
    {
        "lead_id": "samuel.mule@test.com", "email": "samuel.mule@test.com",
        "first_name": "Samuel", "last_name": "Mule", "phone": "254700000015",
        "current_profession": "Clinical Officer", "experience_years": "3-4+ Years",
        "has_business_exp": "No", "financial_readiness_input": "I need a loan",
        "location_county_input": "Nyeri", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=15, hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 16. Agnes (Nurse, none exp, no biz exp, capital, no location) - low exp edge
    {
        "lead_id": "agnes.maisha@test.com", "email": "agnes.maisha@test.com",
        "first_name": "Agnes", "last_name": "Maisha", "phone": "254700000016",
        "current_profession": "Nurse", "experience_years": "None",
        "has_business_exp": "No", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Kakamega", "location_status_input": "No",
        "timestamp": (now - timedelta(days=16, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 17. Victor (Doctor, experienced, biz exp yes, loan, has location) - finance edge
    {
        "lead_id": "victor.gaati@test.com", "email": "victor.gaati@test.com",
        "first_name": "Victor", "last_name": "Gaati", "phone": "254700000017",
        "current_profession": "Medical Doctor", "experience_years": "3-4+ Years",
        "has_business_exp": "Yes", "financial_readiness_input": "I need a loan",
        "location_county_input": "Nairobi", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=17, hours=5)).strftime("%Y-%m-%d %H:%M:%S")
    },
    # 18. Winnie (Clinical Officer, 1-2 years, no biz exp, capital, has location) - clinical edge
    {
        "lead_id": "winnie.neeris@test.com", "email": "winnie.neeris@test.com",
        "first_name": "Winnie", "last_name": "Neeris", "phone": "254700000018",
        "current_profession": "Clinical Officer", "experience_years": "1-2 Years",
        "has_business_exp": "No", "financial_readiness_input": "I have adequate resources",
        "location_county_input": "Kajiado", "location_status_input": "Yes, I own or lease a location",
        "timestamp": (now - timedelta(days=18, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    },
]

print("Injecting Leads...")
for l in leads:
    workflow.process_incoming_lead(l)
    print(f"-> Injected {l['first_name']} {l['last_name']}")
print("Done!")