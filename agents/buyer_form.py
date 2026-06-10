from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class TimelineItem(BaseModel):
    milestone: str
    date: str


class Deliverable(BaseModel):
    name: str
    description: str
    format: Optional[str] = None


class Responsibility(BaseModel):
    party: str  # "Buyer" or "Vendor"
    responsibilities: List[str]


class EvaluationCriteria(BaseModel):
    """
    Kept for backward compatibility with the existing agents.
    Later, the web UI can still store detailed weighted criteria if required.
    """
    name: str
    weight: int
    description: str


class VendorDocumentRequirement(BaseModel):
    """
    Used by the future UI as dropdown/selectable document options.
    requirement_level:
      - mandatory: required from all relevant vendors
      - conditional: required only if applicable
      - optional: not required, but improves eligibility/credibility
      - sector_specific: required if sector/category applies
      - prestige: optional high-prestige organization document
    """
    name: str
    requirement_level: Literal[
        "mandatory",
        "conditional",
        "optional",
        "sector_specific",
        "prestige",
    ]
    category: str
    applicability: str = "All vendors"
    issuing_authority: Optional[str] = None
    notes: Optional[str] = None


class SubmissionControls(BaseModel):
    """
    These map nicely to future UI toggles/dropdowns.
    """
    platform_submission_only: bool = True
    separate_technical_commercial: bool = True
    technical_file_format: str = "PDF"
    commercial_file_format: str = "PDF/Excel"
    max_file_size_mb: Optional[int] = 50
    resubmission_allowed_before_deadline: bool = True
    lock_after_deadline: bool = True
    late_submission_allowed: bool = False
    completeness_check_required: bool = True
    timestamp_is_official: bool = True


class TenderBuyerForm(BaseModel):
    # --- BASIC INFO ---
    tender_title: str
    tender_id: str
    buyer_name: str
    buyer_description: str

    # --- TENDER CONTROL / DATA SHEET ---
    tender_type: str = "Request for Proposal (RFP)"
    procurement_method: str = "Open / Invited Tender"
    issue_date: Optional[str] = None
    clarification_deadline: Optional[str] = None
    submission_deadline: str
    opening_date: Optional[str] = None
    proposal_validity_days: int = 90
    site_visit_required: bool = False
    site_visit_date: Optional[str] = None

    # --- CATEGORY ---
    category: str
    subcategory: str

    # --- PROJECT DETAILS / SOW CORE ---
    project_objective: str
    scope_of_work: str
    deliverables: List[Deliverable]
    timeline: List[TimelineItem]
    roles_and_responsibilities: List[Responsibility]

    # --- REQUIREMENTS ---
    technical_requirements: Optional[str] = None
    methodology_requirements: Optional[str] = None

    # --- COMMERCIAL ---
    estimated_value_sar: Optional[int] = None
    budget_range: Optional[str] = None
    payment_terms: str

    # --- BID SECURITY / BONDS ---
    bid_security_required: bool = False
    bid_security_amount_or_percentage: Optional[str] = None
    performance_bond_required: bool = False
    performance_bond_percentage: Optional[float] = None
    performance_bond_validity: Optional[str] = None
    retention_percentage: Optional[float] = None
    liquidated_damages_applicable: bool = False
    liquidated_damages_rate: Optional[str] = None

    # --- ELIGIBILITY ---
    eligibility_criteria: List[str]
    minimum_years_experience: Optional[int] = None
    minimum_similar_projects: Optional[int] = None
    minimum_project_value_sar: Optional[int] = None
    required_sector_license: Optional[str] = None
    required_certifications: List[str] = Field(default_factory=list)
    blacklist_declaration_required: bool = True
    local_presence_required: bool = False
    saudization_required: bool = True

    # --- DOCUMENT REQUIREMENTS ---
    # kept for backward compatibility
    required_documents: List[str] = Field(default_factory=list)

    mandatory_documents: List[VendorDocumentRequirement] = Field(default_factory=list)
    conditional_documents: List[VendorDocumentRequirement] = Field(default_factory=list)
    optional_documents: List[VendorDocumentRequirement] = Field(default_factory=list)
    sector_specific_documents: List[VendorDocumentRequirement] = Field(default_factory=list)
    prestige_documents: List[VendorDocumentRequirement] = Field(default_factory=list)

    # --- EVALUATION ---
    # UI can offer: "70/30", "60/40", "50/50", "Custom"
    evaluation_model: str = "70/30"
    technical_weight: int = 70
    financial_weight: int = 30
    minimum_score: Optional[int] = 70

    # kept for backward compatibility
    evaluation_criteria: List[EvaluationCriteria] = Field(default_factory=list)

    # New simple evaluation parameter lists.
    # User asked: no formulas/percentages in tender; just list parameters.
    technical_evaluation_parameters: List[str] = Field(default_factory=list)
    financial_evaluation_parameters: List[str] = Field(default_factory=list)

    mandatory_disqualification_criteria: List[str] = Field(default_factory=list)

    # --- SUBMISSION ---
    submission_method: str
    proposal_format: str
    submission_controls: SubmissionControls = Field(default_factory=SubmissionControls)

    # --- CONTRACT TERMS ---
    contract_duration: Optional[str] = None
    warranty_duration: Optional[str] = None
    confidentiality_required: bool = True

    # --- OPTIONAL ---
    location: Optional[str] = None
    onsite_required: Optional[bool] = None
    language_requirements: Optional[str] = None