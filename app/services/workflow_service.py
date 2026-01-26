from datetime import datetime, timedelta
import json
import os
from app.core.config import settings
from app.db.supabase import db
from app.models.domain import Lead, PipelineStage
from app.services.scoring_service import scorer
from app.services.drafting_service import drafter

class WorkflowService:
    def __init__(self):
        # Load Checklist Definitions
        checklist_path = os.path.join(settings.BASE_DIR, "config", "checklists.json")
        with open(checklist_path, "r") as f:
            self.checklists = json.load(f)

    def process_incoming_lead(self, raw_data: dict) -> Lead:
        lead = Lead(**raw_data)
        
        # 1. Hard Gates
        gate_check = scorer.check_hard_gates(lead)
        if not gate_check["passed"]:
            lead.stage = PipelineStage.NO_FIT
            lead.rejection_type = "Hard"
            lead.notes = gate_check["reason"]
            lead.draft_message = drafter.generate_draft(lead, "hard_rejection")
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
                # Set Wake Up Date (+1 Year for Exp, +3 Mo for others)
                days = 365 if soft_check["reason"] == "experience" else 90
                lead.wake_up_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
                lead.draft_message = drafter.generate_draft(lead, f"soft_rejection_{soft_check['reason']}")
            else:
                lead.stage = PipelineStage.NO_FIT
                lead.rejection_type = "Hard"
                lead.notes = "Low Score (Non-Specific)"
                lead.draft_message = drafter.generate_draft(lead, "hard_rejection")
            return db.upsert_lead(lead)

        # 4. Priority Ranking (Passed Gates)
        lead.priority_rank = scorer.determine_priority(lead)
        lead.stage = PipelineStage.POTENTIAL_FIT
        
        # 5. Draft Interest Check
        if lead.priority_rank == 1:
            # Site Ready gets Priority Invite
            lead.draft_message = drafter.generate_draft(lead, "invite_to_call_priority")
        else:
            # Standard Interest Check
            lead.draft_message = drafter.generate_draft(lead, "interest_check")
            
        return db.upsert_lead(lead)

    def handle_interest_response(self, lead_id: str, response: str):
        """Called by Associate from Dashboard"""
        lead = db.get_lead(lead_id)
        if response == "YES":
            lead.stage = PipelineStage.FAQ_SENT
            lead.draft_message = drafter.generate_draft(lead, "faq_screen")
        elif response == "MAYBE":
            lead.stage = PipelineStage.WARM_LEAD
            lead.soft_rejection_reason = "Lead requested delay"
            lead.wake_up_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        elif response == "NO":
            lead.stage = PipelineStage.TURNED_DOWN
        db.upsert_lead(lead)

    def initialize_checklist(self, lead_id: str):
        """Called when entering Gate 4 (Business Proposal Approved)"""
        lead = db.get_lead(lead_id)
        
        # Determine List Type based on inputs
        is_clinic = lead.facility_meta.get("is_clinic_owner") == "Yes"
        list_key = "KYB_Clinic_Conversion" if is_clinic else "KYC_Individual"
        
        items = self.checklists.get(list_key, [])
        lead.checklist_type = list_key
        lead.checklist_status = {item: False for item in items}
        lead.stage = PipelineStage.KYC_SCREENING
        db.upsert_lead(lead)

    def update_checklist(self, lead_id: str, item: str, checked: bool):
        lead = db.get_lead(lead_id)
        if item in lead.checklist_status:
            lead.checklist_status[item] = checked
        db.upsert_lead(lead)

    def approve_draft(self, lead_id: str):
        """Human clicked 'Approve'."""
        lead = db.get_lead(lead_id)
        if not lead: return

        # State Transition Logic based on current stage
        if lead.stage == PipelineStage.POTENTIAL_FIT:
             lead.stage = PipelineStage.INTEREST_CHECK_SENT
        elif lead.stage == PipelineStage.FAQ_SENT:
             lead.stage = PipelineStage.READY_FOR_CALL
        
        lead.draft_message = None
        lead.last_contact_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.upsert_lead(lead)

workflow = WorkflowService()