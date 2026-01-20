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
        """Simulation Mode: Fills a simple f-string."""
        time.sleep(0.5) # Simulate latency
        
        header = f"TO: {lead.email}\nCHANNEL: WhatsApp\n\n"
        
        if template_key == "invite_to_call":
            return header + (
                f"Habari {lead.first_name}! 👋\n\n"
                f"We reviewed your application to become a Curafa franchisee. "
                f"We are impressed by your {lead.experience_years} experience as a {lead.current_profession}.\n\n"
                f"You have been identified as a {lead.fit_classification}. "
                f"Are you free next Tuesday for a 15-min intro call?"
            )
        
        elif template_key == "rejection_notice":
            return header + (
                f"Dear {lead.first_name},\n\n"
                f"Thank you for your interest in Access Afya. "
                f"At this time, we are proceeding with other candidates for the {lead.location_county_input} region.\n\n"
                f"We encourage you to apply again in the future."
            )
        
        return header + "[Draft Generation Error: Unknown Template]"

    def _generate_with_gpt(self, lead: Lead, template_key: str) -> str:
        """Production Mode: Calls OpenAI."""
        user_prompt = f"""
        TASK: Draft a message for template '{template_key}'.
        
        CANDIDATE DATA:
        Name: {lead.first_name} {lead.last_name}
        Profession: {lead.current_profession}
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