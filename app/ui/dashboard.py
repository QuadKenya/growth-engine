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

from app.db.supabase import db
from app.services.workflow_service import workflow


# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Access Afya | Growth Engine",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CUSTOM CSS (Theme-aware: light + dark mode friendly) ---
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

  .lead-card h1, .lead-card h2, .lead-card h3, .lead-card p, .lead-card span, .lead-card div {
    color: var(--text) !important;
  }

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

  div[data-testid="stMetric"] {
    background: var(--card-bg) !important;
    color: var(--text) !important;
    padding: 15px;
    border-radius: 8px;
    border: 1px solid var(--border);
    box-shadow: 0 1px 3px rgba(0,0,0,0.10);
  }

  div[data-testid="stDataFrame"] {
    background: var(--card-bg) !important;
    border-radius: 10px;
    border: 1px solid var(--border);
  }

  .aa-logo-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 6px 0 14px 0;
    margin: 0;
  }
  .aa-logo {
    width: 200px;
    max-width: 200px;
    height: auto;
    display: block;
  }
</style>
""",
    unsafe_allow_html=True,
)

# --- LOGO (Local asset; reliable + deploy-safe) ---
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "access_afya_logo.png"
if not LOGO_PATH.exists():
    LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "access_afya_logo.png"


def render_sidebar_logo(path: Path):
    if not path.exists():
        st.warning(f"Logo missing. Expected at: {path}")
        return
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <div class="aa-logo-wrap">
          <img class="aa-logo" src="data:image/png;base64,{b64}" alt="Access Afya logo"/>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- HELPER: RESET DB (as in original V2) ---
def reset_database():
    file_path = os.path.join(os.path.dirname(__file__), "../../data/local_db.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([], f)
    st.toast("Database Wiped Clean!", icon="🧹")
    time.sleep(1)
    st.rerun()


def _safe_str(x) -> str:
    if x is None:
        return ""
    return str(x)


def _normalize_date_range(dr):
    """
    Streamlit date_input may return date, tuple(date,date), or list[date].
    Normalize to (start_date, end_date) as date objects.
    """
    if isinstance(dr, (list, tuple)):
        if len(dr) == 2:
            return dr[0], dr[1]
        if len(dr) == 1:
            return dr[0], dr[0]
        today = date.today()
        return today, today
    return dr, dr


# --- HELPER: RENDER LEAD CARD (standard UX for pipeline tabs) ---
def render_lead_card(lead):
    css_class = "lead-card"
    badge_html = f'<span class="status-badge status-new">{_safe_str(getattr(lead, "stage", ""))}</span>'

    if getattr(lead, "priority_rank", None) == 1:
        css_class += " hot"
        badge_html = '<span class="status-badge status-hot">🔥 Rank 1: Site Ready</span>'
    elif getattr(lead, "priority_rank", None) == 2:
        badge_html = '<span class="status-badge status-warm">💰 Rank 2: Cash Ready</span>'
    elif getattr(lead, "stage", None) == "WARM_LEAD":
        css_class += " warm"
        badge_html = '<span class="status-badge status-warm">🌤️ Nurture</span>'
    elif getattr(lead, "stage", None) == "KYC_SCREENING":
        css_class += " compliance"
        badge_html = '<span class="status-badge status-success">📂 Compliance</span>'

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
            # Added a 4th column specifically for Notes
            col_data, col_draft, col_actions, col_notes = st.columns([1, 2, 1, 1], gap="small")

            with col_data:
                st.caption("CANDIDATE PROFILE")
                st.write(f"**Role:** {_safe_str(getattr(lead, 'current_profession', ''))}")
                st.write(f"**Exp:** {_safe_str(getattr(lead, 'experience_years', ''))}")
                st.write(f"**Loc:** {_safe_str(getattr(lead, 'location_county_input', ''))}")
                st.write(f"**Fin:** {_safe_str(getattr(lead, 'financial_readiness_input', ''))}")
                st.write(f"**Stage:** {_safe_str(getattr(lead, 'stage', ''))}")
                
                # Show Rejection/Nurture reason if applicable
                if getattr(lead, "stage", "") == "WARM_LEAD":
                     st.write(f"**Reason:** {_safe_str(getattr(lead, 'soft_rejection_reason', ''))}")
                     st.write(f"**Wake Up:** {_safe_str(getattr(lead, 'wake_up_date', ''))}")

                st.caption(f"Applied: {_safe_str(getattr(lead, 'timestamp', ''))}")

            with col_draft:
                st.caption("🤖 AGENT WORKSPACE")

                if getattr(lead, "draft_message", None):
                    st.info("Draft Pending Review")
                    txt = st.text_area(
                        "Edit Message:",
                        value=_safe_str(getattr(lead, "draft_message", "")),
                        height=120,
                        key=f"d_{getattr(lead,'lead_id','')}",
                    )

                    c_save, c_send = st.columns(2)
                    if c_save.button("💾 Save Draft", key=f"save_{getattr(lead,'lead_id','')}", use_container_width=True):
                        if hasattr(workflow, "update_draft"):
                            workflow.update_draft(lead.lead_id, txt)
                        else:
                            lead.draft_message = txt
                            db.upsert_lead(lead)
                        st.toast("Draft saved")
                        time.sleep(0.2)
                        st.rerun()

                    if c_send.button("✅ Approve & Send", key=f"s_{getattr(lead,'lead_id','')}", use_container_width=True):
                        try:
                            workflow.approve_draft(lead.lead_id, message_override=txt) 
                        except TypeError:
                            if hasattr(workflow, "update_draft"):
                                workflow.update_draft(lead.lead_id, txt)
                            else:
                                lead.draft_message = txt
                                db.upsert_lead(lead)
                            workflow.approve_draft(lead.lead_id)

                        st.balloons()
                        time.sleep(0.8)
                        st.rerun()

                elif getattr(lead, "stage", None) == "INTEREST_CHECK_SENT":
                    st.warning("Waiting for Reply...")
                    b1, b2 = st.columns(2)
                    if b1.button("Replied YES", key=f"y_{getattr(lead,'lead_id','')}"):
                        workflow.handle_interest_response(lead.lead_id, "YES")
                        st.rerun()
                    if b2.button("Replied LATER", key=f"m_{getattr(lead,'lead_id','')}"):
                        workflow.handle_interest_response(lead.lead_id, "MAYBE")
                        st.rerun()

                elif getattr(lead, "stage", None) == "KYC_SCREENING":
                    st.success("Proposal Approved")
                    items = getattr(lead, "checklist_status", None) or {}
                    total = len(items)

                    if total == 0:
                        st.info("No checklist configured.")
                    else:
                        completed = sum(1 for v in items.values() if v)
                        st.progress(completed / total)
                        missing_docs = [k for k, v in items.items() if not v]
                        st.write(f"**Pending Docs:** {len(missing_docs)}")

                        with st.popover("Open Checklist"):
                            for item, status in items.items():
                                chk = st.checkbox(item, value=status, key=f"{getattr(lead,'lead_id','')}_{item}")
                                if chk != status:
                                    workflow.update_checklist(lead.lead_id, item, chk)
                                    st.rerun()
                else:
                    st.info("No active draft.")

            with col_actions:
                st.caption("MANUAL ACTIONS")

                # Show Move to Warm unless already there or Rejected
                if getattr(lead, "stage", "") not in ["WARM_LEAD", "TURNED_DOWN", "NO_FIT"]:
                    if st.button("🌤️ Move to Warm", key=f"w_{getattr(lead,'lead_id','')}", use_container_width=True):
                        if hasattr(workflow, "move_to_warm"):
                            workflow.move_to_warm(lead.lead_id)
                        else:
                            lead.stage = "WARM_LEAD"
                            lead.draft_message = None
                            db.upsert_lead(lead)
                        st.rerun()

                if getattr(lead, "stage", "") not in ["TURNED_DOWN", "NO_FIT"]:
                    if st.button("❌ Hard Reject", key=f"r_{getattr(lead,'lead_id','')}", use_container_width=True):
                        reason = st.text_input("Rejection reason", key=f"rej_reason_{getattr(lead,'lead_id','')}") # Reason input inside card is tricky w/ rerun, simplified for now
                        if hasattr(workflow, "hard_reject"):
                            workflow.hard_reject(lead.lead_id)
                        else:
                            lead.stage = "TURNED_DOWN"
                            lead.draft_message = None
                            db.upsert_lead(lead)
                        st.rerun()
                
                # If Warm, maybe Reactivate?
                if getattr(lead, "stage", "") == "WARM_LEAD":
                    if st.button("♻️ Reactivate", key=f"re_{getattr(lead,'lead_id','')}", use_container_width=True):
                        lead.stage = "EXPRESSED_INTEREST" # Reset to start of funnel validation
                        db.upsert_lead(lead)
                        st.rerun()

            # --- NEW: NOTES SECTION ---
            with col_notes:
                st.caption("📝 NOTES")
                current_notes = getattr(lead, "notes", "") or ""
                new_notes = st.text_area(
                    "Associate Notes", 
                    value=current_notes, 
                    height=120,
                    key=f"notes_{getattr(lead,'lead_id','')}",
                    help="Internal notes. Click Save to persist."
                )
                if st.button("💾 Save Note", key=f"btn_note_{getattr(lead,'lead_id','')}", use_container_width=True):
                    lead.notes = new_notes
                    db.upsert_lead(lead)
                    st.toast("Note saved successfully!")
                    time.sleep(0.5)
                    st.rerun()


# --- SIDEBAR NAVIGATION + SIMULATION LAB ---
with st.sidebar:
    render_sidebar_logo(LOGO_PATH)

    st.title("Growth Engine")

    view_mode = st.radio(
        "Pipeline Views",
        [
            "📥 Inbox (New Leads)",
            "🔥 Hot Leads (Action Required)",
            "🌤️ Warm Leads (Nurture)",
            "💬 Engagement (Screening)",
            "📂 Compliance (KYC/KYB)",
            "🔍 Master Database",
        ],
    )

    st.divider()

    with st.expander("🧪 Simulation Lab"):
        with st.form("sim_ingest"):
            st.caption("Inject Test Candidate")
            email = st.text_input("Email", f"test_{int(time.time())}@gmail.com")

            c1, c2 = st.columns(2)
            fname = c1.text_input("First Name", "Jane")
            lname = c2.text_input("Last Name", "Doe")

            prof = st.selectbox("Role", ["Clinical Officer", "Nurse", "Shopkeeper", "Medical Doctor"])

            c3, c4 = st.columns(2)
            exp = c3.selectbox("Exp", ["3-4+ Years", "1-2 Years", "None"])
            biz_exp = c4.selectbox("Biz Exp?", ["Yes", "No"])

            fin = st.selectbox("Finance", ["I have adequate resources", "I need a loan"])
            
            # FIXED: Added County Selector
            # Using a simplified list for simulation
            counties = ["Nairobi", "Mombasa", "Kiambu", "Nakuru", "Kajiado", "Marsabit", "London (Invalid)"]
            county = st.selectbox("County", counties)
            
            loc_status = st.selectbox(
                "Location Status",
                ["Yes, I own or lease a location", "No, but I have found ideal locations", "No"],
            )

            if st.form_submit_button("🚀 Inject Lead"):
                payload = {
                    "lead_id": email,
                    "email": email,
                    "first_name": fname,
                    "last_name": lname,
                    "phone": "0700000000",
                    "current_profession": prof,
                    "experience_years": exp,
                    "has_business_exp": biz_exp,
                    "financial_readiness_input": fin,
                    "location_county_input": county, # FIXED: Using selected county
                    "location_status_input": loc_status,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                workflow.process_incoming_lead(payload)
                st.toast("Candidate Injected Successfully!")
                time.sleep(1)
                st.rerun()

    st.divider()

    if st.button("🗑️ Reset Database"):
        reset_database()


# --- MAIN DASHBOARD LOGIC ---
leads = db.fetch_all_leads()

# Metrics Bar (Always Visible)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Pipeline", len(leads))
m2.metric("🔥 Action Required", len([l for l in leads if getattr(l, "draft_message", None)]))
m3.metric("🌤️ Warm / Nurture", len([l for l in leads if getattr(l, "stage", None) == "WARM_LEAD"]))
m4.metric("✅ Contracted", len([l for l in leads if getattr(l, "stage", None) == "CONTRACT_CLOSED"]))

st.divider()

if view_mode == "📥 Inbox (New Leads)":
    st.header("Inbox: New Leads")
    st.caption("Candidates vetted by the Agent awaiting your approval.")

    inbox = [
        l
        for l in leads
        if getattr(l, "draft_message", None)
        and getattr(l, "stage", None) in ["EXPRESSED_INTEREST", "POTENTIAL_FIT", "NO_FIT"]
    ]
    if not inbox:
        st.success("Inbox Zero! Great job. 🧘")
    for l in inbox:
        render_lead_card(l)

elif view_mode == "🔥 Hot Leads (Action Required)":
    st.header("Prioritized Call List")
    st.caption("Rank 1 (Site Ready) & Rank 2 (Cash Ready) candidates.")

    # Filter for active stages AND exclude Inbox stages to avoid duplicates if draft exists
    hot = [l for l in leads if getattr(l, "stage", None) in ["READY_FOR_CALL", "FAQ_SENT", "INTEREST_CHECK_SENT"]]
    hot.sort(key=lambda x: getattr(x, "priority_rank", 9999))
    
    if not hot:
        st.info("No hot leads pending calls.")
    for l in hot:
        render_lead_card(l)

elif view_mode == "🌤️ Warm Leads (Nurture)":
    st.header("Warm Leads Nurture List")
    st.caption("Candidates PARKED for future cohorts.")

    warm = [l for l in leads if getattr(l, "stage", None) == "WARM_LEAD"]

    if not warm:
        st.info("No Warm Leads.")
    else:
        # FIXED: Switched from Dataframe to Card View
        for l in warm:
            render_lead_card(l)

elif view_mode == "💬 Engagement (Screening)":
    st.header("Engagement & Screening")
    st.caption("Leads currently reviewing FAQs or timelines.")
    engaged = [l for l in leads if getattr(l, "stage", None) in ["FAQ_SENT"]]
    if not engaged:
        st.info("No leads currently in engagement.")
    for l in engaged:
        render_lead_card(l)

elif view_mode == "📂 Compliance (KYC/KYB)":
    st.header("Compliance")
    compliance = [l for l in leads if getattr(l, "stage", None) == "KYC_SCREENING"]
    if not compliance:
        st.info("No candidates in compliance stage.")
    for l in compliance:
        render_lead_card(l)

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
                    use_container_width=True,
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
                        st.dataframe(kv_df({k: record.get(k) for k in core_keys}), use_container_width=True, hide_index=True)

                    with tabs[1]:
                        st.dataframe(kv_df({k: record.get(k) for k in fit_keys}), use_container_width=True, hide_index=True)

                    with tabs[2]:
                        st.dataframe(kv_df({k: record.get(k) for k in contact_keys}), use_container_width=True, hide_index=True)

                    with tabs[3]:
                        st.dataframe(kv_df({k: record.get(k) for k in kyc_keys}), use_container_width=True, hide_index=True)

                    with tabs[4]:
                        st.dataframe(kv_df({k: record.get(k) for k in meta_keys}), use_container_width=True, hide_index=True)

                    with tabs[5]:
                        st.json(record)