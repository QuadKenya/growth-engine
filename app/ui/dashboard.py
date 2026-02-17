import sys
import os
import json
import base64
from pathlib import Path
from datetime import datetime, timedelta, date, time as dt_time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import pandas as pd
import time
import streamlit.components.v1 as components

from app.db.supabase import db
from app.services.workflow_service import workflow
from app.services.reporting_service import reporter

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Access Afya | Growth Engine",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CUSTOM CSS ---
st.markdown(
    """
<style>
  :root {
    --bg: var(--background-color);
    --text: var(--text-color);
    --card-bg: var(--secondary-background-color);
    --border: rgba(128,128,128,0.25);
  }

  .stApp {
    background: var(--bg) !important;
    color: var(--text) !important;
  }

  .lead-card {
    background: var(--card-bg) !important;
    color: var(--text) !important;
    padding: 20px;
    border-radius: 10px;
    border-left: 5px solid #2e86de;
    border: 1px solid var(--border);
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    margin-bottom: 15px;
  }
  .lead-card.hot { border-left-color: #ff4757; }
  .lead-card.warm { border-left-color: #ffa502; }
  .lead-card.compliance { border-left-color: #2ed573; }
  .lead-card.late-stage { border-left-color: #a55eea; }
  .lead-card.closed { border-left-color: #2ed573; border-left-width: 8px; }

  .status-badge {
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    display: inline-block;
    color: white !important;
  }
  .status-hot { background-color: #ff4757; }
  .status-warm { background-color: #ffa502; }
  .status-new { background-color: #3742fa; }
  .status-success { background-color: #2ed573; }
  .status-purple { background-color: #a55eea; }

  .activity-log {
    max-height: 200px;
    overflow-y: auto;
    background: rgba(0,0,0,0.02);
    padding: 10px;
    border-radius: 5px;
    font-size: 0.9em;
    margin-bottom: 10px;
  }
  .log-entry {
    margin-bottom: 8px;
    border-bottom: 1px solid #eee;
    padding-bottom: 4px;
  }
  .log-meta { font-size: 0.8em; color: #888; }

  /* Streamlit 1.53.1: make ONLY the metric label bigger (keep numbers unchanged) */
    [data-testid="stMetric"] [data-testid="stMetricLabel"],
    [data-testid="stMetric"] [data-testid="stMetricLabel"] * {
    font-size: 1.6rem !important;   /* <- increase/decrease this */
    font-weight: 700 !important;
    line-height: 1.15 !important;
 }
</style>
""",
    unsafe_allow_html=True,
)

# --- LOGO & ASSETS ---
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "access_afya_logo.png"
if not LOGO_PATH.exists():
    LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "access_afya_logo.png"

def render_sidebar_logo(path: Path):
    if path.exists():
        st.sidebar.image(str(path), width=200)
    else:
        st.sidebar.title("Access Afya")

