from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum
from typing import Optional, Dict, List, Any, Union
from datetime import datetime

class PipelineStage(str, Enum):
    # Gate 1: Vetting
    EXPRESSED_INTEREST = "EXPRESSED_INTEREST"
    NO_FIT = "NO_FIT"             # Hard Rejection
    WARM_LEAD = "WARM_LEAD"       # Soft Rejection / Parked
    
    # Gate 2: Prioritization & Interest
    POTENTIAL_FIT = "POTENTIAL_FIT"
    INTEREST_CHECK_SENT = "INTEREST_CHECK_SENT"
    NEUTRAL_NURTURE = "NEUTRAL_NURTURE"
    
    # Gate 3: Screening
    FAQ_SENT = "FAQ_SENT"
    READY_FOR_CALL = "READY_FOR_CALL"
    
    # Gate 4: Proposal & Compliance
    INITIAL_CONVO = "INITIAL_CONVO"
    BUSINESS_PROPOSAL = "BUSINESS_PROPOSAL"
    KYC_SCREENING = "KYC_SCREENING"
    FINANCIAL_ASSESSMENT = "FINANCIAL_ASSESSMENT"
    
    # Gate 5: Assessment
    ASSESSMENT_PSYCH = "ASSESSMENT_PSYCH"
    ASSESSMENT_INTERVIEW = "ASSESSMENT_INTERVIEW"
    
    # Gate 6: Site & Contract
    SITE_SEARCH = "SITE_SEARCH"
    SITE_VETTING = "SITE_VETTING"
    CONTRACTING = "CONTRACTING"
    CONTRACT_CLOSED = "CONTRACT_CLOSED"
    
    TURNED_DOWN = "TURNED_DOWN"
    INACTIVE = "INACTIVE"

class ActivityType(str, Enum):
    TRANSITION = "TRANSITION"
    NOTE = "NOTE"
    EMAIL = "EMAIL"
    ACTION = "ACTION"
    SYSTEM = "SYSTEM"

class ActivityLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    author: str = "System"  # "System" or "Associate"
    type: ActivityType = ActivityType.SYSTEM
    content: str
    stage_snapshot: Optional[str] = None

    class Config:
        use_enum_values = True

class Lead(BaseModel):
    # --- Identity ---
    lead_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    email: EmailStr
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    phone: str
    
    # --- Inputs (Gate 1) ---
    current_profession: str
    experience_years: str
    has_business_exp: str
    financial_readiness_input: str
    location_county_input: str
    location_status_input: str
    
    # --- Clinic Conversion Meta Data (Optional) ---
    facility_meta: Dict[str, Any] = {}
    
    # --- Gate 1: Vetting State ---
    stage: PipelineStage = PipelineStage.EXPRESSED_INTEREST
    fit_score: float = 0.0
    fit_classification: str = "Unscored"
    
    # --- Gate 2: Prioritization ---
    priority_rank: int = 3  # 1=Site Ready, 2=Cash Ready, 3=Standard
    rejection_type: Optional[str] = None  # "Hard", "Soft"
    wake_up_date: Optional[str] = None    # For Warm Leads
    soft_rejection_reason: Optional[str] = None
    
    # --- Gate 3: Engagement ---
    draft_message: Optional[str] = None
    preferred_call_time: Optional[str] = None
    
    # --- Gate 4: Compliance & Financials ---
    checklist_status: Dict[str, bool] = {} 
    checklist_type: str = "KYC_Individual"
    verified_financial_capital: Optional[float] = None
    
    # --- Gate 5: Assessment ---
    psychometric_score: Optional[str] = None
    interview_notes: Optional[str] = None
    interview_date: Optional[str] = None
    
    # --- Gate 6: Site & Contract ---
    site_visit_score: Optional[float] = None
    site_location_details: Optional[str] = None
    contract_generated_date: Optional[str] = None
    
    # --- Audit & History ---
    # Notes are now part of activity_log, but we keep this field optional for backward compat
    notes: Optional[str] = None 
    activity_log: List[ActivityLogEntry] = []
    
    # --- Tracking ---
    last_contact_date: Optional[str] = None
    last_contact_channel: Optional[str] = None

    class Config:
        use_enum_values = True
        populate_by_name = True

    @validator("timestamp", pre=True)
    def parse_timestamp(cls, v):
        if isinstance(v, datetime): return v
        if not v: return datetime.now()
        try:
            # Handles string timestamp often found in JSON
            if "T" in str(v):
                return datetime.fromisoformat(str(v))
            return datetime.strptime(str(v).split('.')[0], "%Y-%m-%d %H:%M:%S")
        except:
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