from __future__ import annotations

from pydantic import BaseModel, Field

from agents.buyer_form import TenderBuyerForm


# ── INPUT ──────────────────────────────────────────────────────────────────────

class TenderDraftInput(BaseModel):
    buyer_id: str
    form: TenderBuyerForm


# ── SECTION 1: METADATA ────────────────────────────────────────────────────────

class TenderMetadata(BaseModel):
    title: str
    tender_id: str
    issue_date: str
    buyer_entity: str
    project_name: str
    rfp_reference: str = ""


class TenderDataSheet(BaseModel):
    tender_title: str
    tender_reference: str
    buyer_entity: str
    procurement_category: str
    tender_type: str
    procurement_method: str
    submission_method: str
    issue_date: str
    clarification_deadline: str
    submission_deadline: str
    opening_date: str | None = None
    proposal_validity: str
    site_visit: str
    bid_security: str
    performance_bond: str
    contract_duration: str
    warranty_duration: str | None = None
    language: str
    evaluation_model: str
    minimum_technical_score: str


# ── SECTION 2: INTRODUCTION ────────────────────────────────────────────────────

class Introduction(BaseModel):
    about_organization: str
    background: str
    purpose_of_rfp: str


# ── SECTION 3: INSTRUCTIONS TO BIDDERS ────────────────────────────────────────

class Timetable(BaseModel):
    issue_date: str
    clarifications_deadline: str
    submission_deadline: str


class SubmissionControlOutput(BaseModel):
    platform_submission_only: bool = True
    separate_technical_commercial: bool = True
    technical_file_format: str = "PDF"
    commercial_file_format: str = "PDF/Excel"
    max_file_size_mb: int | None = 50
    resubmission_allowed_before_deadline: bool = True
    lock_after_deadline: bool = True
    late_submission_allowed: bool = False
    completeness_check_required: bool = True
    timestamp_is_official: bool = True
    rules: list[str] = Field(default_factory=list)


class InstructionsToBidders(BaseModel):
    submission_rules: list[str]
    timetable: Timetable
    proposal_validity_days: int = 90
    clarifications_process: str
    confidentiality_statement: str
    conflict_of_interest_policy: str
    cancellation_rights: str
    submission_controls: SubmissionControlOutput | None = None


# ── SECTION 4: AWARD AND CONTRACT ─────────────────────────────────────────────

class VendorDocumentOutput(BaseModel):
    name: str
    requirement_level: str
    category: str
    applicability: str = "All vendors"
    issuing_authority: str | None = None
    notes: str | None = None


class AwardAndContract(BaseModel):
    evaluation_process: str
    negotiation_policy: str
    award_rules: str
    bid_security: str | None = None
    performance_bond_percent: float | None = None
    performance_bond_text: str | None = None
    statutory_documents_required: list[str]
    mandatory_documents: list[VendorDocumentOutput] = Field(default_factory=list)
    conditional_documents: list[VendorDocumentOutput] = Field(default_factory=list)
    optional_documents: list[VendorDocumentOutput] = Field(default_factory=list)
    sector_specific_documents: list[VendorDocumentOutput] = Field(default_factory=list)
    prestige_documents: list[VendorDocumentOutput] = Field(default_factory=list)
    vendor_document_rules: list[str] = Field(default_factory=list)
    saudization_requirements: str


# ── SECTION 5: PROPOSAL FORMAT REQUIREMENTS ───────────────────────────────────

class TechnicalProposalFormat(BaseModel):
    file_naming_convention: str
    required_sections: list[str]


class CommercialProposalFormat(BaseModel):
    file_naming_convention: str
    pricing_requirements: list[str]
    accepted_currencies: list[str] = Field(default_factory=lambda: ["SAR"])


class ProposalFormatRequirements(BaseModel):
    submission_method: str
    technical_proposal: TechnicalProposalFormat
    commercial_proposal: CommercialProposalFormat


# ── SECTION 6: PROJECT OVERVIEW ───────────────────────────────────────────────

class ProjectOverview(BaseModel):
    project_introduction: str
    background: str
    context: str


# ── SECTION 7: OBJECTIVES ─────────────────────────────────────────────────────

class Objectives(BaseModel):
    business_goals: list[str]
    expected_outcomes: list[str]
    kpis: list[str]


# ── SECTION 8: SCOPE OF WORK ──────────────────────────────────────────────────

class ScopeCategory(BaseModel):
    name: str
    description: str
    requirements: list[str]


class ScopePhase(BaseModel):
    phase: str
    activities: list[str]


