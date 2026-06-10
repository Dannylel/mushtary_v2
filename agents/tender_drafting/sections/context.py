"""
ContextSectionAgent

Builds structured opening tender sections deterministically:
- Metadata
- Tender Data Sheet
- Introduction
- Instructions to Bidders
- Award and Contract
- Vendor Document Requirements
- Proposal Format

This avoids invalid LLM JSON and prevents blank PDFs.
"""

from __future__ import annotations

from typing import Any

from agents.buyer_form import TenderBuyerForm
from agents.tender_drafting.schemas import (
    AwardAndContract,
    CommercialProposalFormat,
    ContextSections,
    Introduction,
    InstructionsToBidders,
    ProposalFormatRequirements,
    SubmissionControlOutput,
    TechnicalProposalFormat,
    TenderDataSheet,
    TenderMetadata,
    Timetable,
    VendorDocumentOutput,
)

from .base import BaseSectionAgent
from agents.prompts import load_prompt


def _value(value: Any, default: str = "Not specified") -> str:
    if value is None:
        return default

    text = str(value).strip()
    return text or default


def _bid_security_text(form: TenderBuyerForm) -> str:
    if not form.bid_security_required:
        return "Not required"

    return f"Required. Bid security amount: {form.bid_security_amount_or_percentage or 'as specified by buyer'}."


def _bond_text(form: TenderBuyerForm) -> str:
    if not form.performance_bond_required:
        return "Not required"

    percent = (
        f"{form.performance_bond_percentage}%"
        if form.performance_bond_percentage is not None
        else "as specified by buyer"
    )

    validity = form.performance_bond_validity or (
        "valid for the full implementation period and warranty/support period, unless otherwise stated in the final contract"
    )

    return f"Required. Performance bond amount: {percent} of contract value. Validity: {validity}."


def _site_visit_text(form: TenderBuyerForm) -> str:
    """
    For MVP tender generation, site visit is treated as recommended for IT/data-center tenders
    unless the buyer explicitly makes it mandatory in the final policy/UI.

    This lets bidders understand the environment before bidding, while the post-award
    assessment remains part of the vendor's delivery scope.
    """
    if not form.site_visit_required:
        return "Not required"

    if form.site_visit_date:
        return f"Recommended / optional. Site visit date: {form.site_visit_date}."

    return "Recommended / optional. Date to be confirmed by buyer."


def _proposal_validity_text(form: TenderBuyerForm) -> str:
    return f"{form.proposal_validity_days} days from the proposal submission deadline"


def _minimum_score_text(form: TenderBuyerForm) -> str:
    return f"{form.minimum_score or 70}%"


def _evaluation_model_text(form: TenderBuyerForm) -> str:
    if form.evaluation_model:
        if "/" in form.evaluation_model and "%" not in form.evaluation_model:
            parts = form.evaluation_model.split("/")
            if len(parts) == 2:
                return f"{parts[0]}% Technical / {parts[1]}% Financial"

        return form.evaluation_model

    return f"{form.technical_weight}% Technical / {form.financial_weight}% Financial"


def _document_to_output(doc: Any) -> VendorDocumentOutput:
    if hasattr(doc, "model_dump"):
        data = doc.model_dump()
    elif hasattr(doc, "dict"):
        data = doc.dict()
    elif isinstance(doc, dict):
        data = doc
    else:
        data = {
            "name": str(doc),
            "requirement_level": "mandatory",
            "category": "Document",
            "applicability": "As required",
            "issuing_authority": None,
            "notes": None,
        }

    return VendorDocumentOutput(
        name=data.get("name", ""),
        requirement_level=data.get("requirement_level", ""),
        category=data.get("category", ""),
        applicability=data.get("applicability", "As required"),
        issuing_authority=data.get("issuing_authority"),
        notes=data.get("notes"),
    )


def _documents_to_outputs(docs: list[Any]) -> list[VendorDocumentOutput]:
    return [_document_to_output(doc) for doc in docs or []]


def _statutory_document_names(form: TenderBuyerForm) -> list[str]:
    names: list[str] = []

    for group in [
        form.mandatory_documents,
        form.conditional_documents,
        form.sector_specific_documents,
        form.optional_documents,
    ]:
        for doc in group:
            name = getattr(doc, "name", None)
            if name and name not in names:
                names.append(name)

    return names or form.required_documents or []


