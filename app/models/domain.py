from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum
from typing import Optional
from datetime import datetime

# --- Enums matching the 2025 Modified File validation lists ---
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
    Reflects columns in the '2025 Modified File' and 'Flat File'.
    """
    
    # --- Identity (Cols A, B, C, D) ---
    lead_id: str = Field(description="Unique ID (Email is used for MVP)")
    # Robust timestamp handling for 'Flat File' Col A
    timestamp: datetime = Field(default_factory=datetime.now, description="Application Date")
    
    email: EmailStr
    first_name: str
    middle_name: Optional[str] = None # Added per Flat File Col D analysis
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
    financial_readiness: str = "Unknown" 
    location_readiness: str = "Unknown"
    
    # --- Workflow / Tracker Fields (Cols C, E, F) ---
    draft_message: Optional[str] = None
    next_step_due_date: Optional[str] = None
    notes: Optional[str] = None  # Added for Column C (Associate Comments)
    
    # Critical for SOP Inactive Rule (Column E)
    last_contact_date: Optional[str] = None 
    # Critical for reporting (Column F)
    last_contact_channel: Optional[str] = None 

    class Config:
        use_enum_values = True
        populate_by_name = True

    # --- Validators ---

    @validator("timestamp", pre=True)
    def parse_timestamp(cls, v):
        """
        Handles incoming timestamps from Google Forms (M/D/Y) or ISO format.
        """
        if isinstance(v, datetime): return v
        if not v: return datetime.now()
        
        # List of expected formats
        formats = [
            "%m/%d/%Y %H:%M:%S", # Google Forms default
            "%Y-%m-%dT%H:%M:%S", # ISO
            "%Y-%m-%d %H:%M:%S"  # DB standard
        ]
        
        for fmt in formats:
            try:
                # Clean up millisecond decimals if present
                clean_v = str(v).split('.')[0]
                return datetime.strptime(clean_v, fmt)
            except ValueError:
                continue
        
        # Fallback if parsing fails
        return datetime.now()

    @validator("phone")
    def clean_phone(cls, v):
        """Normalizes phone numbers to 254 format."""
        digits = "".join(filter(str.isdigit, v))
        if digits.startswith("0"):
            return "254" + digits[1:]
        if digits.startswith("7"):
            return "254" + digits
        return digits