# --- HELPER: RESET DB ---
def reset_database():
    file_path = os.path.join(os.path.dirname(__file__), "../../data/local_db.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([], f)
    st.toast("Database Wiped Clean!", icon="🧹")
    time.sleep(1)
    st.rerun()

def _safe_str(x) -> str:
    return str(x) if x is not None else ""

# --- HELPER: SEARCH FUNCTIONALITY ---
def filter_leads(leads, query):
    if not query:
        return leads
    q = query.lower()
    return [
        l for l in leads 
        if q in _safe_str(getattr(l, "first_name", "")).lower() 
        or q in _safe_str(getattr(l, "last_name", "")).lower()
        or q in _safe_str(getattr(l, "email", "")).lower()
    ]

# --- HELPER: DATE RANGE NORMALIZATION ---
def _normalize_date_range(dr):
    if isinstance(dr, (list, tuple)):
        if len(dr) == 2:
            return dr[0], dr[1]
        if len(dr) == 1:
            return dr[0], dr[0]
        today = date.today()
        return today, today
    return dr, dr

# --- HELPER: RENDER ACTIVITY LOG (FIXED) ---
def render_activity_feed(lead):
    logs = getattr(lead, "activity_log", []) or []

    # Input for new note
    new_note_content = st.text_area("Note Content", key=f"note_content_{getattr(lead,'lead_id','')}", placeholder="Type note here", height=100)
    add_button = st.button("Add Note", key=f"add_button_{getattr(lead,'lead_id','')}")

    if add_button and new_note_content:
        workflow.add_note(lead.lead_id, new_note_content)
        st.toast("Note Added")
        time.sleep(0.5)
        st.rerun()
    
    st.divider()
    
    if not logs:
        st.caption("No activity recorded.")
    else:
        # Helper to safely get attributes
        def get_log_val(obj, attr, default=None):
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        # Sort newest first
        logs = sorted(logs, key=lambda x: get_log_val(x, 'timestamp') or '', reverse=True)
        
        with st.container(height=250):
            for log in logs:
                ts_raw = get_log_val(log, 'timestamp')
                try:
                    if isinstance(ts_raw, str):
                        dt = datetime.fromisoformat(str(ts_raw).replace('Z', ''))
                    else:
                        dt = ts_raw
                    ts_str = dt.strftime("%b %d, %H:%M")
                except:
                    ts_str = str(ts_raw)[:16]

                author = get_log_val(log, 'author', 'System')
                content = get_log_val(log, 'content', '')
                icon = "🤖" if author == "System" else "👤"

                st.markdown(f"""
                <div style="border-bottom: 1px solid #f0f2f6; padding-bottom: 10px; margin-bottom: 10px;">
                    <div style="font-size: 0.85rem; color: #6b7280;">{icon} <b>{author}</b> • {ts_str}</div>
                    <div style="font-size: 1rem; padding-top: 4px;">{content}</div>
                </div>
                """, unsafe_allow_html=True)

# --- HELPER: RENDER LEAD CARD ---
def render_lead_card(lead):
    css_class = "lead-card"
    stage = getattr(lead, "stage", "")
    badge_html = f'<span class="status-badge status-new">{stage}</span>'

    if getattr(lead, "priority_rank", None) == 1:
        css_class += " hot"
        badge_html = '<span class="status-badge status-hot">🔥 Rank 1: Site Ready</span>'
    elif getattr(lead, "priority_rank", None) == 2:
        badge_html = '<span class="status-badge status-warm">💰 Rank 2: Cash Ready</span>'
    elif stage == "WARM_LEAD":
        css_class += " warm"
        badge_html = '<span class="status-badge status-warm">🌤️ Nurture</span>'
    elif stage == "KYC_SCREENING":
        css_class += " compliance"
        badge_html = '<span class="status-badge status-success">📂 Compliance</span>'
    elif stage in ["FINANCIAL_ASSESSMENT", "ASSESSMENT_PSYCH", "SITE_SEARCH", "SITE_PRE_VISIT", "SITE_POST_VISIT"]:
        css_class += " late-stage"
        badge_html = f'<span class="status-badge status-purple">{stage}</span>'
    elif stage == "CONTRACT_CLOSED":
        css_class += " closed"
        badge_html = '<span class="status-badge status-success">✅ Contracted</span>'

    with st.container():
        st.markdown(
            f"""
            <div class="{css_class}">
              <div style="display:flex; justify-content:space-between; align-items:center; gap: 12px;">
                <h3 style="margin:0; color: var(--text-color);">
                  {_safe_str(getattr(lead, "first_name", ""))} {_safe_str(getattr(lead, "last_name", ""))}
                </h3>
                {badge_html}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("View Details & Actions", expanded=False):
            # Layout: Data | Agent/Action | Log
            col_data, col_action, col_log = st.columns([1, 1.5, 1.5], gap="medium")

            with col_data:
                st.caption("PROFILE")
                st.write(f"**Role:** {_safe_str(getattr(lead, 'current_profession', ''))}")
                st.write(f"**Work Experience:** {_safe_str(getattr(lead, 'experience_years', ''))}")
                st.write(f"**County:** {_safe_str(getattr(lead, 'location_county_input', ''))}")
                st.write(f"**Biz Experience:** {_safe_str(getattr(lead, 'has_business_exp', ''))}")
                st.write(f"**Finances:** {_safe_str(getattr(lead, 'financial_readiness_input', ''))}")
                st.write(f"**Location:** {_safe_str(getattr(lead, 'location_status_input', ''))}")
                st.write(f"**Stage:** {_safe_str(getattr(lead, 'stage', ''))}")
                
                # Show Rejection/Nurture reason if applicable
                if getattr(lead, "stage", "") == "WARM_LEAD":
                     st.write(f"**Reason:** {_safe_str(getattr(lead, 'soft_rejection_reason', ''))}")
                     st.write(f"**Wake Up:** {_safe_str(getattr(lead, 'wake_up_date', ''))}")

                if getattr(lead, "verified_financial_capital", None):
                    st.success(f"**Verified Revenue:** KES {getattr(lead, 'verified_financial_capital'):,.0f}")
                
                if getattr(lead, "site_assessment_results", None):
                    res = lead.site_assessment_results
                    st.info(f"**Site Score:** {res.overall_site_score*100:.0f}%")
                    st.write(f"**Competition:** {res.competition_status}")

                st.caption(f"Applied: {getattr(lead, 'timestamp')}")

            with col_action:
                st.caption("ACTIONS")
                
                # --- DRAFTING SECTION ---
                if getattr(lead, "draft_message", None):
                    st.info("Draft Pending")
                    txt = st.text_area("Edit:", value=lead.draft_message, height=100, key=f"d_{lead.lead_id}")
                    if st.button("✅ Approve & Send", key=f"s_{lead.lead_id}", width="stretch"):
                        workflow.approve_draft(lead.lead_id, message_override=txt)
                        st.toast("Sent!")
                        time.sleep(0.5)
                        st.rerun()

                # --- STAGE SPECIFIC ACTIONS ---
                if stage == "INTEREST_CHECK_SENT":
                    st.warning("Waiting for Reply...")
                    b1, b2 = st.columns(2)
                    if b1.button("✅ Replied YES", key=f"y_{lead.lead_id}", width='stretch'):
                        workflow.handle_interest_response(lead.lead_id, "YES")
                        st.rerun()
                    if b2.button("⏳ Replied LATER", key=f"m_{lead.lead_id}", width='stretch'):
                        workflow.handle_interest_response(lead.lead_id, "MAYBE")
                        st.rerun()

                # Gate 3: Call Ready
                if stage == "READY_FOR_CALL":
                    st.success("Candidate is Ready for Intro Call")
                    if st.button("✅ Call Complete / Start KYC", key=f"kyc_{lead.lead_id}", width="stretch"):
                        workflow.initialize_checklist(lead.lead_id)
                        time.sleep(1)
                        st.rerun()

                # Gate 4: Compliance Checklist
                if stage == "KYC_SCREENING":
                    items = getattr(lead, "checklist_status", {})
                    if items:
                        total = len(items)
                        completed = sum(1 for v in items.values() if v)
                        ratio = completed / total
                        missing_count = total - completed
                        
                        st.progress(ratio, text=f"Progress: {int(ratio*100)}%")

                        # Visual Reminder (Yellow Box)
                        missing_items = [k for k, v in items.items() if not v]
                        
                        if missing_items:
                            # Create a bulleted list string
                            missing_str = "\n".join([f"- {item}" for item in missing_items])
                            st.warning(f"**⚠️ Outstanding Documents ({len(missing_items)}):**\n\n{missing_str}")
                            
                        else:
                            st.success("All documents verified! Moving to Financials...")

                        # Checklist Manager (Popover)
                        with st.popover(f"✅ Update Checklist ({completed}/{total})", width='stretch'):
                            for item, status in items.items():
                                is_checked = st.checkbox(item, value=status, key=f"{lead.lead_id}_{item}")
                                if is_checked != status:
                                    workflow.update_checklist(lead.lead_id, item, is_checked)
                                    st.rerun()
                    else:
                        st.warning("No checklist initialized.")
                        
                # Gate 4: Financials
                if stage == "FINANCIAL_ASSESSMENT":
                    st.subheader("💰 ABD & ABB Calculator")
                    st.info("Complete the Statement Credits and Periodic Balances below to compute capacity.")

                    # --- Step 1: ABD (Average Bank Deposits) ---
                    with st.popover("📊 Step 1: Statement Credits (ABD)", width='stretch'):
                        st.caption("Enter credit rows. Only 'Included' deposits count towards revenue.")

                        # Robust data initialization
                        current_rows = getattr(lead.financial_data, "statement_rows", None) or []
                        if not current_rows:
                            # IMPORTANT: use a real date object, not a string (Streamlit DateColumn requires this)
                            current_rows = [{"date": date.today(), "credit_amount": 0.0, "include_deposit": True}]

                        # DataFrame conversion + dtype normalization for Streamlit
                        initial_df = pd.DataFrame(current_rows)

                        # Ensure required columns exist
                        if "date" not in initial_df.columns:
                            initial_df["date"] = date.today()
                        if "credit_amount" not in initial_df.columns:
                            initial_df["credit_amount"] = 0.0
                        if "include_deposit" not in initial_df.columns:
                            initial_df["include_deposit"] = True

                        # Convert date strings -> datetime.date (required for DateColumn)
                        initial_df["date"] = pd.to_datetime(initial_df["date"], errors="coerce").dt.date
                        initial_df["date"] = initial_df["date"].fillna(date.today())

                        # Normalize other dtypes (prevents weird editor type issues)
                        initial_df["credit_amount"] = pd.to_numeric(initial_df["credit_amount"], errors="coerce").fillna(0.0).astype("float64")
                        initial_df["include_deposit"] = initial_df["include_deposit"].fillna(True).astype(bool)

                        edited_abd = st.data_editor(
                            initial_df,
                            num_rows="dynamic",
                            column_config={
                                "date": st.column_config.DateColumn("Date", required=True, format="YYYY-MM-DD"),
                                "credit_amount": st.column_config.NumberColumn("Amount (KES)", min_value=0, format="%.2f"),
                                "include_deposit": st.column_config.CheckboxColumn("Include?"),
                            },
                            key=f"abd_editor_final_{lead.lead_id}",
                            width='stretch',
                        )

                    # --- Step 2: ABB (Average Bank Balances) ---
                    with st.popover("🏦 Step 2: Periodic Balances (ABB)", width='stretch'):
                        st.caption("Enter balances for the 5th, 10th, 15th, 20th, 25th, and 30th.")

                        checkpoints = ["5th", "10th", "15th", "20th", "25th", "30th"]
                        months = ["Month 1", "Month 2", "Month 3", "Month 4", "Month 5", "Month 6"]
                        existing_grid = getattr(lead.financial_data, "abb_grid", {}) or {}

                        new_abb_grid: dict[str, dict[str, float]] = {}
                        for m in months:
                            with st.expander(f"📅 {m}", expanded=(m == "Month 1")):
                                cols = st.columns(3)
                                new_abb_grid[m] = {}
                                for i, cp in enumerate(checkpoints):
                                    col_idx = i % 3
                                    default_val = existing_grid.get(m, {}).get(cp)
                                    val = cols[col_idx].number_input(
                                        f"Day {cp}",
                                        value=float(default_val) if default_val is not None else 0.0,
                                        min_value=0.0,
                                        key=f"abb_{m}_{cp}_{lead.lead_id}",
                                    )
                                    new_abb_grid[m][cp] = float(val)

                    # --- Step 3: Action & Feedback ---
                    if st.button(
                        "🧮 Compute & Submit Assessment",
                        key=f"sub_fin_{lead.lead_id}",
                        width='stretch',
                        type="primary",
                    ):
                        from app.models.domain import FinancialAssessmentData

                        # Serialize rows: convert datetime.date/datetime -> ISO strings (stable for DB/JSON)
                        rows = edited_abd.to_dict("records")
                        for r in rows:
                            d = r.get("date")
                            if d is None:
                                continue
                            # datetime -> date
                            if hasattr(d, "date"):
                                try:
                                    d = d.date()
                                except Exception:
                                    pass
                            # date -> "YYYY-MM-DD"
                            if hasattr(d, "isoformat"):
                                r["date"] = d.isoformat()
                            else:
                                r["date"] = str(d)

                            # Ensure expected fields exist and types are sane
                            r["credit_amount"] = float(r.get("credit_amount") or 0.0)
                            r["include_deposit"] = bool(r.get("include_deposit", True))

                        # Payload preparation
                        payload = FinancialAssessmentData(
                            statement_rows=rows,
                            abb_grid=new_abb_grid,
                        )

                        # Execution
                        with st.spinner("Calculating capacity and updating lead status..."):
                            workflow.submit_financial_assessment(lead.lead_id, payload)
                            st.toast("✅ Assessment Calculated Successfully!", icon="💰")

                        # Give the user a moment to see the toast before the UI refreshes
                        time.sleep(1)
                        st.rerun()

                # Gate 5: Psych & Interview
                if stage == "ASSESSMENT_PSYCH":
                    st.info("Psychometrics Link Sent.")
                    if st.button("Mark Test Complete", key=f"psy_{lead.lead_id}"):
                        lead.stage = "ASSESSMENT_INTERVIEW"
                        db.upsert_lead(lead)
                        st.rerun()
                
                if stage == "ASSESSMENT_INTERVIEW":
                    res = st.radio("Interview Result", ["PASS", "FAIL"], key=f"int_res_{lead.lead_id}")
                    note = st.text_area("Interview Notes", key=f"int_note_{lead.lead_id}", placeholder="Type note here", height=100)
                    if st.button("Log Result", key=f"log_int_{lead.lead_id}"):
                        workflow.log_interview_result(lead.lead_id, res, note)
                        st.rerun()

                # Gate 6: Site & Contract
                if stage == "SITE_SEARCH":
                    st.info("Lead is currently scouting for a location.")
                    if st.button("🔍 Start Site Review", key=f"start_rev_{lead.lead_id}", width='stretch'):
                        workflow.start_site_review(lead.lead_id)
                        st.rerun()

                if stage == "SITE_PRE_VISIT":
                    st.subheader("🖥️ Desktop Screening")
                    checklist = lead.site_assessment_data.pre_visit_checklist
                    missing = [k for k, v in checklist.items() if not v]
                    
                    if missing:
                        st.warning(f"**⚠️ Outstanding Information:**\n" + "\n".join([f"- {i.replace('_',' ').title()}" for i in missing]))
                    
                    with st.popover("📝 Update Pre-Visit Items", width='stretch'):
                        for item, status in checklist.items():
                            if st.checkbox(item.replace('_',' ').title(), value=status, key=f"pre_{lead.lead_id}_{item}") != status:
                                workflow.update_pre_visit_checklist(lead.lead_id, item, not status)
                                st.rerun()

                if stage == "SITE_POST_VISIT":
                    st.subheader("📍 Field Scorecard")
                    st.info("Input findings from the physical site visit.")
                    
                    with st.form(f"scorecard_{lead.lead_id}"):
                        c1, c2 = st.columns(2)
                        setting = c1.selectbox("Cluster Type", ["Urban", "Semi-Urban", "Rural"])
                        archetype = c2.selectbox("Site Archetype", [1, 2, 3, 4], format_func=lambda x: {1:"1: Bad", 2:"2: Fair", 3:"3: Good", 4:"4: Excellent"}[x])
                        
                        st.divider()
                        st.write("**Competition & Market**")
                        cc1, cc2, cc3 = st.columns(3)
                        clinics = cc1.number_input("Private Clinics (1km)", min_value=0)
                        pharms = cc2.number_input("Pharmacies (1km)", min_value=0)
                        traffic = cc3.number_input("Foot Traffic (Hourly)", min_value=0)
                        
                        st.divider()
                        st.write("**Physical Condition**")
                        cp1, cp2 = st.columns(2)
                        sqft = cp1.number_input("Building Size (sqft)", min_value=0)
                        rooms = cp2.checkbox("At least 2 rooms?")
                        vent = st.checkbox("Ventilated and well-lit?")
                        mobile = st.checkbox("Mobility Accessible?")
                        
                        st.divider()
                        st.write("**Utilities**")
                        cu1, cu2, cu3, cu4 = st.columns(4)
                        elec = cu1.checkbox("Electricity")
                        water = cu2.checkbox("Water")
                        net = cu3.checkbox("Internet")
                        toilet = cu4.checkbox("Private Toilets")

                        if st.form_submit_button("🧮 Submit Site Scorecard", width='stretch'):
                            from app.models.domain import SiteAssessmentData
                            data = SiteAssessmentData(
                                setting_type=setting, archetype_score=archetype,
                                competition_clinics_1km=clinics, competition_pharmacies_1km=pharms,
                                foot_traffic_count=traffic, building_sqft=sqft,
                                has_2_rooms=rooms, ventilated_well_lit=vent, mobile_accessible=mobile,
                                electricity_available=elec, water_available=water,
                                internet_possible=net, private_toilets=toilet
                            )
                            workflow.submit_site_scorecard(lead.lead_id, data)
                            st.rerun()

                # Fire celebration on next rerun EVEN IF stage has already advanced
                celebration_key = f"onboard_success_{lead.lead_id}"
                if st.session_state.get(celebration_key):
                    st.balloons()
                    st.toast("🎉 Lead Successfully Contracted!", icon="🤝🏽")
                    st.session_state[celebration_key] = False

                if stage == "CONTRACTING":
                    st.success("🎉 Site Approved! Contract has been generated.")
                    if st.button("🚀 Finalize Onboarding", key=f"cc_{lead.lead_id}", width='stretch'):
                        workflow.close_contract(lead.lead_id)

                        # Set the flag so balloons fire on the next rerun
                        st.session_state[celebration_key] = True
                        st.rerun()

                elif stage == "CONTRACT_CLOSED":
                    st.success("Franchisee Onboarded 🎉")

                
		# --- WARM LEAD SPECIFIC ACTIONS (Reactivate / Reject) ---
                if stage == "WARM_LEAD":
                    st.divider()
                    c1, c2 = st.columns(2)
                    if c1.button("♻️ Reactivate", key=f"react_{lead.lead_id}", width='stretch'):
                        # UPDATED: Use the workflow helper to regenerate draft and fix state
                        workflow.reactivate_lead(lead.lead_id)
                        st.toast("Lead Reactivated!")
                        time.sleep(0.5)
                        st.rerun()
                    
                    if c2.button("❌ Reject", key=f"r_warm_{lead.lead_id}", width='stretch'):
                        workflow.hard_reject(lead.lead_id)
                        st.rerun()

                # --- STANDARD ACTIONS (Move to Warm / Reject) ---
                elif stage not in ["TURNED_DOWN", "CONTRACT_CLOSED", "WARM_LEAD"]:
                    st.divider()
                    c1, c2 = st.columns(2)
                    if c1.button("🌤️ Warm", key=f"w_{lead.lead_id}", width="stretch"):
                        workflow.move_to_warm(lead.lead_id)
                        st.rerun()
                    if c2.button("❌ Reject", key=f"r_{lead.lead_id}", width="stretch"):
                        workflow.hard_reject(lead.lead_id)
                        st.rerun()

            with col_log:
                st.caption("📝 ACTIVITY & NOTES")
                render_activity_feed(lead)


# --- SIDEBAR & NAVIGATION ---
with st.sidebar:
    render_sidebar_logo(LOGO_PATH)
    st.title("Growth Engine")

    view_mode = st.radio("Pipeline Views", [
        "📥 Inbox (New Leads)",
        "🔥 Hot Leads (Action Required)",
        "🌤️ Warm Leads (Nurture)",
        "💬 Engagement (Screening)",
        "📂 Compliance (KYC)",
        "💰 Financial Assessment",
        "🧠 Psychometric & Interview",
        "📍 Site & Contract",
        "🤝🏽 Contracted / Alumni",
	    "📈 KPI Reports",
        "🔍 Master Database"
    ],
    key="view_mode",
    )

    st.divider()
    
    # Simulation Lab
    with st.expander("🧪 Simulation"):
        with st.form("sim_ingest", clear_on_submit=True):
            # CHANGED: Direct Text Input for Email
            email = st.text_input("Email", placeholder="candidate@example.com")
            
            c1, c2 = st.columns(2)
            fname = c1.text_input("First Name", "Jane")
            lname = c2.text_input("Last Name", "Doe")
            prof = st.selectbox("Role", ["Clinical Officer", "Nurse", "Medical Doctor", "Shopkeeper"])
            exp = st.selectbox("Experience", ["3-4+ Years", "1-2 Years", "None"])
            biz_exp = st.selectbox("Business Experience?", ["Yes", "No"])
            fin = st.selectbox("Finance", ["I have adequate resources", "I need a loan"])
            county = st.selectbox("County", ["Nairobi", "Mombasa", "Kiambu", "Marsabit"])
            loc = st.selectbox("Location", ["Yes, I own or lease a location", "No, but I have found ideal locations", "No"])
            
            if st.form_submit_button("🚀 Inject"):
                # 1. Quick Validation
                if not email or "@" not in email:
                    st.error("⚠️ Please enter a valid email address (must contain '@').")
                else:
                    try:
                        payload = {
                            "lead_id": email, 
                            "email": email, 
                            "first_name": fname, 
                            "last_name": lname, 
                            "phone": "254700000000", 
                            "current_profession": prof, 
                            "experience_years": exp, 
                            "has_business_exp": biz_exp, 
                            "financial_readiness_input": fin, 
                            "location_county_input": county, 
                            "location_status_input": loc,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        workflow.process_incoming_lead(payload)
                        st.toast("Injected Successfully!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Input Error: {str(e)}")
                
    st.divider()
    if st.button("🗑️ Reset Database"):
        reset_database()

# --- MAIN DASHBOARD LOGIC ---
leads = db.fetch_all_leads()
cohorts = workflow.get_all_cohorts()

# Filter Helpers
def get_leads_by_stage(stages): return [l for l in leads if getattr(l, "stage", "") in stages]

# Metrics
# UPDATED: Added Compliance Pending Metric
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Pipeline", len(leads))
m2.metric("📝 Pending Drafts", len([l for l in leads if getattr(l, "draft_message", None)]))
m3.metric("📂 KYC Screening", len(get_leads_by_stage(["KYC_SCREENING"]))) 
m4.metric("🌤️ Warm/Nurture", len(get_leads_by_stage(["WARM_LEAD"])))
m5.metric("🤝🏽 Contracted", len(get_leads_by_stage(["CONTRACT_CLOSED"])))

st.divider()

# --- SEARCH BAR (COMMON FOR ACTIVE TABS) ---
if view_mode != "🔍 Master Database":
    search_q = st.text_input("🔍 Filter Leads", placeholder="Search by name or email...")
    if search_q:
        leads = filter_leads(leads, search_q)

    components.html(
        """
    <script>
    (function () {
    const stop = Date.now() + 3000; // try for up to 3s
    const timer = setInterval(() => {
        const doc = window.parent.document;

        // Find the input by its placeholder text
        const el = Array.from(doc.querySelectorAll('input'))
        .find(i => i.getAttribute('placeholder') === 'Search by name or email...');

        if (el) {
        el.setAttribute('autocomplete', 'off');
        el.setAttribute('autocorrect', 'off');
        el.setAttribute('autocapitalize', 'off');
        el.setAttribute('spellcheck', 'false');

        // IMPORTANT: change the name so Chrome won't reuse past entries
        el.setAttribute('name', 'lead_search_' + Math.random().toString(36).slice(2));

        clearInterval(timer);
        }

        if (Date.now() > stop) clearInterval(timer);
    }, 100);
    })();
    </script>
    """,
        height=0,
)

# --- VIEWS ---

if view_mode == "📥 Inbox (New Leads)":
    st.header("Inbox: New Leads")
    targets = [l for l in leads if getattr(l, "draft_message", None) and l.stage in ["EXPRESSED_INTEREST", "POTENTIAL_FIT", "NO_FIT"]]
    if not targets: st.success("Inbox Zero! Great job. 🧘")
    for l in targets: render_lead_card(l)

elif view_mode == "🔥 Hot Leads (Action Required)":
    st.header("Prioritized Call List")
    targets = get_leads_by_stage(["READY_FOR_CALL", "INTEREST_CHECK_SENT"])
    targets.sort(key=lambda x: getattr(x, "priority_rank", 999))
    if not targets: 
        st.info("No hot leads pending calls or replies.")
        st.caption("Check the 'Engagement' tab if you are looking for leads currently being screened.")
    
    for l in targets: 
        render_lead_card(l)

elif view_mode == "🌤️ Warm Leads (Nurture)":
    st.header("Warm Leads")
    targets = get_leads_by_stage(["WARM_LEAD"])
    if not targets: st.info("No Warm Leads.")
    for l in targets: render_lead_card(l)

elif view_mode == "💬 Engagement (Screening)":
    st.header("Engagement")
    targets = get_leads_by_stage(["FAQ_SENT"])
    if not targets: st.info("No active engagement.")
    for l in targets: render_lead_card(l)

elif view_mode == "📂 Compliance (KYC)":
    st.header("Compliance Checklist")
    targets = get_leads_by_stage(["KYC_SCREENING"])
    if not targets: st.info("No active compliance checks.")
    for l in targets: render_lead_card(l)

elif view_mode == "💰 Financial Assessment":
    st.header("Financial Assessment")
    targets = get_leads_by_stage(["FINANCIAL_ASSESSMENT"])
    if not targets: st.info("No financial assessments pending.")
    for l in targets: render_lead_card(l)

elif view_mode == "🧠 Psychometric & Interview":
    st.header("Psych & Interview")
    targets = get_leads_by_stage(["ASSESSMENT_PSYCH", "ASSESSMENT_INTERVIEW"])
    if not targets: st.info("No assessments pending.")
    for l in targets: render_lead_card(l)

elif view_mode == "📍 Site & Contract":
    st.header("Site Vetting & Contracting")
    targets = get_leads_by_stage(["SITE_SEARCH", "SITE_PRE_VISIT", "SITE_POST_VISIT", "CONTRACTING"])
    if not targets: st.info("No pending contracts.")
    for l in targets: render_lead_card(l)

elif view_mode == "🤝🏽 Contracted / Alumni":
    st.header("Contracted Franchisees")
    targets = get_leads_by_stage(["CONTRACT_CLOSED"])
    if not targets: st.info("No contracted leads yet.")
    for l in targets: render_lead_card(l)

if view_mode == "📈 KPI Reports":
    st.header("Operational Intelligence")
    
    # 1. COHORT FILTER
    c_names = ["All Time"] + [c.name for c in cohorts]
    sel_cohort = st.selectbox("Analysis Cohort", c_names, help="Filter reports by a specific Call for EOI")
    
    report_leads = leads
    if sel_cohort != "All Time":
        c = next(x for x in cohorts if x.name == sel_cohort)
        # Filter leads by application date falling within cohort range
        report_leads = [
            l for l in leads 
            if getattr(l, 'timestamp', datetime.min) 
            and l.timestamp.date() >= c.start_date 
            and l.timestamp.date() <= c.end_date
        ]
    
    # 2. RUN CALCULATIONS
    stats = reporter.calculate_general_stats(report_leads)
    funnel = reporter.calculate_funnel(report_leads)
    cycles = reporter.calculate_cycle_times(report_leads)
    
    # 3. HEADLINE METRICS (SPEED & HEALTH)
    # st.subheader("🚀 Velocity & Health")
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.metric(
            "Total Cycle", 
            f"{cycles['avg_to_contract']} Days", 
            help="Average time from Application to Contract Signed (Closed wins only)"
        )
    with m2:
        st.metric(
            "To Psychometric", 
            f"{cycles['avg_to_psych']} Days", 
            help="Average time to clear Vetting, Compliance, and Financials"
        )
    with m3:
        st.metric(
            "Rejection Rate", 
            stats["rejection_rate"], 
            help="% of applicants who were Hard Rejected (Quality indicator)",
            delta_color="inverse"
        )
    with m4:
        st.metric(
            "Hot : Warm Ratio", 
            stats["hot_warm_ratio"],
            help="Balance between ready-to-close leads and nurturing leads"
        )

    st.divider()

    # 4. DEEP DIVE VISUALS
    c_left, c_right = st.columns([3, 2], gap="large")
    
    with c_left:
        st.subheader("⏱️ Journey Velocity (Avg Days)")
        st.caption("Time taken to reach specific milestones from Application Date.")
        
        # Prepare Data for Chart
        if any(cycles["milestone_values"]):
            journey_df = pd.DataFrame({
                "Milestone": cycles["milestone_labels"],
                "Days": cycles["milestone_values"]
            })
            # Visual Chart
            st.bar_chart(data=journey_df, x="Milestone", y="Days", color="#2e86de")
            
            # Smart Insights / Bottleneck Detection
            psych_days = cycles["avg_to_psych"]
            contract_days = cycles["avg_to_contract"]
            
            if psych_days > 45:
                st.error(f"⚠️ **Bottleneck Alert:** It takes {psych_days} days to reach Psychometrics. Review the Compliance/Financial collection process.")
            elif psych_days > 0 and contract_days > (psych_days * 2):
                st.warning("⚠️ **Closing Lag:** Site Vetting & Contracting is taking longer than the entire vetting process combined.")
            elif psych_days > 0:
                st.success("✅ **Velocity Check:** Pipeline is moving at a healthy pace.")
        else:
            st.info("No timeline data available for this cohort yet. Move leads through stages to generate velocity metrics.")

    with c_right:
        st.subheader("🎯 Conversion Funnel")
        st.caption("Candidate drop-off at key gates.")
        
        if funnel:
            # Table View
            funnel_df = pd.DataFrame({
                "Stage": funnel["labels"],
                "Candidates": funnel["counts"],
                "Conversion Rate": [f"{p:.1f}%" for p in funnel["percentages"]]
            })
            st.dataframe(funnel_df, width='stretch', hide_index=True)
            
            # Simple Text Summary
            conversion = funnel.get("overall_conversion", 0)
            if conversion > 0:
                st.write(f"**Overall Success Rate:** {conversion:.1f}%")
        else:
            st.info("No funnel data.")

    st.divider()

    # 5. PREDICTIVE FORECASTING
    st.subheader("🔮 Pipeline Forecasting")
    f_col1, f_col2 = st.columns([1, 2])
    
    with f_col1:
        target = st.number_input("Target New Contracts", min_value=1, value=10, help="How many new clinics do you want to open?")
    
    with f_col2:
        forecast = reporter.generate_forecast(report_leads, target)
        
        if forecast["current_rate"] > 0:
            req_leads = forecast["required_leads"]
            curr_rate = forecast["current_rate"]
            current_total = stats["total"]
            gap = req_leads - current_total
            
            st.metric(
                label=f"Required Applications (at {curr_rate}% conversion)", 
                value=req_leads,
                delta=f"-{gap} needed" if gap > 0 else "Target Met",
                delta_color="normal" if gap <= 0 else "inverse"
            )
            
            if gap > 0:
                st.warning(f"Based on historical performance, you need to acquire **{gap}** more leads to hit your target of {target} contracts.")
            else:
                st.success(f"You have enough leads in the pipeline to hit your target of {target} contracts!")
        else:
            st.info("Insufficient data to forecast. Close at least one contract to establish a baseline conversion rate.")

elif view_mode == "🔍 Master Database":
    st.header("Master Database")
    st.caption("Analyze cohorts, search leads, and inspect full records.")

    # 1. COHORT MANAGEMENT SECTION
    with st.expander("📁 Manage Call-for-EOI Cohorts"):
        c_form1, c_form2, c_form3 = st.columns([2, 3, 2])
        with c_form1:
            new_cohort_name = st.text_input("Cohort Name", placeholder="e.g. Q1 2025 Call", key="new_coh_name")
        with c_form2:
            # Independent date input for creation - defaults to last 30 days
            new_cohort_dates = st.date_input(
                "EOI Date Range", 
                value=[date.today() - timedelta(days=30), date.today()],
                key="new_coh_dates"
            )
        with c_form3:
            st.write("") # Padding
            if st.button("➕ Create Cohort", width='stretch'):
                if new_cohort_name and isinstance(new_cohort_dates, (list, tuple)) and len(new_cohort_dates) == 2:
                    workflow.create_cohort(new_cohort_name, new_cohort_dates[0], new_cohort_dates[1])
                    st.toast(f"Cohort '{new_cohort_name}' defined successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please provide a name and select both a Start and End date.")
        
        if cohorts:
            st.divider()
            st.caption("Active Cohort Definitions")
            for c in cohorts:
                cols = st.columns([3, 4, 1])
                cols[0].write(f"**{c.name}**")
                cols[1].write(f"{c.start_date.strftime('%d %b %Y')} — {c.end_date.strftime('%d %b %Y')}")
                if cols[2].button("🗑️", key=f"del_{c.name}"):
                    workflow.delete_cohort(c.name)
                    st.rerun()

    if not leads:
        st.info("No leads found in the database.")
    else:
        # Data Preparation
        df_all = pd.DataFrame([l.dict() for l in leads])
        # Ensure columns exist
        for col in ["lead_id","first_name","last_name","stage","priority_rank","fit_score","fit_classification","timestamp","draft_message","notes"]:
            if col not in df_all.columns: df_all[col] = None
            
        df_all["Name"] = (df_all["first_name"].fillna("").astype(str) + " " + df_all["last_name"].fillna("")).str.strip()
        df_all["_applied_dt"] = pd.to_datetime(df_all["timestamp"], errors="coerce")

        # Create filterable dataframe
        df_skinny = df_all[["lead_id", "Name", "stage", "priority_rank", "fit_score", "fit_classification", "timestamp", "_applied_dt", "draft_message", "notes"]].copy()
        df_skinny.rename(columns={
            "lead_id":"ID",
            "stage":"Stage",
            "priority_rank":"Rank",
            "fit_score":"Score",
            "fit_classification":"Fit",
            "timestamp":"Date",
            "draft_message":"Action",
            "notes":"Notes"
        }, inplace=True)

        # --- FILTERS ROW ---
        st.subheader("Global Filters")
        f0, f1, f2, f3, f4 = st.columns([2, 2, 2, 2, 2])
        
        with f0:
            cohort_names = ["No Filter"] + [c.name for c in cohorts]
            # Use index to avoid reset on rerun
            selected_cohort_name = st.selectbox("Cohort (EOI Call)", options=cohort_names, key="master_cohort_filter")
        
        with f1:
            stage_opts = sorted([str(s) for s in df_skinny["Stage"].dropna().unique().tolist() if str(s).strip()])
            stage_sel = st.multiselect("Stage", options=stage_opts)

        with f2:
            rank_opts = sorted([int(x) for x in pd.to_numeric(df_skinny["Rank"], errors="coerce").dropna().unique().tolist()])
            rank_sel = st.multiselect("Priority Rank", options=rank_opts)

        with f3:
            fit_opts = sorted([str(s) for s in df_skinny["Fit"].dropna().unique().tolist() if str(s).strip()])
            fit_sel = st.multiselect("Vetting Class", options=fit_opts)

        with f4:
            st.write("") # Spacer
            only_action = st.checkbox("Action Required", help="Show only leads with pending drafts")

        # --- DATE RANGE SELECTION LOGIC ---
        # If a cohort is selected, we suggest its dates, otherwise default to 30 days
        if selected_cohort_name != "No Filter":
            sel_c = next(c for c in cohorts if c.name == selected_cohort_name)
            initial_start, initial_end = sel_c.start_date, sel_c.end_date
        else:
            initial_start = date.today() - timedelta(days=30)
            initial_end = date.today()

        dr_col1, dr_col2 = st.columns([3, 2])
        with dr_col1:
            # We use a key to persist the date selection across partial clicks
            date_range = st.date_input("Filter by Application Date", value=[initial_start, initial_end], key="master_date_range")
        with dr_col2:
            search = st.text_input("Global Search", placeholder="Name, ID, or Stage...", key="master_search")

        # --- APPLY ALL FILTERS ---
        df_view = df_skinny.copy()

        # 1. Cohort Filter (Strict Date Bound)
        if selected_cohort_name != "No Filter":
            c = next(coh for coh in cohorts if coh.name == selected_cohort_name)
            # start_dt, end_dt = pd.Timestamp(c.start_date), pd.Timestamp(c.end_date)
            df_view = df_view[(df_view["_applied_dt"].dt.date >= c.start_date) & (df_view["_applied_dt"].dt.date <= c.end_date)]

        # 2. Date Range Filter (Overrides/Refines Cohort)
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
            df_view = df_view[(df_view["_applied_dt"].dt.date >= start_date) & (df_view["_applied_dt"].dt.date <= end_date)]

        # 3. Categorical Filters
        if stage_sel: df_view = df_view[df_view["Stage"].isin(stage_sel)]
        if rank_sel: df_view = df_view[pd.to_numeric(df_view["Rank"], errors="coerce").isin(rank_sel)]
        if fit_sel: df_view = df_view[df_view["Fit"].isin(fit_sel)]
        if only_action: 
            df_view = df_view[df_view["Action"].notna() & (df_view["Action"] != "")]
        
        # 4. Search Filter
        if search and search.strip():
            s = search.strip().lower()

            df_view = df_view[
                df_view["Name"].astype(str).str.lower().str.contains(s, na=False, regex=False) |
                df_view["ID"].astype(str).str.lower().str.contains(s, na=False, regex=False) |
                df_view["Stage"].astype(str).str.lower().str.contains(s, na=False, regex=False)
            ]

        st.info(f"Displaying **{len(df_view)}** records matching current filters.")

        # --- RESULTS TABLE & DRAWER ---
        left, right = st.columns([2, 3], gap="large")

        with left:
            st.subheader("Lead Registry")
            # Using data_editor for better selection performance
            event = st.dataframe(
                df_view[["ID", "Name", "Stage", "Rank", "Score", "Date"]], 
                hide_index=True, 
                on_select="rerun", 
                selection_mode="single-row",
                width='stretch'
            )
            selected_id = None
            if event and event.selection and event.selection.rows:
                selected_id = df_view.iloc[event.selection.rows[0]]["ID"]

        with right:
            st.subheader("Inspection Drawer")
            if not selected_id:
                st.write("Please select a lead from the registry to inspect full details.")
            else:
                lead_data = df_all[df_all["lead_id"] == selected_id].iloc[0].to_dict()
                t1, t2, t3, t4, t5 = st.tabs(["Profile", "Vetting", "Documents", "Log", "System Data"])
                
                with t1:
                    st.write(f"**Full Name:** {lead_data.get('first_name')} {lead_data.get('middle_name','')} {lead_data.get('last_name')}")
                    st.write(f"**Email:** {lead_data.get('email')}")
                    st.write(f"**Phone:** {lead_data.get('phone')}")
                    st.write(f"**Applied On:** {lead_data.get('timestamp')}")
                    st.write(f"**Current Stage:** {lead_data.get('stage')}")
                
                with t2:
                    st.write(f"**Fit Classification:** {lead_data.get('fit_classification')}")
                    st.write(f"**Fit Score:** {lead_data.get('fit_score')}")
                    st.write(f"**Priority Rank:** {lead_data.get('priority_rank')}")
                    st.divider()
                    st.write(f"**Profession:** {lead_data.get('current_profession')}")
                    st.write(f"**Experience:** {lead_data.get('experience_years')}")
                    st.write(f"**Financial Input:** {lead_data.get('financial_readiness_input')}")

                with t3:
                    chk = lead_data.get('checklist_status', {})
                    if chk:
                        st.write("**KYC Checklist Status:**")
                        for item, status in chk.items():
                            st.write(f"{'✅' if status else '❌'} {item}")
                    else:
                        st.info("No documents have been tracked for this lead yet.")
                    
                    if lead_data.get('verified_financial_capital'):
                        st.success(f"**Verified Capital:** KES {lead_data.get('verified_financial_capital'):,.0f}")

                with t4:
                    # Render the COMPLETE activity history
                    history = lead_data.get('activity_log', [])
                    if history:
                        # Convert to DataFrame (handling Pydantic models or dicts)
                        log_entries = [e.dict() if hasattr(e, 'dict') else e for e in history]
                        log_df = pd.DataFrame(log_entries)
                        
                        # Ensure timestamp is readable and sorted newest first
                        log_df['timestamp'] = pd.to_datetime(log_df['timestamp'])
                        log_df = log_df.sort_values(by='timestamp', ascending=False)
                        
                        # Rename for clean headers
                        log_df.rename(columns={
                            "timestamp": "Time",
                            "author": "User",
                            "type": "Category",
                            "content": "Description",
                            "stage_snapshot": "Stage At Time"
                        }, inplace=True)

                        st.write(f"**Full Activity History ({len(log_df)} entries)**")
                        
                        # Display scrollable interactive dataframe
                        st.dataframe(
                            log_df[["Time", "User", "Category", "Description", "Stage At Time"]],
                            width='stretch',
                            hide_index=True,
                            column_config={
                                "Time": st.column_config.DatetimeColumn("Time", format="DD/MM/YY HH:mm"),
                                "Description": st.column_config.TextColumn("Description", width="large")
                            }
                        )
                    else:
                        st.info("No activity recorded for this lead yet.")

                with t5:
                    st.json(lead_data)