def _submission_rules(form: TenderBuyerForm) -> list[str]:
    sc = form.submission_controls

    rules = [
        f"All proposals must be submitted through {form.submission_method}.",
        "Hard copy submissions will not be accepted unless explicitly allowed by the buyer.",
    ]

    if sc.separate_technical_commercial:
        rules.append("Bidders must submit separate Technical and Commercial proposals.")

    rules.extend(
        [
            f"The Technical Proposal must be submitted in {sc.technical_file_format} format.",
            f"The Commercial Proposal must be submitted in {sc.commercial_file_format} format.",
        ]
    )

    if sc.max_file_size_mb:
        rules.append(
            f"Each uploaded file must not exceed {sc.max_file_size_mb} MB unless otherwise approved by the buyer."
        )

    if sc.completeness_check_required:
        rules.append("The platform may perform completeness checks before final submission.")

    if sc.resubmission_allowed_before_deadline:
        rules.append(
            "Bidders may revise and resubmit proposals before the official submission deadline. Each resubmission creates a new retained version."
        )
    else:
        rules.append("Resubmission is not allowed unless specifically approved by the buyer.")

    if sc.lock_after_deadline:
        rules.append("Submitted proposals will be locked after the official deadline.")

    if not sc.late_submission_allowed:
        rules.append("Late submissions will not be accepted.")

    if sc.timestamp_is_official:
        rules.append("The official submission time shall be the timestamp recorded by the Mushtarry platform.")

    rules.extend(
        [
            "All proposals must be signed and stamped by an authorized representative of the bidder.",
            "The bidder is responsible for ensuring that all required documents are complete, valid, and readable.",
            "The buyer reserves the right to reject incomplete, non-compliant, or misleading submissions.",
        ]
    )

    return rules


def _submission_control_rules(form: TenderBuyerForm) -> list[str]:
    sc = form.submission_controls

    rules = []

    if sc.platform_submission_only:
        rules.append("Submission is permitted only through the Mushtarry platform.")

    if sc.separate_technical_commercial:
        rules.append("Technical and Commercial proposals must be submitted separately.")

    if sc.completeness_check_required:
        rules.append("Mandatory document completeness may be checked before final submission.")

    if sc.resubmission_allowed_before_deadline:
        rules.append("Resubmissions before the deadline create updated proposal versions.")

    if sc.lock_after_deadline:
        rules.append("Final submitted proposals are locked after the deadline.")

    if not sc.late_submission_allowed:
        rules.append("Late submissions are not allowed.")

    if sc.timestamp_is_official:
        rules.append("The Mushtarry platform timestamp is the official submission timestamp.")

    return rules


def _technical_required_sections(form: TenderBuyerForm) -> list[str]:
    return [
        "Cover Page including tender reference, project title, bidder legal name, contact details, date, signature, and stamp.",
        "Company Profile including legal structure, headquarters, core business, KSA presence, and relevant experience.",
        "Executive Summary describing the proposed solution and how it addresses the buyer's objectives.",
        "Understanding of Scope of Work and Project Objectives.",
        "Proposed Technical Solution and Compliance with Specifications.",
        "Implementation Methodology including migration approach, rollback plan, testing plan, and risk management.",
        "Project Timeline, Milestones, and Resource Plan.",
        "Project Team Structure, Roles, CVs, Certifications, and Relevant Experience.",
        "Warranty, SLA, Support Model, and Handover Plan.",
        "Technical Compliance Matrix.",
        "Mandatory, Conditional, Sector-Specific, and Optional Document Checklist.",
        "Deviation and Exception Statement, if any.",
    ]


def _commercial_pricing_requirements(form: TenderBuyerForm) -> list[str]:
    return [
        "Commercial proposal must be submitted separately from the Technical Proposal.",
        "All prices must be quoted in Saudi Riyals (SAR), unless otherwise approved by the buyer.",
        "The bidder must provide an itemized pricing breakdown covering hardware, software, implementation, support, warranty, and recurring costs.",
        "VAT and other applicable taxes must be shown clearly and separately.",
        "One-time and recurring costs must be clearly distinguished.",
        "The total proposed contract value must be shown in numbers and words.",
        "All commercial exceptions, assumptions, exclusions, and deviations must be clearly declared.",
        "The commercial proposal must remain valid for the required proposal validity period.",
        "The commercial proposal must be signed and stamped by the bidder's authorized representative.",
    ]


def _vendor_document_rules() -> list[str]:
    return [
        "Mandatory documents are required to qualify the vendor for this tender.",
        "Mandatory-if-applicable and conditional documents are required only where they apply to the vendor type, buyer type, sector, or regulatory context.",
        "Missing conditional or sector-specific documents may result in limited eligibility or buyer/manager review, rather than automatic rejection, unless the buyer defines them as mandatory for this tender.",
        "Optional documents are not mandatory but may improve buyer confidence, eligibility, and AI category inference.",
        "All submitted documents must be valid, readable, and aligned with the vendor's legal identity.",
        "Expired mandatory documents may place the vendor under review.",
        "All document validation actions and decisions must be auditable.",
    ]


