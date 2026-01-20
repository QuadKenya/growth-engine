from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum
from typing import Optional
from datetime import datetime

class PipelineStage(str, Enum):
    EXPRESSED_INTEREST = "EXPRESSED_INTEREST"
    FRANCHISEE_VETTED = "FRANCHISEE_VETTED"
    POTENTIAL_FIT = "POTENTIAL_FIT"
    NO_FIT = "NO_FIT"
    INITIAL_CONVO = "INITIAL_CONVO"
    BUSINESS_PROPOSAL = "BUSINESS_PROPOSAL"
    INACTIVE = "INACTIVE"
    TURNED_DOWN = "TURNED_DOWN"

class Lead(BaseModel):
    """
    The canonical Candidate entity.
    Maps to the columns in the '2025 Modified File'.
    """
    # --- Identity ---
    lead_id: str = Field(description="Unique ID (Email is used for MVP)")
    timestamp: datetime = Field(default_factory=datetime.now)
    email: EmailStr
    first_name: str
    last_name: str
    phone: str
    source: str = "Web"
    
    # --- Inputs (From Google Form) ---
    current_profession: str
    experience_years: str
    has_business_exp: str
    certifications: Optional[str] = None
    financial_readiness_input: str
    location_county_input: str
    location_status_input: str

    # --- Computed State (Managed by Agent) ---
    stage: PipelineStage = PipelineStage.EXPRESSED_INTEREST
    fit_score: float = 0.0
    fit_classification: str = "Unscored"
    financial_readiness: str = "Unknown" # 🟢 Ready / 🟠 Nurture
    location_readiness: str = "Unknown"
    
    # --- Workflow Actions ---
    draft_message: Optional[str] = None
    next_step_due_date: Optional[str] = None

    class Config:
        use_enum_values = True

    @validator("phone")
    def clean_phone(cls, v):
        """Normalizes phone numbers to 254 format"""
        digits = "".join(filter(str.isdigit, v))
        if digits.startswith("0"):
            return "254" + digits[1:]
        if digits.startswith("7"):
            return "254" + digits
        return digits