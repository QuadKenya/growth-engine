from datetime import datetime, timedelta
from app.core.config import settings
from app.db.supabase import db
from app.models.domain import Lead, PipelineStage
from app.services.scoring_service import scorer
from app.services.drafting_service import drafter

class WorkflowService:
    def __init__(self):
        self.state_config = settings.STATE_MACHINE

    def process_incoming_lead(self, raw_data: dict) -> Lead:
        """
        End-to-End processing of a new Webhook.
        """
        # 1. Create Object (Validates Schema & Parses Timestamp)
        lead = Lead(**raw_data)
        
        # 2. Score
        score_result = scorer.calculate_score(lead)
        lead.fit_score = score_result["score"]
        lead.fit_classification = scorer.classify_score(lead.fit_score)
        
        # 3. Assess Readiness
        lead.financial_readiness = scorer.determine_readiness(
            lead.financial_readiness_input, "financial"
        )
        lead.location_readiness = scorer.determine_readiness(
            lead.location_status_input, "location"
        )

        # 4. State Transition (Gate 1 Logic)
        if lead.fit_classification == "Not A Fit":
            self._transition_to(lead, PipelineStage.NO_FIT, "rejection_notice")
        else:
            self._transition_to(lead, PipelineStage.POTENTIAL_FIT, "invite_to_call")
            
        return db.upsert_lead(lead)

    def run_sla_checks(self) -> int:
        """
        Iterates all leads. Checks if they are stuck. Generates Nudges.
        Returns number of nudges created.
        """
        leads = db.fetch_all_leads()
        nudges_generated = 0
        now = datetime.now()

        for lead in leads:
            if lead.draft_message: continue

            # LOGIC: If in POTENTIAL_FIT for > 3 days (Simulated), Nudge
            if lead.stage == PipelineStage.POTENTIAL_FIT:
                # Safe date conversion using Pydantic's parsed timestamp
                lead_date = lead.timestamp
                if isinstance(lead_date, str):
                    # Fallback if string persisted
                    lead_date = datetime.strptime(lead_date.split(".")[0], "%Y-%m-%d %H:%M:%S")

                # Simulation Mode: 0 days to trigger instantly
                if (now - lead_date).days >= 0: 
                    lead.draft_message = drafter.generate_draft(lead, "nudge_booking")
                    lead.next_step_due_date = now.strftime("%Y-%m-%d")
                    db.upsert_lead(lead)
                    nudges_generated += 1
            
            # LOGIC: If in INITIAL_CONVO > 7 days, Nudge Proposal
            elif lead.stage == PipelineStage.INITIAL_CONVO:
                lead.draft_message = drafter.generate_draft(lead, "nudge_proposal")
                db.upsert_lead(lead)
                nudges_generated += 1

        return nudges_generated

    def _transition_to(self, lead: Lead, new_stage: PipelineStage, template: str = None):
        lead.stage = new_stage
        
        state_def = self.state_config["states"].get(new_stage.value, {})
        
        if "sla_days" in state_def:
            due = datetime.now() + timedelta(days=state_def["sla_days"])
            lead.next_step_due_date = due.strftime("%Y-%m-%d")
            
        if template:
            lead.draft_message = drafter.generate_draft(lead, template)

    def approve_draft(self, lead_id: str):
        """
        Human clicked 'Approve'. Updates contact timestamp and stage.
        """
        lead = db.get_lead(lead_id)
        if not lead: return

        # 1. Update Pipeline Stage
        if lead.stage == PipelineStage.FRANCHISEE_VETTED:
            lead.stage = PipelineStage.POTENTIAL_FIT
        
        # 2. Pipeline Integrity: Update Contact Meta-Data
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lead.last_contact_date = now_str
        
        # Infer channel from the draft (Simulation logic)
        if lead.draft_message and "WhatsApp" in lead.draft_message:
            lead.last_contact_channel = "WhatsApp"
        else:
            lead.last_contact_channel = "Email"

        # 3. Clear Draft
        lead.draft_message = None 
        
        db.upsert_lead(lead)

workflow = WorkflowService()