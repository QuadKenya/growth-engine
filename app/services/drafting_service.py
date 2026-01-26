from app.core.config import settings
from app.models.domain import Lead

class DraftingService:
    def __init__(self):
        self.system_prompt = settings.SYSTEM_PROMPT

    def generate_draft(self, lead: Lead, template_key: str) -> str:
        # Mock Mode logic updated for new templates
        header = f"TO: {lead.email}\nCHANNEL: WhatsApp (+{lead.phone})\n\n"
        
        if template_key == "interest_check":
            return header + (
                f"Habari {lead.first_name},\n\n"
                "Thank you for applying to Curafa! We have reviewed your application and you meet our initial vetting criteria.\n"
                "Before we proceed to the next stage, are you still interested in moving forward right now?\n"
                "Reply YES to proceed, or let us know if you prefer to wait."
            )
            
        elif template_key == "invite_to_call_priority":
            return header + (
                f"Habari {lead.first_name},\n"
                f"Your application stood out—especially since you have a location ready in {lead.location_county_input}.\n"
                "We are fast-tracking site owners. Are you available for a brief chat this week?"
            )
            
        elif template_key == "soft_rejection_experience":
            return header + (
                f"Dear {lead.first_name},\n"
                "Your profile is promising! However, Curafa requires 3 years of clinical experience.\n"
                "We have added you to our Talent Pool and will reach out in 12 months."
            )

        elif template_key == "soft_rejection_financial":
            return header + (
                f"Dear {lead.first_name},\n"
                "We noticed you are still planning your funding. We recommend organizing capital approx KES 80k/month.\n"
                "We will keep you on our Warm List for the next cohort."
            )

        elif template_key == "soft_rejection_location":
            return header + (
                f"Dear {lead.first_name},\n"
                f"We see you are still scouting in {lead.location_county_input}. Location is key.\n"
                "Attached is our Site Selection Guide. We will check in next quarter."
            )
            
        elif template_key == "faq_screen":
            return header + (
                "Great! To ensure Curafa is the right fit, please review the commitment:\n"
                "1. It is a Franchise business.\n"
                "2. Timeline: Intro Call (Wk1) -> Contract (Wk12).\n\n"
                "If you agree, reply with your preferred time for an Intro Call."
            )
            
        elif template_key == "checklist_reminder":
            missing = [k for k, v in lead.checklist_status.items() if not v]
            return header + (
                f"Hi {lead.first_name}, we are still waiting on:\n"
                f"- {', '.join(missing)}\n"
                "Please upload these to proceed to the Financial Assessment."
            )

        elif template_key == "hard_rejection":
            return header + (
                f"Dear {lead.first_name},\n"
                f"Based on our current criteria regarding {lead.notes}, we cannot proceed with your application at this time."
            )

        return header + f"[Drafting Template: {template_key}]"

drafter = DraftingService()