def _introduction(form: TenderBuyerForm) -> Introduction:
    """Deterministic fallback introduction (used only if the LLM output is unusable)."""
    return Introduction(
        about_organization=(
            f"{form.buyer_name} is issuing this tender through the Mushtarry platform. "
            f"{form.buyer_description}"
        ),
        background=(
            f"The buyer intends to procure under the category "
            f"'{form.category} - {form.subcategory}'. {form.project_objective}"
        ),
        purpose_of_rfp=(
            f"The purpose of this Request for Proposal is to invite qualified vendors to submit technical and commercial "
            f"proposals for '{form.tender_title}'. The selected vendor will be expected to deliver the required scope of work, "
            f"meet all eligibility and document requirements, and comply with the tender's technical, commercial, legal, "
            f"and submission rules."
        ),
    )


# ── AI-generated narrative overlay ─────────────────────────────────────────────
# Facts (dates, IDs, security amounts, document lists, toggles) stay deterministic.
# Only the narrative prose below is generated by the LLM, category-agnostically.

NARRATIVE_SYSTEM_PROMPT = load_prompt("drafting_context_narrative_system")


def _narrative_user_message(form: TenderBuyerForm) -> str:
    return f"""\
Draft the narrative sections for this tender.

BUYER: {form.buyer_name}
BUYER DESCRIPTION: {form.buyer_description}
TENDER TITLE: {form.tender_title}
CATEGORY: {form.category} / {form.subcategory}
PROJECT OBJECTIVE: {form.project_objective}
SAUDIZATION REQUIRED: {form.saudization_required}

Return only the JSON object.
"""


def _pick(d: dict, key: str, default: str) -> str:
    if not isinstance(d, dict):
        return default
    value = d.get(key)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