class ScopeOfWork(BaseModel):
    categories: list[ScopeCategory]
    phases: list[ScopePhase]
    general_requirements: list[str]


# ── SECTION 9: DELIVERABLES ───────────────────────────────────────────────────

class TenderDeliverable(BaseModel):
    name: str
    description: str
    format: str | None = None
    deadline_note: str | None = None


class EscalationTier(BaseModel):
    level: str
    trigger_delay: str
    contact_role: str


class DeliverablesSection(BaseModel):
    work_order_process: list[str]
    deliverables: list[TenderDeliverable]
    approval_process: str
    reporting_requirements: list[str]
    escalation_tiers: list[EscalationTier]


# ── SECTION 10: TIMELINE ──────────────────────────────────────────────────────

class TenderMilestone(BaseModel):
    phase: str
    milestone: str
    target_date: str


class Timeline(BaseModel):
    total_duration: str
    project_phases: list[str]
    milestones: list[TenderMilestone]


# ── SECTION 11: TEAM REQUIREMENTS ────────────────────────────────────────────

class TeamRole(BaseModel):
    position: str
    responsibilities: str
    minimum_experience: str


class TeamRequirements(BaseModel):
    roles: list[TeamRole]
    saudization_note: str


# ── SECTION 12: GENERAL & SPECIAL TERMS ──────────────────────────────────────

class GeneralTerms(BaseModel):
    legal_terms: list[str]
    compliance_requirements: list[str]
    language_requirements: str
    equipment_and_logistics: str | None = None


# ── SECTION 14: EVALUATION CRITERIA ──────────────────────────────────────────

class MandatoryCriterion(BaseModel):
    criterion: str


class ScoredCriterion(BaseModel):
    """
    Kept for backward compatibility.
    The tender document can still avoid showing formulas/percentages.
    """
    id: str
    name: str
    description: str
    weight_percent: float = Field(ge=0.0, le=100.0)
    scoring_rubric: str


class EvaluationSection(BaseModel):
    evaluation_model: str = "70/30"
    technical_weight: int = 70
    financial_weight: int = 30
    mandatory_criteria: list[MandatoryCriterion]
    technical_parameters: list[str] = Field(default_factory=list)
    financial_parameters: list[str] = Field(default_factory=list)
    scored_criteria: list[ScoredCriterion] = Field(default_factory=list)
    minimum_technical_score: float = 70.0
    award_basis: str = "Highest combined evaluation result after mandatory compliance and buyer approval"


# ── SECTION 15: PAYMENT TERMS ────────────────────────────────────────────────

class PaymentTerms(BaseModel):
    payment_basis: str
    invoice_requirements: list[str]
    payment_timeline: str


# ── SECTION-GROUP AGENT OUTPUT MODELS ────────────────────────────────────────

class ContextSections(BaseModel):
    metadata: TenderMetadata
    tender_data_sheet: TenderDataSheet
    introduction: Introduction
    instructions_to_bidders: InstructionsToBidders
    award_and_contract: AwardAndContract
    proposal_format: ProposalFormatRequirements


class ScopeSections(BaseModel):
    project_overview: ProjectOverview
    objectives: Objectives
    scope_of_work: ScopeOfWork


class ExecutionSections(BaseModel):
    deliverables: DeliverablesSection
    timeline: Timeline
    team_requirements: TeamRequirements


class LegalEvalSections(BaseModel):
    general_terms: GeneralTerms
    confidentiality: str
    evaluation_criteria: EvaluationSection
    payment_terms: PaymentTerms
    annexures: list[str]


# ── PLATFORM POLICY (deterministic — never left to the model) ─────────────────

# The standard annexure set every Mushtarry tender carries (reference layout:
# docs/tender_draft 1.pdf §17). Fixed for uniformity across all tenders.
STANDARD_ANNEXURES: list[str] = [
    "Annexure A: Technical Compliance Matrix",
    "Annexure B: Commercial Pricing Schedule",
    "Annexure C: Mandatory and Applicable Document Checklist",
    "Annexure D: Vendor Experience Form",
    "Annexure E: Key Personnel CV Template",
    "Annexure F: Implementation Plan and Timeline Template",
    "Annexure G: Risk and Mitigation Register",
    "Annexure H: Deviation / Exception Form",
    "Annexure I: SLA, Warranty, and Support Form",
    "Annexure J: Bid Security and Performance Bond Templates, if applicable",
]

