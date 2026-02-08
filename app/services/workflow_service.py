from datetime import datetime, timedelta, date
import json
import os
from app.core.config import settings
from app.db.supabase import db
from app.models.domain import (
    Lead, PipelineStage, ActivityLogEntry, ActivityType, 
    FinancialAssessmentData, SiteAssessmentData, Cohort
)
from app.services.scoring_service import scorer, fin_calc, site_calc
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
            lead.notes = gate_check["reason"]
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

    # --- ENGAGEMENT ---
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
        lead.notes = content 
        self.log_activity(lead, content, ActivityType.NOTE, author="Associate")
        db.upsert_lead(lead)

    # --- GATE 4: COMPLIANCE ---
    def initialize_checklist(self, lead_id: str, type_override: str = None):
        """Start KYC/KYB."""
        lead = db.get_lead(lead_id)
        list_key = type_override if type_override else "KYC_Individual"
        items = self.checklists.get(list_key, [])
        lead.checklist_type = list_key
        lead.checklist_status = {item: False for item in items}
        lead.stage = PipelineStage.KYC_SCREENING
        self.log_activity(lead, f"Started Compliance ({list_key}).", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    def update_checklist(self, lead_id: str, item: str, checked: bool):
        """
        Updates a specific checklist item.
        Transitions to Financial Assessment if all items are complete.
        """
        lead = db.get_lead(lead_id)
        if item in lead.checklist_status:
            lead.checklist_status[item] = checked
            
            # Check if all done
            if all(lead.checklist_status.values()):
                lead.stage = PipelineStage.FINANCIAL_ASSESSMENT
                lead.draft_message = None # Clear draft, no nudge needed
                self.log_activity(lead, "All Docs Received. Moved to Financial Assessment.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    # --- UPDATED: Financial Submission ---
    def submit_financial_assessment(self, lead_id: str, assessment_data: FinancialAssessmentData):
        """Processes structured financial inputs and determines if lead proceeds."""
        lead = db.get_lead(lead_id)
        if not lead: return

        # 1. Run Calculator
        results = fin_calc.calculate_assessment(assessment_data)
        
        # 2. Persist inputs and results
        lead.financial_data = assessment_data
        lead.financial_results = results
        lead.verified_financial_capital = results.total_revenue # Legacy display field
        
        # 3. Decision Logic
        if results.overall_pass:
            lead.stage = PipelineStage.ASSESSMENT_PSYCH
            self.log_activity(lead, f"Financials PASSED. Revenue: KES {results.total_revenue:,.0f}, Capacity: KES {results.installment_capacity_amount:,.0f}", ActivityType.TRANSITION)
        else:
            lead.stage = PipelineStage.WARM_LEAD
            lead.rejection_type = "Soft"
            lead.soft_rejection_reason = f"Financial Threshold Not Met (Rev: KES {results.total_revenue:,.0f})"
            lead.wake_up_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
            self.log_activity(lead, f"Financials FAILED (Rev: {results.total_revenue:,.0f} < 240k). Moved to Warm Leads.", ActivityType.TRANSITION)
            
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

    # --- NEW: GATE 6: SITE SELECTION ---
    def start_site_review(self, lead_id: str):
        """Moves lead to Pre-Visit Desktop Review."""
        lead = db.get_lead(lead_id)
        lead.stage = PipelineStage.SITE_PRE_VISIT
        self.log_activity(lead, "Site Information received. Starting Desktop Review.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    def update_pre_visit_checklist(self, lead_id: str, item: str, checked: bool):
        """Updates Desktop Screening items."""
        lead = db.get_lead(lead_id)
        if item in lead.site_assessment_data.pre_visit_checklist:
            lead.site_assessment_data.pre_visit_checklist[item] = checked
            
            # If all screening items are checked, move to POST_VISIT (Field Scorecard stage)
            if all(lead.site_assessment_data.pre_visit_checklist.values()):
                lead.stage = PipelineStage.SITE_POST_VISIT
                self.log_activity(lead, "Desktop Review Complete. Moved to Field Assessment.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    def submit_site_scorecard(self, lead_id: str, scorecard_data: SiteAssessmentData):
        """Calculates site results and decides if lead moves to contracting."""
        lead = db.get_lead(lead_id)
        if not lead: return

        # 1. Calculate
        results = site_calc.calculate_site_results(scorecard_data)
        
        # 2. Persist
        lead.site_assessment_data = scorecard_data
        lead.site_assessment_results = results
        lead.site_visit_score = results.overall_site_score * 100 
        
        # 3. Decision & Detailed Logging
        if results.overall_site_pass:
            lead.stage = PipelineStage.CONTRACTING
            lead.contract_generated_date = datetime.now().strftime("%Y-%m-%d")
            self.log_activity(lead, f"Site APPROVED (Score: {results.overall_site_score*100:.0f}%). Moving to Contracting.", ActivityType.TRANSITION)
        else:
            # Construct detailed reason string for the log
            reasons = []
            if results.competition_status == "Red": reasons.append("Competition: RED")
            if not results.foot_traffic_pass: reasons.append("Foot Traffic: FAIL")
            if not results.physical_criteria_pass: reasons.append("Physical Criteria: FAIL")
            if not results.utilities_pass: reasons.append("Utilities: FAIL")
            if results.overall_site_score < 0.70: reasons.append("Score below 70%")
            reason_str = ", ".join(reasons)
            lead.stage = PipelineStage.SITE_SEARCH
            self.log_activity(
                lead, 
                f"Site REJECTED (Score: {results.overall_site_score*100:.0f}%). Reasons: {reason_str}. Returning to search.", 
                ActivityType.TRANSITION
            )
            
        db.upsert_lead(lead)

    def close_contract(self, lead_id: str):
        lead = db.get_lead(lead_id)
        lead.stage = PipelineStage.CONTRACT_CLOSED
        self.log_activity(lead, "Contract Signed! New Franchisee Onboarded.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    # --- NEW: COHORT MANAGEMENT ---
    def create_cohort(self, name: str, start_date: date, end_date: date):
        cohort = Cohort(name=name, start_date=start_date, end_date=end_date)
        return db.upsert_cohort(cohort)

    def get_all_cohorts(self) -> list[Cohort]:
        return db.fetch_all_cohorts()

    def delete_cohort(self, name: str):
        db.delete_cohort(name)

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

    def reactivate_lead(self, lead_id: str):
        """Reactivates a Warm Lead back to Potential Fit."""
        lead = db.get_lead(lead_id)
        lead.stage = PipelineStage.POTENTIAL_FIT
        lead.wake_up_date = None
        lead.soft_rejection_reason = None
        
        # Regenerate Draft based on Priority (Rank 1 vs Standard)
        if lead.priority_rank == 1:
            lead.draft_message = drafter.generate_draft(lead, "invite_to_call_priority")
        else:
            lead.draft_message = drafter.generate_draft(lead, "interest_check")
            
        self.log_activity(lead, "Lead Reactivated from Warm Pool. Draft Regenerated.", ActivityType.TRANSITION)
        db.upsert_lead(lead)

    # NEW: Update draft helper (was missing from previous file dump but used in dashboard)
    def update_draft(self, lead_id: str, new_text: str):
        lead = db.get_lead(lead_id)
        lead.draft_message = new_text
        db.upsert_lead(lead)

workflow = WorkflowService()