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
        # 1. Create Object (Validates Schema)
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

        # 5. Persist
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
            # Skip if already has a draft waiting (don't double draft)
            if lead.draft_message:
                continue

            # LOGIC: If in POTENTIAL_FIT for > 3 days (Simulated), Nudge
            if lead.stage == PipelineStage.POTENTIAL_FIT:
                # Robust timestamp parsing
                try:
                    ts_str = str(lead.timestamp)
                    # Handle both formats if they exist (ISO vs simple)
                    if "T" in ts_str:
                        lead_date = datetime.strptime(ts_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")
                    else:
                        lead_date = datetime.strptime(ts_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except:
                    # Fallback if timestamp is messy, assume it's old
                    lead_date = now - timedelta(days=10)

                # Using 0 days for simulation purposes so you see it instantly
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
        """
        Handles entry actions for a new state (e.g., Drafting).
        """
        lead.stage = new_stage
        
        # Look up config for this state
        state_def = self.state_config["states"].get(new_stage.value, {})
        
        # A. Apply SLA
        if "sla_days" in state_def:
            due = datetime.now() + timedelta(days=state_def["sla_days"])
            lead.next_step_due_date = due.strftime("%Y-%m-%d")
            
        # B. Generate Draft if requested
        if template:
            lead.draft_message = drafter.generate_draft(lead, template)

    def approve_draft(self, lead_id: str):
        """
        Human clicked 'Approve'.
        1. Clear draft.
        2. Move state forward.
        """
        lead = db.get_lead(lead_id)
        if not lead: return
        
        # Scenario: Approving the first invite
        if lead.stage == PipelineStage.FRANCHISEE_VETTED:
            lead.stage = PipelineStage.POTENTIAL_FIT
        
        # Scenario: Approving a Nudge
        # (State stays same, just timestamp update implicitly)
        
        lead.draft_message = None # Email sent
        db.upsert_lead(lead)

workflow = WorkflowService()