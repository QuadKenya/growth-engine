import time
from app.core.config import settings
from app.models.domain import Lead

# Optional: Import OpenAI if API key exists
try:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
except ImportError:
    client = None

class DraftingService:
    def __init__(self):
        self.system_prompt = settings.SYSTEM_PROMPT

    def generate_draft(self, lead: Lead, template_key: str) -> str:
        """
        Decides whether to use Real AI or Mock AI based on .env
        """
        if settings.OPENAI_API_KEY and client:
            return self._generate_with_gpt(lead, template_key)
        else:
            return self._generate_mock(lead, template_key)

    def _generate_mock(self, lead: Lead, template_key: str) -> str:
        """Simulation Mode: Generates dynamic text based on Score & Readiness."""
        time.sleep(0.5) 
        
        header = f"TO: {lead.email}\nCHANNEL: WhatsApp (+{lead.phone})\n\n"
        
        # --- TEMPLATE: INVITE TO CALL (POTENTIAL FIT) ---
        if template_key == "invite_to_call":
            greeting = f"Habari {lead.first_name}! 👋\n\n"
            
            # VARIATION 1: IDEAL FIT (Score >= 0.20)
            if lead.fit_classification == "Ideal Fit":
                body = (
                    f"We are impressed by your profile! With {lead.experience_years} experience as a {lead.current_profession} "
                    f"AND your business background, you are exactly the type of partner we look for.\n\n"
                    f"We want to fast-track your application for the {lead.location_county_input} region."
                )
            
            # VARIATION 2: CONDITIONAL FIT (Score 0.17 - 0.18)
            elif lead.fit_classification == "Fair/Conditional Fit":
                body = (
                    f"We reviewed your application. You meet our minimum requirements for the {lead.location_county_input} region, "
                    f"but we noticed you might need support with business operations.\n\n"
                    f"We would like to discuss how our training program can help bridge that gap."
                )
                
            # VARIATION 3: STANDARD GOOD FIT
            else:
                body = (
                    f"We think you could be a great fit for Curafa given your background as a {lead.current_profession}.\n\n"
                    f"We are expanding in {lead.location_county_input} and would like to discuss next steps."
                )

            # ADD-ON: FINANCIAL NURTURE (If they need a loan)
            financial_note = ""
            if lead.financial_readiness == "🟠 Nurture":
                financial_note = (
                    "\n\n(Note: We saw you mentioned needing financing. "
                    "We have banking partners who assist Curafa franchisees with working capital—we can discuss this on the call.)"
                )

            call_to_action = "\n\nAre you free next Tuesday for a 15-min intro call?"
            
            return header + greeting + body + financial_note + call_to_action
        
        # --- TEMPLATE: REJECTION (NO FIT) ---
        elif template_key == "rejection_notice":
            return header + (
                f"Dear {lead.first_name},\n\n"
                f"Thank you for applying to Access Afya. "
                f"This year's process is competitive. Unfortunately, based on our territory and experience criteria, "
                f"we cannot proceed with your application for {lead.location_county_input} at this time.\n\n"
                f"We will keep your details for future opportunities."
            )

        # --- TEMPLATE: NUDGE (STUCK IN PIPELINE) ---
        elif template_key == "nudge_booking":
            return header + (
                f"Hi {lead.first_name}, just checking in! \n\n"
                f"We still have a slot open for an intro call this week. "
                f"Please let us know if you are still interested?"
            )
            
        elif template_key == "nudge_proposal":
            return header + (
                f"Hi {lead.first_name}, hope you are well.\n\n"
                f"Just a gentle reminder to submit your Business Proposal form."
            )

        return header + "[Draft Error: Unknown Template]"

    def _generate_with_gpt(self, lead: Lead, template_key: str) -> str:
        """Production Mode: Calls OpenAI."""
        user_prompt = f"""
        TASK: Draft a message for template '{template_key}'.
        
        CANDIDATE DATA:
        Name: {lead.first_name} {lead.last_name}
        Profession: {lead.current_profession}
        Exp: {lead.experience_years}
        Business Exp: {lead.has_business_exp}
        County: {lead.location_county_input}
        Score: {lead.fit_score} ({lead.fit_classification})
        Financial Readiness: {lead.financial_readiness}
        """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

# Singleton
drafter = DraftingService()