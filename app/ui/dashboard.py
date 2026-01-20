import sys
import os

# Add the project root directory to Python's search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import pandas as pd
import time
from app.db.supabase import db
from app.services.workflow_service import workflow
from app.services.drafting_service import drafter
from app.core.config import settings

# --- CONFIG ---
st.set_page_config(
    page_title="Access Afya | Vetting Control Tower",
    page_icon="🏥",
    layout="wide"
)

# --- STYLING ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #1a4593;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: SIMULATION ---
with st.sidebar:
    st.image("https://www.accessafya.com/wp-content/uploads/2020/10/Access-Afya-Logo.png", width=200)
    st.title("Simulation Lab")
    st.markdown("Inject test data to trigger the Agent.")
    
    with st.form("sim_form"):
        fname = st.text_input("First Name", "Jane")
        lname = st.text_input("Last Name", "Doe")
        email = st.text_input("Email", "jane@test.com")
        prof = st.selectbox("Profession", ["Nurse", "Clinical Officer", "Shopkeeper", "Doctor"])
        exp = st.selectbox("Experience", ["3-4+ Years", "1-2 Years", "None"])
        finance = st.selectbox("Financials", ["I have adequate resources (cash available)", "I need a loan"])
        county = st.selectbox("County", ["Nairobi", "Mombasa", "Turkana"])
        
        submitted = st.form_submit_button("🚀 Inject Lead")
        
        if submitted:
            # Construct payload matching Lead model
            payload = {
                "lead_id": email,
                "email": email,
                "first_name": fname,
                "last_name": lname,
                "phone": "0700123456",
                "current_profession": prof,
                "experience_years": exp,
                "has_business_exp": "No",
                "financial_readiness_input": finance,
                "location_county_input": county,
                "location_status_input": "No, but I have potential communities in mind"
            }
            
            with st.spinner("Agent is vetting..."):
                workflow.process_incoming_lead(payload)
                time.sleep(1) # Visual pause
            st.success("Lead processed! Check Inbox.")

# --- MAIN AREA ---
st.title("Growth Coordinator Dashboard")

# Top Level Metrics
leads = db.fetch_all_leads()
pending_drafts = len([l for l in leads if l.draft_message])
total_vetted = len(leads)
ideal_fits = len([l for l in leads if l.fit_classification == "Ideal Fit"])

c1, c2, c3 = st.columns(3)
c1.metric("Pending Approvals", pending_drafts, delta_color="inverse")
c2.metric("Total Pipeline", total_vetted)
c3.metric("Ideal Fits", ideal_fits)

# Tabs
tab_inbox, tab_tracker = st.tabs(["📥 Inbox (Needs Action)", "📊 Pipeline Tracker"])

# --- TAB 1: INBOX ---
with tab_inbox:
    to_approve = [l for l in leads if l.draft_message]
    
    if not to_approve:
        st.info("🎉 All caught up! No drafts pending approval.")
    
    for lead in to_approve:
        with st.expander(f"{lead.fit_classification} | {lead.first_name} {lead.last_name} | {lead.stage}", expanded=True):
            col_left, col_right = st.columns([2, 1])
            
            with col_left:
                st.subheader("📝 Review Draft")
                # Editable Text Area
                edited_draft = st.text_area(
                    label="Edit before sending:",
                    value=lead.draft_message,
                    height=250,
                    key=f"draft_{lead.lead_id}"
                )
                
                btn_col1, btn_col2 = st.columns(2)
                if btn_col1.button("✅ Approve & Send", key=f"approve_{lead.lead_id}"):
                    # In real app: Update draft content with edit, then send
                    lead.draft_message = edited_draft 
                    db.upsert_lead(lead) 
                    workflow.approve_draft(lead.lead_id)
                    st.toast(f"Message sent to {lead.first_name}!")
                    st.rerun()
                
                if btn_col2.button("✋ Reject / Flag", key=f"flag_{lead.lead_id}"):
                    st.warning("Flagging feature coming in v2")

            with col_right:
                st.subheader("🔍 Context")
                st.markdown(f"**Score:** `{lead.fit_score * 100:.1f}%`")
                st.markdown(f"**Prof:** {lead.current_profession}")
                st.markdown(f"**Exp:** {lead.experience_years}")
                st.markdown(f"**Finance:** {lead.financial_readiness}")
                st.markdown(f"**Location:** {lead.location_readiness}")
                st.markdown("---")
                st.markdown(f"**Rec:** {lead.fit_classification}")

# --- TAB 2: TRACKER ---
with tab_tracker:
    if leads:
        # Convert to DataFrame for nice table
        df = pd.DataFrame([l.dict() for l in leads])
        
        # Select and Rename Columns for readability
        display_cols = [
            "timestamp", "first_name", "last_name", "stage", 
            "fit_score", "fit_classification", "financial_readiness"
        ]
        
        # Safety check if cols exist
        available_cols = [c for c in display_cols if c in df.columns]
        
        st.dataframe(
            df[available_cols].style.applymap(
                lambda v: "color: green; font-weight: bold" if v == "Ideal Fit" else "", 
                subset=["fit_classification"]
            ),
            use_container_width=True
        )
    else:
        st.write("No data in pipeline.")