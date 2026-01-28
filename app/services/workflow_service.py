from datetime import datetime, timedelta
import json
import os
from app.core.config import settings
from app.db.supabase import db
from app.models.domain import Lead, PipelineStage, ActivityLogEntry, ActivityType
from app.services.scoring_service import scorer
from app.services.drafting_service import drafter

class WorkflowService:
    def __init__(self):
        # Load Checklist Definitions
        checklist_path = os.path.join(settings.BASE_DIR, "config", "checklists.json")
        with open(checklist_path, "r") as f:
            self.checklists = json.load(f)

    # --- HELPER: AUDIT LOGGING ---
    def log_activity(self, lead: Lead, content: str, type: ActivityType = ActivityType.SYSTEM, author: str = "System"):
        """Appends an entry to the lead's activity log."""
        entry = ActivityLogEntry(
            timestamp=datetime.now(),
            author=author,
            type=type,
            content=content,
            stage_snapshot=lead.stage
        )
        if lead.activity_log is None:
            lead.activity_log = []
        lead.activity_log.append(entry)

    # --- GATE 1: INGESTION ---
    def process_incoming_lead(self, raw_data: dict) -> Lead:
        lead = Lead(**raw_data)
        self.log_activity(lead, "Lead captured via Google Form.", ActivityType.SYSTEM)
        
        # 1. Hard Gates
        gate_check = scorer.check_hard_gates(lead)
        if not gate_check["passed"]:
            lead.stage = PipelineStage.NO_FIT
            lead.rejection_type = "Hard"
            lead.notes = gate_check["reason"] # Legacy field
            lead.draft_message = drafter.generate_draft(lead, "hard_rejection")
            self.log_activity(lead, f"Hard Rejection: {gate_check['reason']}", ActivityType.TRANSITION)
            return db.upsert_lead(lead)

        # 2. Score
        score_res = scorer.calculate_score(lead)
        lead.fit_score = score_res["score"]
        lead.fit_classification = scorer.classify_score(lead.fit_score)
        
        # 3. Soft Gate / Warm Lead Check
        if lead.fit_classification == "Not A Fit":
            soft_check = scorer.is_soft_rejection(lead)
            if soft_check["is_soft"]:
                lead.stage = PipelineStage.WARM_LEAD
                lead.rejection_type = "Soft"
                lead.soft_rejection_reason = soft_check["reason"]
                
                days = 365 if soft_check["reason"] == "experience" else 90
                lead.wake_up_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
                lead.draft_message = drafter.generate_draft(lead, f"soft_rejection_{soft_check['reason']}")
                self.log_activity(lead, f"Soft Rejection ({soft_check['reason']}). Moved to Warm Leads.", ActivityType.TRANSITION)
            else:
                lead.stage = PipelineStage.NO_FIT
                lead.rejection_type = "Hard"
                lead.notes = "Low Score (Non-Specific)"
                lead.draft_message = drafter.generate_draft(lead, "hard_rejection")
                self.log_activity(lead, "Low Score. Hard Rejection.", ActivityType.TRANSITION)
            return db.upsert_lead(lead)

        # 4. Priority Ranking (Passed Gates)
        lead.priority_rank = scorer.determine_priority(lead)
        lead.stage = PipelineStage.POTENTIAL_FIT
        self.log_activity(lead, f"Vetting Passed. Rank {lead.priority_rank} ({lead.fit_classification}).", ActivityType.TRANSITION)
        
        # 5. Draft Interest Check
        if lead.priority_rank == 1:
            lead.draft_message = drafter.generate_draft(lead, "invite_to_call_priority")
        else:
            lead.draft_message = drafter.generate_draft(lead, "interest_check")
            
        return db.upsert_lead(lead)

    # --- GATE 2/3: ENGAGEMENT ---
    def approve_draft(self, lead_id: str, message_override: str = None):
        """Human clicked 'Approve'."""
        lead = db.get_lead(lead_id)
        if not lead: return

        # Update draft if edited
        final_msg = message_override if message_override else lead.draft_message
        
        # Transition Logic
        if lead.stage == PipelineStage.POTENTIAL_FIT:
             lead.stage = PipelineStage.INTEREST_CHECK_SENT
        elif lead.stage == PipelineStage.FAQ_SENT:
             lead.stage = PipelineStage.READY_FOR_CALL
        
        lead.draft_message = None
        lead.last_contact_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.log_activity(lead, "Message Approved & Sent.", ActivityType.EMAIL)
        db.upsert_lead(lead)

    def handle_interest_response(self, lead_id: str, response: str):
        lead = db.get_lead(lead_id)
        if response == "YES":
            lead.stage = PipelineStage.FAQ_SENT
            lead.draft_message = drafter.generate_draft(lead, "faq_screen")
            self.log_activity(lead, "Lead Replied YES. Sending FAQs.", ActivityType.ACTION)
        elif response == "MAYBE":
            lead.stage = PipelineStage.WARM_LEAD
            lead.soft_rejection_reason = "Lead requested delay"
            lead.wake_up_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
            self.log_activity(lead, "Lead Replied MAYBE. Moved to Warm Leads.", ActivityType.TRANSITION)
        elif response == "NO":
            lead.stage = PipelineStage.TURNED_DOWN
            self.log_activity(lead, "Lead Replied NO. Turned Down.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    def add_note(self, lead_id: str, content: str):
        """Manual note by Associate."""
        lead = db.get_lead(lead_id)
        # We append to activity log, but also update legacy 'notes' field for quick view
        lead.notes = content 
        self.log_activity(lead, content, ActivityType.NOTE, author="Associate")
        db.upsert_lead(lead)

    # --- GATE 4: COMPLIANCE ---
    def initialize_checklist(self, lead_id: str, type_override: str = None):
        """Start KYC/KYB."""
        lead = db.get_lead(lead_id)
        
        # Determine List Type
        if type_override:
            list_key = type_override
        else:
            is_clinic = lead.facility_meta.get("is_clinic_owner") == "Yes"
            list_key = "KYB_Clinic_Conversion" if is_clinic else "KYC_Individual"
        
        items = self.checklists.get(list_key, [])
        lead.checklist_type = list_key
        lead.checklist_status = {item: False for item in items}
        lead.stage = PipelineStage.KYC_SCREENING
        
        self.log_activity(lead, f"Started Compliance ({list_key}).", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    def update_checklist(self, lead_id: str, item: str, checked: bool):
        lead = db.get_lead(lead_id)
        if item in lead.checklist_status:
            lead.checklist_status[item] = checked
            # Check if all done
            if all(lead.checklist_status.values()):
                lead.stage = PipelineStage.FINANCIAL_ASSESSMENT
                self.log_activity(lead, "All Docs Received. Moved to Financial Assessment.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    def submit_financial_assessment(self, lead_id: str, amount: float):
        """Gate 4 Decision."""
        lead = db.get_lead(lead_id)
        lead.verified_financial_capital = amount
        
        # Logic: 80k threshold
        if amount >= 80000:
            lead.stage = PipelineStage.ASSESSMENT_PSYCH
            self.log_activity(lead, f"Financials Verified ({amount}). Moved to Psychometrics.", ActivityType.TRANSITION)
        else:
            # AUTO-TRANSITION: Move to Warm Leads immediately
            lead.stage = PipelineStage.WARM_LEAD
            lead.rejection_type= "Soft"
            lead.soft_rejection_reason = f"Insufficient Verified Capital (KES {amount})"
            # Set Nurture Timer (e.g., 3 Months to save up)
            lead.wake_up_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
            
            self.log_activity(lead, f"Financials Failed ({amount} < 80k). Moved to Warm Leads.", ActivityType.TRANSITION)
            
        db.upsert_lead(lead)

    # --- GATE 5: ASSESSMENT ---
    def log_interview_result(self, lead_id: str, result: str, notes: str):
        lead = db.get_lead(lead_id)
        lead.interview_notes = notes
        
        if result == "PASS":
            lead.stage = PipelineStage.SITE_SEARCH
            self.log_activity(lead, "Interview Passed. Moved to Site Search.", ActivityType.TRANSITION)
        else:
            lead.stage = PipelineStage.TURNED_DOWN
            self.log_activity(lead, "Interview Failed. Turned Down.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    # --- GATE 6: SITE & CONTRACT ---
    def finalize_site_vetting(self, lead_id: str, score: float):
        lead = db.get_lead(lead_id)
        lead.site_visit_score = score
        if score >= 80: # Passing score
            lead.stage = PipelineStage.CONTRACTING
            lead.contract_generated_date = datetime.now().strftime("%Y-%m-%d")
            self.log_activity(lead, f"Site Approved (Score {score}). Contract Generated.", ActivityType.TRANSITION)
        else:
            self.log_activity(lead, f"Site Rejected (Score {score}). Search continues.", ActivityType.ACTION)
        db.upsert_lead(lead)

    def close_contract(self, lead_id: str):
        lead = db.get_lead(lead_id)
        lead.stage = PipelineStage.CONTRACT_CLOSED
        self.log_activity(lead, "Contract Signed! New Franchisee Onboarded.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    # --- MANUAL UTILS ---
    def move_to_warm(self, lead_id: str):
        lead = db.get_lead(lead_id)
        lead.stage = PipelineStage.WARM_LEAD
        lead.wake_up_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        lead.draft_message = None
        self.log_activity(lead, "Manually moved to Warm Leads.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    def hard_reject(self, lead_id: str, reason: str = None):
        lead = db.get_lead(lead_id)
        lead.stage = PipelineStage.TURNED_DOWN
        lead.draft_message = None
        if reason: lead.notes = reason
        self.log_activity(lead, f"Manually Rejected. Reason: {reason}", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    # NEW: Update draft helper (was missing from previous file dump but used in dashboard)
    def update_draft(self, lead_id: str, new_text: str):
        lead = db.get_lead(lead_id)
        lead.draft_message = new_text
        db.upsert_lead(lead)

workflow = WorkflowService()