class ContextSectionAgent(BaseSectionAgent):
    def run(self, form: TenderBuyerForm) -> ContextSections:
        sc = form.submission_controls

        # AI narrative overlay (falls back to deterministic prose on any failure).
        narrative = self._generate(NARRATIVE_SYSTEM_PROMPT, _narrative_user_message(form), max_tokens=1600)
        ni = narrative.get("introduction") if isinstance(narrative, dict) else {}
        ninst = narrative.get("instructions") if isinstance(narrative, dict) else {}
        naward = narrative.get("award") if isinstance(narrative, dict) else {}
        fb_intro = _introduction(form)

        metadata = TenderMetadata(
            title=form.tender_title,
            tender_id=form.tender_id,
            issue_date=_value(form.issue_date, ""),
            buyer_entity=form.buyer_name,
            project_name=form.tender_title,
            rfp_reference=form.tender_id,
        )

        tender_data_sheet = TenderDataSheet(
            tender_title=form.tender_title,
            tender_reference=form.tender_id,
            buyer_entity=form.buyer_name,
            procurement_category=f"{form.category} / {form.subcategory}",
            tender_type=form.tender_type,
            procurement_method=form.procurement_method,
            submission_method=form.submission_method,
            issue_date=_value(form.issue_date, "To be confirmed"),
            clarification_deadline=_value(form.clarification_deadline, "To be confirmed"),
            submission_deadline=form.submission_deadline,
            opening_date=form.opening_date,
            proposal_validity=_proposal_validity_text(form),
            site_visit=_site_visit_text(form),
            bid_security=_bid_security_text(form),
            performance_bond=_bond_text(form),
            contract_duration=_value(form.contract_duration),
            warranty_duration=form.warranty_duration,
            language=_value(form.language_requirements, "Arabic and English"),
            evaluation_model=_evaluation_model_text(form),
            minimum_technical_score=_minimum_score_text(form),
        )

        instructions_to_bidders = InstructionsToBidders(
            submission_rules=_submission_rules(form),
            timetable=Timetable(
                issue_date=_value(form.issue_date, "To be confirmed"),
                clarifications_deadline=_value(form.clarification_deadline, "To be confirmed"),
                submission_deadline=form.submission_deadline,
            ),
            proposal_validity_days=form.proposal_validity_days,
            clarifications_process=_pick(
                ninst,
                "clarifications_process",
                "All clarification requests must be submitted through the Mushtarry platform before the clarification deadline. "
                "Clarifications issued by the buyer through the platform shall form part of the tender record. "
                "If a site visit is conducted, the clarification deadline should remain open after the site visit so bidders can raise site-visit-related questions.",
            ),
            confidentiality_statement=_pick(
                ninst,
                "confidentiality_statement",
                "All tender information, buyer data, technical specifications, documents, and bidder submissions shall be treated as confidential "
                "and used only for the purpose of this procurement.",
            ),
            conflict_of_interest_policy=_pick(
                ninst,
                "conflict_of_interest_policy",
                "Bidders must disclose any actual, potential, or perceived conflict of interest. The buyer may reject or disqualify a bidder "
                "where a conflict compromises fairness, integrity, or independence of the procurement process.",
            ),
            cancellation_rights=_pick(
                ninst,
                "cancellation_rights",
                "The buyer reserves the right to cancel, amend, suspend, extend, partially award, or reject all proposals at any stage, "
                "subject to applicable procurement rules and buyer approval.",
            ),
            submission_controls=SubmissionControlOutput(
                platform_submission_only=sc.platform_submission_only,
                separate_technical_commercial=sc.separate_technical_commercial,
                technical_file_format=sc.technical_file_format,
                commercial_file_format=sc.commercial_file_format,
                max_file_size_mb=sc.max_file_size_mb,
                resubmission_allowed_before_deadline=sc.resubmission_allowed_before_deadline,
                lock_after_deadline=sc.lock_after_deadline,
                late_submission_allowed=sc.late_submission_allowed,
                completeness_check_required=sc.completeness_check_required,
                timestamp_is_official=sc.timestamp_is_official,
                rules=_submission_control_rules(form),
            ),
        )

        award_and_contract = AwardAndContract(
            evaluation_process=_pick(
                naward,
                "evaluation_process",
                "Proposals will be reviewed in stages: mandatory pass/fail compliance, technical evaluation, financial evaluation, "
                "AI-assisted recommendation where enabled, and final buyer approval. AI outputs are advisory only and do not replace buyer decision-making.",
            ),
            negotiation_policy=_pick(
                naward,
                "negotiation_policy",
                "The buyer may negotiate with one or more shortlisted bidders regarding technical scope, commercial terms, implementation details, "
                "or contractual clarifications before final award.",
            ),
            award_rules=_pick(
                naward,
                "award_rules",
                "Award shall be based on mandatory compliance, technical and financial evaluation parameters, commercial acceptability, buyer approval, "
                "and final contract execution. The buyer may reject non-compliant or incomplete proposals.",
            ),
            bid_security=_bid_security_text(form),
            performance_bond_percent=form.performance_bond_percentage,
            performance_bond_text=_bond_text(form),
            statutory_documents_required=_statutory_document_names(form),
            mandatory_documents=_documents_to_outputs(form.mandatory_documents),
            conditional_documents=_documents_to_outputs(form.conditional_documents),
            optional_documents=_documents_to_outputs(form.optional_documents),
            sector_specific_documents=_documents_to_outputs(form.sector_specific_documents),
            prestige_documents=_documents_to_outputs(form.prestige_documents),
            vendor_document_rules=_vendor_document_rules(),
            saudization_requirements=_pick(
                naward,
                "saudization_requirements",
                (
                    "The bidder shall comply with all applicable Saudization, labor, and local content requirements. "
                    "Where Saudization is relevant to the tender, the bidder should clearly state the proposed Saudi national participation, "
                    "local support capability, and compliance evidence."
                    if form.saudization_required
                    else "Saudization requirements are not specifically required for this tender unless mandated by law."
                ),
            ),
        )

        proposal_format = ProposalFormatRequirements(
            submission_method=form.submission_method,
            technical_proposal=TechnicalProposalFormat(
                file_naming_convention=f"Technical_[Bidder Name]_{form.tender_id}_{form.tender_title}.pdf",
                required_sections=_technical_required_sections(form),
            ),
            commercial_proposal=CommercialProposalFormat(
                file_naming_convention=f"Commercial_[Bidder Name]_{form.tender_id}_{form.tender_title}.pdf",
                pricing_requirements=_commercial_pricing_requirements(form),
                accepted_currencies=["SAR"],
            ),
        )

        introduction = Introduction(
            about_organization=_pick(ni, "about_organization", fb_intro.about_organization),
            background=_pick(ni, "background", fb_intro.background),
            purpose_of_rfp=_pick(ni, "purpose_of_rfp", fb_intro.purpose_of_rfp),
        )

        return ContextSections(
            metadata=metadata,
            tender_data_sheet=tender_data_sheet,
            introduction=introduction,
            instructions_to_bidders=instructions_to_bidders,
            award_and_contract=award_and_contract,
            proposal_format=proposal_format,
        )