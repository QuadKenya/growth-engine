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
        1. Create Lead
        2. Score Lead
        3. Transition State
        4. Draft Message
        5. Persist
        """
        # 1. Create Object (Validates Schema)
        # Assuming raw_data keys match Lead model fields or aliases
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
        # In a full State Machine, we'd lookup 'FRANCHISEE_VETTED' transitions.
        # Hardcoded for MVP flow:
        if lead.fit_classification == "Not A Fit":
            self._transition_to(lead, PipelineStage.NO_FIT)
        else:
            self._transition_to(lead, PipelineStage.POTENTIAL_FIT)

        # 5. Persist
        return db.upsert_lead(lead)

    def _transition_to(self, lead: Lead, new_stage: PipelineStage):
        """
        Handles entry actions for a new state (e.g., Drafting).
        """
        lead.stage = new_stage
        
        # Look up config for this state
        # e.g. "POTENTIAL_FIT"
        state_def = self.state_config["states"].get(new_stage.value, {})
        
        # A. Apply SLA
        if "sla_days" in state_def:
            due = datetime.now() + timedelta(days=state_def["sla_days"])
            lead.next_step_due_date = due.strftime("%Y-%m-%d")
            
        # B. Trigger Entry Actions (Drafting)
        if "on_entry" in state_def:
            action = state_def["on_entry"]
            if action["action"] == "draft_message":
                template = action["template"]
                lead.draft_message = drafter.generate_draft(lead, template)

    def approve_draft(self, lead_id: str):
        """
        Human clicked 'Approve'.
        1. Clear draft.
        2. Move state forward.
        """
        lead = db.get_lead(lead_id)
        if not lead: return
        
        # Logic: If sitting in Potential Fit with a draft, move to Initial Convo
        if lead.stage == PipelineStage.POTENTIAL_FIT:
            lead.draft_message = None # Email sent
            # Note: Real state machine might wait for "Call Completed"
            # For MVP, we assume Approval = Invite Sent -> Wait for Call
            pass 
        
        elif lead.stage == PipelineStage.NO_FIT:
             lead.draft_message = None
             lead.stage = PipelineStage.TURNED_DOWN
             
        db.upsert_lead(lead)

# Singleton
workflow = WorkflowService()