# Everything happens ON the Mushtarry platform. These clauses are guaranteed to appear
# in every draft regardless of what the model wrote.
_PLATFORM_SUBMISSION_RULE = (
    "All proposals, clarifications, communications, and document uploads shall be made "
    "exclusively through the Mushtarry platform; no other channel is accepted."
)
_PLATFORM_WORK_ORDER_RULE = (
    "All Work Orders shall be issued, accepted, tracked, and closed exclusively through "
    "the Mushtarry platform."
)
_PLATFORM_DELIVERABLES_NOTE = (
    " All deliverables shall be submitted, reviewed, and accepted exclusively through the "
    "Mushtarry platform; platform records constitute the official record of submission "
    "and acceptance."
)
_PLATFORM_COMPLIANCE_RULE = (
    "All tender activities — submissions, clarifications, deliverables, acceptance, "
    "invoicing, and correspondence — shall be conducted on the Mushtarry platform, whose "
    "timestamps and records are the official record."
)
_PLATFORM_INVOICE_RULE = (
    "Invoices and supporting documents shall be submitted through the Mushtarry platform."
)


def _has_mushtarry(items: list[str]) -> bool:
    return any("mushtarry" in (i or "").lower() for i in items)


def _enforce_platform_policy(draft: "TenderDraft") -> "TenderDraft":
    """Guarantee the everything-on-Mushtarry clauses appear, wherever the model forgot."""
    ins = draft.instructions_to_bidders
    if not _has_mushtarry(ins.submission_rules):
        ins.submission_rules.insert(0, _PLATFORM_SUBMISSION_RULE)

    dels = draft.deliverables
    if not _has_mushtarry(dels.work_order_process):
        dels.work_order_process.insert(0, _PLATFORM_WORK_ORDER_RULE)
    if "mushtarry" not in (dels.approval_process or "").lower():
        dels.approval_process = (dels.approval_process or "").rstrip() + _PLATFORM_DELIVERABLES_NOTE

    gt = draft.general_terms
    if not _has_mushtarry(gt.compliance_requirements):
        gt.compliance_requirements.append(_PLATFORM_COMPLIANCE_RULE)

    pay = draft.payment_terms
    if not _has_mushtarry(pay.invoice_requirements):
        pay.invoice_requirements.append(_PLATFORM_INVOICE_RULE)

    return draft


def assemble_tender_draft(
    ctx: ContextSections,
    scope: ScopeSections,
    exec_: ExecutionSections,
    legal: LegalEvalSections,
    trace_id: str,
) -> "TenderDraft":
    draft = TenderDraft(
        metadata=ctx.metadata,
        tender_data_sheet=ctx.tender_data_sheet,
        introduction=ctx.introduction,
        instructions_to_bidders=ctx.instructions_to_bidders,
        award_and_contract=ctx.award_and_contract,
        proposal_format=ctx.proposal_format,
        project_overview=scope.project_overview,
        objectives=scope.objectives,
        scope_of_work=scope.scope_of_work,
        deliverables=exec_.deliverables,
        timeline=exec_.timeline,
        team_requirements=exec_.team_requirements,
        general_terms=legal.general_terms,
        confidentiality=legal.confidentiality,
        evaluation_criteria=legal.evaluation_criteria,
        payment_terms=legal.payment_terms,
        # Annexures are the fixed platform-standard set — uniform across all tenders.
        annexures=list(STANDARD_ANNEXURES),
        ai_generated=True,
        trace_id=trace_id,
    )
    return _enforce_platform_policy(draft)


# ── FULL TENDER DRAFT OUTPUT ──────────────────────────────────────────────────

class TenderDraft(BaseModel):
    metadata: TenderMetadata
    tender_data_sheet: TenderDataSheet
    introduction: Introduction
    instructions_to_bidders: InstructionsToBidders
    award_and_contract: AwardAndContract
    proposal_format: ProposalFormatRequirements
    project_overview: ProjectOverview
    objectives: Objectives
    scope_of_work: ScopeOfWork
    deliverables: DeliverablesSection
    timeline: Timeline
    team_requirements: TeamRequirements
    general_terms: GeneralTerms
    confidentiality: str
    evaluation_criteria: EvaluationSection
    payment_terms: PaymentTerms
    annexures: list[str]
    ai_generated: bool = True
    trace_id: str


# ── FALLBACK ──────────────────────────────────────────────────────────────────

