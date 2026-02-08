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
    SITE_PRE_VISIT = "SITE_PRE_VISIT"    # New: Desktop Screening
    SITE_POST_VISIT = "SITE_POST_VISIT"  # New: Field Scorecard
    SITE_VETTING = "SITE_VETTING"        # Legacy / Transition
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

# --- Financial Logic Structures ---
class FinancialAssessmentData(BaseModel):
    # ABD Inputs (Statement Credits)
    statement_rows: List[Dict[str, Any]] = [] # [{date, credit_amount, include_deposit}]
    
    # ABB Inputs: 6 months x 6 checkpoints
    abb_grid: Dict[str, Dict[str, Optional[float]]] = {} # {"Month 1": {"5th": 100, ...}}

class FinancialAssessmentResults(BaseModel):
    # ABD Results
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    num_months: int = 0
    sum_deposits: float = 0.0
    abd: float = 0.0
    
    # ABB Results
    checkpoint_averages: Dict[str, float] = {}
    abb: float = 0.0
    
    # Capacity Results
    total_revenue: float = 0.0
    net_income_amount: float = 0.0
    installment_capacity_amount: float = 0.0
    
    # Decisions
    revenue_pass: bool = False
    installment_pass: bool = False
    overall_pass: bool = False

# --- NEW: Site Selection Logic Structures ---
class SiteAssessmentData(BaseModel):
    # Pre-Visit Checklist (Desktop Screening)
    pre_visit_checklist: Dict[str, bool] = {
        "photos_received": False,
        "location_pin_received": False,
        "not_too_remote": False,
        "busy_area": False,
        "ground_floor": False,
        "building_state_good": False
    }
    
    # Post-Visit Scorecard (Field Assessment)
    setting_type: str = "Urban" # Urban / Semi-Urban / Rural
    competition_clinics_1km: int = 0
    competition_pharmacies_1km: int = 0
    dist_nearest_public: float = 0.0
    archetype_score: int = 1 # 1-4
    building_sqft: float = 0.0
    has_2_rooms: bool = False
    ventilated_well_lit: bool = False
    mobile_accessible: bool = False
    electricity_available: bool = False
    water_available: bool = False
    internet_possible: bool = False
    private_toilets: bool = False
    foot_traffic_count: int = 0

class SiteAssessmentResults(BaseModel):
    competition_status: str = "Red" # Red / Amber / Green
    foot_traffic_pass: bool = False
    physical_criteria_pass: bool = False
    utilities_pass: bool = False
    overall_site_score: float = 0.0 # Percentage
    overall_site_pass: bool = False

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
    priority_rank: int = 3  
    rejection_type: Optional[str] = None  
    wake_up_date: Optional[str] = None    
    soft_rejection_reason: Optional[str] = None
    
    # --- Gate 3: Engagement ---
    draft_message: Optional[str] = None
    preferred_call_time: Optional[str] = None
    
    # --- Gate 4: Compliance & Financials ---
    checklist_status: Dict[str, bool] = {} 
    checklist_type: str = "KYC_Individual"
    financial_data: FinancialAssessmentData = Field(default_factory=FinancialAssessmentData)
    financial_results: Optional[FinancialAssessmentResults] = None
    verified_financial_capital: Optional[float] = None
    
    # --- Gate 5: Assessment ---
    psychometric_score: Optional[str] = None
    interview_notes: Optional[str] = None
    interview_date: Optional[str] = None
    
    # --- Gate 6: Site & Contract ---
    site_assessment_data: SiteAssessmentData = Field(default_factory=SiteAssessmentData)
    site_assessment_results: Optional[SiteAssessmentResults] = None
    site_visit_score: Optional[float] = None # Legacy/Sync
    site_location_details: Optional[str] = None
    contract_generated_date: Optional[str] = None
    
    # --- Audit & History ---
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