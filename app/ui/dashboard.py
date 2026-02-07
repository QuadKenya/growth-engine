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
                
                # st.markdown(f"""
                # <div class="log-box">
                #     <div class="log-meta">{icon} <b>{author}</b> • {ts_str}</div>
                #     <div class="log-content">{content}</div>
                # </div>
                # """, unsafe_allow_html=True)

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
    elif stage in ["FINANCIAL_ASSESSMENT", "ASSESSMENT_PSYCH", "SITE_SEARCH"]:
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
                    st.success(f"**Verified Cap:** KES {getattr(lead, 'verified_financial_capital')}")
                st.caption(f"Applied: {_safe_str(getattr(lead, 'timestamp', ''))}")

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
                        # REMOVED BALLOONS HERE
                        # st.toast("KYC Started!")
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
                        current_rows = getattr(lead.financial_data, "statement_rows", []) or []
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
                        initial_df["credit_amount"] = pd.to_numeric(initial_df["credit_amount"], errors="coerce").fillna(0.0)
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
                    note = st.text_input("Interview Notes", key=f"int_note_{lead.lead_id}")
                    if st.button("Log Result", key=f"log_int_{lead.lead_id}"):
                        workflow.log_interview_result(lead.lead_id, res, note)
                        st.rerun()

                # Gate 6: Site & Contract
                if stage == "SITE_SEARCH":
                    st.info("Candidate searching for site...")
                    if st.button("Site Found / Vetting Req", key=f"sf_{lead.lead_id}"):
                        lead.stage = "SITE_VETTING"
                        db.upsert_lead(lead)
                        st.rerun()
                
                if stage == "SITE_VETTING":
                    score = st.slider("Site Score", 0, 100, 70, key=f"ss_{lead.lead_id}")
                    if st.button("Finalize Site", key=f"fs_{lead.lead_id}"):
                        workflow.finalize_site_vetting(lead.lead_id, score)
                        st.rerun()

                if stage == "CONTRACTING":
                    # 1. Check if we should show the celebration from a previous click
                    if st.session_state.get(f"show_balloons_{lead.lead_id}"):
                        st.balloons()
                        st.toast("Lead Contracted!")
                        # Clear the flag so they don't loop forever
                        st.session_state[f"show_balloons_{lead.lead_id}"] = False

                    st.success("Contract Generated!")
                    if st.button("🎉 Close Contract", key=f"cc_{lead.lead_id}", width="stretch"):
                        workflow.close_contract(lead.lead_id)
                        
                        # 2. Set the flag in session state instead of calling balloons directly
                        st.session_state[f"show_balloons_{lead.lead_id}"] = True
                        st.rerun()
                
                if stage == "CONTRACT_CLOSED":
                    st.success("Franchisee Onboarded")

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
        "🔍 Master Database"
    ],
    key="view_mode",
    )

    st.divider()
    
    # Simulation Lab
    with st.expander("🧪 Simulation Lab"):
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
            
            if st.form_submit_button("🚀 Inject Lead"):
                # Use entered email or fallback to timestamp if empty (safety net)
                final_email = email if email else f"test_{int(time.time())}@gmail.com"
                
                payload = {
                    "lead_id": final_email, 
                    "email": final_email, 
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
                st.toast("Injected!")
                time.sleep(1)
                st.rerun()
                
    st.divider()
    if st.button("🗑️ Reset Database"):
        reset_database()

# --- MAIN DASHBOARD LOGIC ---
leads = db.fetch_all_leads()

# Filter Helpers
def get_leads_by_stage(stages):
    return [l for l in leads if getattr(l, "stage", "") in stages]

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
    targets = get_leads_by_stage(["SITE_SEARCH", "SITE_VETTING", "CONTRACTING"])
    if not targets: st.info("No pending contracts.")
    for l in targets: render_lead_card(l)

elif view_mode == "✅ Contracted / Alumni":
    st.header("Contracted Franchisees")
    targets = get_leads_by_stage(["CONTRACT_CLOSED"])
    if not targets: st.info("No contracted leads yet.")
    for l in targets: render_lead_card(l)

elif view_mode == "🔍 Master Database":
    st.header("Master Database")
    st.caption("Search + filters on the left, inspect the full record on the right.")

    if not leads:
        st.info("No leads yet.")
    else:
        # Full dataset (ALL fields)
        df_all = pd.DataFrame([l.dict() for l in leads])

        # Ensure safe existence of common columns used in filters/table
        for col in [
            "lead_id",
            "first_name",
            "last_name",
            "stage",
            "priority_rank",
            "fit_score",
            "fit_classification",
            "timestamp",
            "draft_message",
            "notes"
        ]:
            if col not in df_all.columns:
                df_all[col] = None

        # Name field
        df_all["Name"] = (
            df_all["first_name"].fillna("").astype(str).str.strip()
            + " "
            + df_all["last_name"].fillna("").astype(str).str.strip()
        ).str.strip()

        # Parse timestamps for date filter (tolerant)
        df_all["_applied_dt"] = pd.to_datetime(df_all["timestamp"], errors="coerce")

        # Skinny view (for filtering + table)
        df_skinny = df_all[
            ["lead_id", "Name", "stage", "priority_rank", "fit_score", "fit_classification", "timestamp", "_applied_dt", "draft_message", "notes"]
        ].copy()

        df_skinny.rename(
            columns={
                "lead_id": "ID",
                "stage": "Stage",
                "priority_rank": "Rank",
                "fit_score": "Score",
                "fit_classification": "Fit Classification",
                "timestamp": "Date",
                "draft_message": "Draft Message",
                "notes": "Internal Notes"
            },
            inplace=True,
        )

        # --- CLEAN FILTERS ROW ---
        st.subheader("Filters")
        f1, f2, f3, f4, f5 = st.columns([2, 2, 2, 3, 2])

        with f1:
            stage_opts = sorted(
                [s for s in df_skinny["Stage"].dropna().astype(str).unique().tolist() if str(s).strip()]
            )
            stage_sel = st.multiselect("Stage", options=stage_opts, default=[])

        with f2:
            rank_numeric = pd.to_numeric(df_skinny["Rank"], errors="coerce")
            rank_opts = sorted([int(x) for x in rank_numeric.dropna().unique().tolist()])
            rank_sel = st.multiselect("Rank", options=rank_opts, default=[])

        with f3:
            fit_opts = sorted(
                [s for s in df_skinny["Fit Classification"].dropna().astype(str).unique().tolist() if str(s).strip()]
            )
            fit_sel = st.multiselect("Fit", options=fit_opts, default=[])

        with f4:
            applied_dt = df_skinny["_applied_dt"]
            dt_min = applied_dt.min()
            dt_max = applied_dt.max()
            today = date.today()

            if pd.notna(dt_max):
                default_end = dt_max.date()
                default_start = (dt_max - pd.Timedelta(days=30)).date()
            else:
                default_end = today
                default_start = today - timedelta(days=30)

            min_date = dt_min.date() if pd.notna(dt_min) else (today - timedelta(days=365))
            max_date = dt_max.date() if pd.notna(dt_max) else today

            date_range = st.date_input(
                "Applied date range",
                value=[max(default_start, min_date), min(default_end, max_date)],
                min_value=min_date,
                max_value=max_date,
            )

        with f5:
            only_action = st.checkbox("Action required", value=False, help="Only show leads with a draft pending review.")

        include_missing_dates = st.checkbox("Include leads with missing/invalid dates", value=True)

        search = st.text_input("Search (Name, ID, Stage)", "")

        # Apply filters to df_view
        df_view = df_skinny.copy()

        if stage_sel:
            df_view = df_view[df_view["Stage"].isin(stage_sel)]

        if rank_sel:
            df_view = df_view[pd.to_numeric(df_view["Rank"], errors="coerce").isin(rank_sel)]

        if fit_sel:
            df_view = df_view[df_view["Fit Classification"].astype(str).isin(fit_sel)]

        if only_action:
            df_view = df_view[df_view["Draft Message"].notna() & (df_view["Draft Message"].astype(str).str.strip() != "")]

        start_date, end_date = _normalize_date_range(date_range)
        start_dt = pd.Timestamp(datetime.combine(start_date, dt_time.min))
        end_dt = pd.Timestamp(datetime.combine(end_date, dt_time.max))

        if include_missing_dates:
            mask = df_view["_applied_dt"].isna() | ((df_view["_applied_dt"] >= start_dt) & (df_view["_applied_dt"] <= end_dt))
            df_view = df_view[mask]
        else:
            df_view = df_view[df_view["_applied_dt"].notna()]
            df_view = df_view[(df_view["_applied_dt"] >= start_dt) & (df_view["_applied_dt"] <= end_dt)]

        if search.strip():
            s = search.strip()
            df_view = df_view[
                df_view["Name"].str.contains(s, case=False, na=False)
                | df_view["ID"].astype(str).str.contains(s, case=False, na=False)
                | df_view["Stage"].astype(str).str.contains(s, case=False, na=False)
            ]

        st.caption(f"Showing **{len(df_view)}** leads (out of {len(df_skinny)} total).")

        df_table = df_view[["ID", "Name", "Stage", "Rank", "Score", "Date", "Internal Notes"]].reset_index(drop=True)

        def kv_df(d: dict) -> pd.DataFrame:
            def to_cell(v):
                if v is None:
                    return ""
                if isinstance(v, (dict, list)):
                    return json.dumps(v, ensure_ascii=False, default=str)
                return str(v)

            return pd.DataFrame({"Field": list(d.keys()), "Value": [to_cell(d[k]) for k in d.keys()]})

        def filter_existing(keys, all_keys):
            return [k for k in keys if k in all_keys]

        left, right = st.columns([2, 3], gap="large")

        with left:
            st.subheader("Leads")
            st.caption("Select a row to view full details →")
            selected_id = None
            try:
                event = st.dataframe(
                    df_table,
                    width="stretch",
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                )
                if event and event.selection and event.selection.rows:
                    row_idx = event.selection.rows[0]
                    selected_id = df_table.iloc[row_idx]["ID"]
            except TypeError:
                if len(df_table):
                    selected_id = st.selectbox("Select a lead", df_table["ID"].tolist(), index=0)
                else:
                    st.info("No matches for your filters/search.")

        with right:
            st.subheader("Detail Drawer")

            if not selected_id:
                st.info("Select a lead from the table to view full details.")
            else:
                full_row = df_all[df_all["lead_id"] == selected_id]
                if full_row.empty:
                    st.warning("Selected lead not found.")
                else:
                    record = full_row.iloc[0].to_dict()
                    all_keys = set(record.keys())

                    core_keys = filter_existing(
                        [
                            "lead_id",
                            "first_name",
                            "last_name",
                            "Name",
                            "stage",
                            "priority_rank",
                            "timestamp",
                            "wake_up_date",
                            "soft_rejection_reason",
                        ],
                        all_keys,
                    )
                    fit_keys = filter_existing(
                        [
                            "fit_score",
                            "fit_classification",
                            "financial_readiness_input",
                            "location_status_input",
                            "experience_years",
                            "has_business_exp",
                        ],
                        all_keys,
                    )
                    contact_keys = filter_existing(
                        ["email", "phone", "location_county_input", "current_profession"],
                        all_keys,
                    )
                    kyc_keys = filter_existing(
                        ["checklist_status", "kyc_status", "kyb_status", "documents_received"],
                        all_keys,
                    )
                    meta_keys = filter_existing(
                        ["draft_message", "notes", "raw_payload", "source", "created_at", "updated_at"],
                        all_keys,
                    )

                    covered = set(core_keys + fit_keys + contact_keys + kyc_keys + meta_keys)
                    extras = [k for k in record.keys() if k not in covered]
                    meta_keys = meta_keys + extras

                    tabs = st.tabs(["Core", "Fit", "Contact", "KYC", "Metadata", "Raw JSON"])

                    with tabs[0]:
                        st.dataframe(kv_df({k: record.get(k) for k in core_keys}), width="stretch", hide_index=True)

                    with tabs[1]:
                        st.dataframe(kv_df({k: record.get(k) for k in fit_keys}), width="stretch", hide_index=True)

                    with tabs[2]:
                        st.dataframe(kv_df({k: record.get(k) for k in contact_keys}), width="stretch", hide_index=True)

                    with tabs[3]:
                        # NEW: Enhanced KYC View
                        checklist = record.get("checklist_status", {})
                        if checklist:
                            st.subheader("Checklist Details")
                            df_chk = pd.DataFrame({
                                "Document": list(checklist.keys()),
                                "Status": ["✅ Received" if v else "❌ Pending" for v in checklist.values()]
                            })
                            st.dataframe(df_chk, width='stretch', hide_index=True)
                        else:
                            st.info("No checklist active.")
                        
                        # Show non-checklist KYC fields below
                        st.divider()
                        st.dataframe(kv_df({k: record.get(k) for k in kyc_keys if k != "checklist_status"}), width='stretch', hide_index=True)

                    with tabs[4]:
                        st.dataframe(kv_df({k: record.get(k) for k in meta_keys}), width="stretch", hide_index=True)

                    with tabs[5]:
                        st.json(record)