DRAFT_FALLBACK = TenderDraft(
    metadata=TenderMetadata(
        title="Draft Tender",
        tender_id="TND-DRAFT",
        issue_date="",
        buyer_entity="",
        project_name="",
        rfp_reference="TND-DRAFT",
    ),
    tender_data_sheet=TenderDataSheet(
        tender_title="Draft Tender",
        tender_reference="TND-DRAFT",
        buyer_entity="",
        procurement_category="",
        tender_type="Request for Proposal (RFP)",
        procurement_method="Open / Invited Tender",
        submission_method="Electronic submission",
        issue_date="",
        clarification_deadline="",
        submission_deadline="",
        proposal_validity="90 days",
        site_visit="Not specified",
        bid_security="Not required",
        performance_bond="Not required",
        contract_duration="Not specified",
        warranty_duration=None,
        language="Arabic and English",
        evaluation_model="70/30",
        minimum_technical_score="70%",
    ),
    introduction=Introduction(
        about_organization="",
        background="",
        purpose_of_rfp="",
    ),
    instructions_to_bidders=InstructionsToBidders(
        submission_rules=[
            "Separate Technical and Commercial Proposals are required.",
            "Late submissions will not be accepted.",
            "All proposals must be signed and stamped.",
        ],
        timetable=Timetable(issue_date="", clarifications_deadline="", submission_deadline=""),
        proposal_validity_days=90,
        clarifications_process="Clarifications must be submitted in writing by the stated deadline.",
        confidentiality_statement="All proposals shall be kept strictly confidential.",
        conflict_of_interest_policy="Bidders must disclose any actual or potential conflict of interest.",
        cancellation_rights="The buyer reserves the right to cancel the tender at any stage.",
        submission_controls=SubmissionControlOutput(),
    ),
    award_and_contract=AwardAndContract(
        evaluation_process="Proposals will be evaluated using mandatory compliance, technical parameters, and financial parameters.",
        negotiation_policy="The buyer reserves the right to negotiate with shortlisted bidders.",
        award_rules="Award is subject to buyer approval and final contract execution.",
        bid_security="Not required",
        performance_bond_percent=None,
        performance_bond_text="Not required",
        statutory_documents_required=[
            "Commercial Registration Certificate",
            "VAT Registration Certificate, if applicable",
            "National Address Certificate",
            "IBAN Certificate / Bank Letter",
        ],
        saudization_requirements="Vendor must comply with applicable Saudization requirements.",
    ),
    proposal_format=ProposalFormatRequirements(
        submission_method="Electronic submission",
        technical_proposal=TechnicalProposalFormat(
            file_naming_convention="Technical_[Bidder]_[Tender Reference]_[Tender Title].pdf",
            required_sections=[
                "Cover Page",
                "Company Profile",
                "Executive Summary",
                "Technical Methodology",
                "Implementation Plan",
                "Project Team",
                "Document Checklist",
            ],
        ),
        commercial_proposal=CommercialProposalFormat(
            file_naming_convention="Commercial_[Bidder]_[Tender Reference]_[Tender Title].pdf",
            pricing_requirements=[
                "Submit itemized pricing.",
                "Quote in SAR.",
                "Show VAT separately where applicable.",
                "Sign and stamp the commercial proposal.",
            ],
        ),
    ),
    project_overview=ProjectOverview(project_introduction="", background="", context=""),
    objectives=Objectives(business_goals=[], expected_outcomes=[], kpis=[]),
    scope_of_work=ScopeOfWork(categories=[], phases=[], general_requirements=[]),
    deliverables=DeliverablesSection(
        work_order_process=[],
        deliverables=[],
        approval_process="All deliverables are subject to buyer review and written approval.",
        reporting_requirements=[],
        escalation_tiers=[],
    ),
    timeline=Timeline(total_duration="", project_phases=[], milestones=[]),
    team_requirements=TeamRequirements(roles=[], saudization_note=""),
    general_terms=GeneralTerms(
        legal_terms=[],
        compliance_requirements=[],
        language_requirements="Arabic and English.",
    ),
    confidentiality="The vendor shall keep all buyer information confidential.",
    evaluation_criteria=EvaluationSection(
        evaluation_model="70/30",
        technical_weight=70,
        financial_weight=30,
        mandatory_criteria=[
            MandatoryCriterion(criterion="Submission of all mandatory documents."),
            MandatoryCriterion(criterion="Compliance with tender submission deadline."),
        ],
        technical_parameters=[],
        financial_parameters=[],
        minimum_technical_score=70.0,
    ),
    payment_terms=PaymentTerms(
        payment_basis="Milestone-based payment after written acceptance.",
        invoice_requirements=["Valid invoice", "Signed acceptance certificate"],
        payment_timeline="Within the buyer-approved payment cycle.",
    ),
    annexures=[
        "Annexure A: Technical Compliance Matrix",
        "Annexure B: Commercial Pricing Schedule",
        "Annexure C: Mandatory Document Checklist",
    ],
    ai_generated=True,
    trace_id="fallback",
)