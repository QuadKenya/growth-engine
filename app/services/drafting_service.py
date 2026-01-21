import time
from app.core.config import settings
from app.models.domain import Lead

class DraftingService:
    def __init__(self):
        self.system_prompt = settings.SYSTEM_PROMPT

    def generate_draft(self, lead: Lead, template_key: str) -> str:
        # In a real app, this calls OpenAI. 
        # Here we simulate the specific templates defined in your SOP.
        time.sleep(0.5) 
        
        header = f"TO: {lead.email}\nCHANNEL: WhatsApp (+{lead.phone})\n\n"
        
        # --- SCENARIO A: NEW LEAD (The "Potential Fit") ---
        if template_key == "invite_to_call":
            return header + (
                f"Habari {lead.first_name}! 👋\n\n"
                f"We reviewed your application for the {lead.location_county_input} region. "
                f"Given your {lead.experience_years} experience as a {lead.current_profession}, "
                f"we think you could be a great fit for Curafa.\n\n"
                f"Are you free next Tuesday for a 15-min intro call?"
            )
        
        # --- SCENARIO B: REJECTION (The "No Fit") ---
        elif template_key == "rejection_notice":
            return header + (
                f"Dear {lead.first_name},\n\n"
                f"Thank you for applying to Access Afya. "
                f"This year's process is very competitive. Unfortunately, based on our current territory criteria, "
                f"we cannot proceed with your application at this time.\n\n"
                f"We will keep your details for future opportunities."
            )

        # --- SCENARIO C: THE NUDGE (Stuck in 'Potential Fit') ---
        elif template_key == "nudge_booking":
            return header + (
                f"Hi {lead.first_name}, just checking in! \n\n"
                f"We still have a slot open for an intro call this week to discuss the franchise opportunity. "
                f"Please let us know if you are still interested?"
            )

        # --- SCENARIO D: THE PROPOSAL CHASER (Stuck in 'Initial Convo') ---
        elif template_key == "nudge_proposal":
            return header + (
                f"Hi {lead.first_name}, hope you are well.\n\n"
                f"Just a gentle reminder to submit your Business Proposal form. "
                f"Remember, our team is available on Thursday if you need help with the financials section."
            )

        return header + "[Draft Error: Unknown Template]"

drafter = DraftingService()