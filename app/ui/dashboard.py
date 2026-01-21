import sys
import os

# Add the project root directory to Python's search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import pandas as pd
import time
from app.db.supabase import db
from app.services.workflow_service import workflow

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Access Afya | Vetting Control Tower",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLING ---
st.markdown("""
<style>
    .badge-ideal { background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-warn { background-color: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .badge-error { background-color: #f8d7da; color: #721c24; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: SIMULATION LAB ---
with st.sidebar:
    st.header("🧪 Simulation Lab")
    
    with st.expander("1️⃣ Ingest New Lead", expanded=True):
        with st.form("sim_ingest"):
            # Using unique email logic to prevent overwriting same ID
            timestamp_id = int(time.time())
            email_default = f"candidate_{timestamp_id}@test.com"
            
            email = st.text_input("Email (ID)", email_default)
            fname = st.text_input("Name", "John")
            prof = st.selectbox("Role", ["Nurse", "Clinical Officer", "Shopkeeper"])
            exp = st.selectbox("Experience", ["3-4+ Years", "1-2 Years", "None"])
            finance = st.selectbox("Finance", ["I have adequate resources (cash available)", "I need a loan"])
            
            if st.form_submit_button("🚀 Inject Lead"):
                payload = {
                    "lead_id": email, 
                    "email": email, 
                    "first_name": fname, 
                    "last_name": "Doe",
                    "phone": "0700000000", 
                    "current_profession": prof, 
                    "experience_years": exp,
                    "has_business_exp": "No", 
                    "financial_readiness_input": finance,
                    "location_county_input": "Nairobi", 
                    "location_status_input": "No"
                }
                
                with st.spinner("Agent is vetting..."):
                    workflow.process_incoming_lead(payload)
                    time.sleep(0.5) # Allow FS to sync
                
                st.success("Lead Ingested!")
                time.sleep(0.5)
                st.rerun()

    with st.expander("2️⃣ Time Travel (Nudge Test)"):
        if st.button("☀️ Run Daily Checks"):
            count = workflow.run_sla_checks()
            if count > 0:
                st.success(f"Generated {count} Nudges!")
            else:
                st.info("No candidates need nudging.")
            time.sleep(1)
            st.rerun()
            
    st.divider()
    if st.button("🗑️ Reset Database", type="primary"):
        db.reset_db()
        st.toast("Database cleared!")
        time.sleep(1)
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("Growth Coordinator Dashboard 🗼")

# Load Data
try:
    leads = db.fetch_all_leads()
except Exception as e:
    st.error(f"Database Error: {e}")
    leads = []

# Filtering Logic
pending_drafts = [l for l in leads if l.draft_message]
total_vetted = len(leads)
ideal_fits = len([l for l in leads if l.fit_classification == "Ideal Fit"])

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("📥 Inbox (Pending)", len(pending_drafts))
c2.metric("📊 Total Pipeline", total_vetted)
c3.metric("⭐ Ideal Fits", ideal_fits)

# Tabs
tab_inbox, tab_tracker = st.tabs(["📥 Inbox & Approvals", "📋 Master Tracker"])

# --- TAB 1: INBOX ---
with tab_inbox:
    if not pending_drafts:
        st.info("🎉 Inbox is empty! Inject a lead or run checks to generate tasks.")
    
    for lead in pending_drafts:
        with st.container():
            # Header
            st.markdown(f"### {lead.first_name} {lead.last_name}")
            
            col_left, col_right = st.columns([1, 2])
            
            with col_left:
                st.caption("CANDIDATE DATA")
                # Badge
                if lead.fit_classification == "Ideal Fit":
                    st.markdown('<span class="badge-ideal">Ideal Fit</span>', unsafe_allow_html=True)
                elif lead.fit_classification == "Not A Fit":
                    st.markdown('<span class="badge-error">No Fit</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="badge-warn">{lead.fit_classification}</span>', unsafe_allow_html=True)
                
                st.write(f"**Score:** `{lead.fit_score:.2f}`")
                st.write(f"**Role:** {lead.current_profession}")
                st.write(f"**Financial:** {lead.financial_readiness}")
                
            with col_right:
                st.caption(f"DRAFT ACTION: {lead.stage}")
                
                # Editable Draft
                new_draft = st.text_area(
                    "Review Message:", 
                    value=lead.draft_message, 
                    height=150,
                    key=f"draft_{lead.lead_id}"
                )
                
                b1, b2 = st.columns([1, 4])
                if b1.button("✅ Send", key=f"send_{lead.lead_id}"):
                    lead.draft_message = new_draft # Save edit
                    db.upsert_lead(lead)
                    workflow.approve_draft(lead.lead_id)
                    st.toast(f"Sent to {lead.first_name}!")
                    time.sleep(0.5)
                    st.rerun()

            st.divider()

# --- TAB 2: TRACKER ---
with tab_tracker:
    if leads:
        # Prepare Table Data
        data = []
        for l in leads:
            data.append({
                "ID": l.lead_id,
                "Date": l.timestamp,
                "Name": f"{l.first_name} {l.last_name}",
                "Stage": l.stage,
                "Score": l.fit_score,
                "Class": l.fit_classification,
                "Draft Waiting?": "✅ Yes" if l.draft_message else "No",
                "Action Due": l.next_step_due_date
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.write("No data found.")