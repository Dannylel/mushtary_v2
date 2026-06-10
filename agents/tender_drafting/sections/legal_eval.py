"""
LegalEvalSectionAgent — AI-generated prose, factual numbers preserved.

Generates General & Special Terms, Confidentiality, Evaluation Methodology, Payment
Terms, and Annexures for ANY category.

Deterministic (facts from the buyer form, never invented):
  - evaluation_model / technical_weight / financial_weight / minimum_technical_score

AI-generated (category-agnostic prose):
  - legal terms, compliance requirements, confidentiality, evaluation parameters,
    mandatory criteria, award basis, payment terms, annexures

The exact bid-security / performance-bond / retention / liquidated-damages figures are
passed to the model so it can weave them in; a buyer-derived fallback guarantees the
legally material clauses still appear if the LLM output is unusable.
"""

from __future__ import annotations

from typing import Any

from agents.buyer_form import TenderBuyerForm
from agents.tender_drafting.schemas import (
    EvaluationSection,
    GeneralTerms,
    LegalEvalSections,
    MandatoryCriterion,
    PaymentTerms,
)

from .base import BaseSectionAgent
from agents.prompts import load_prompt

SYSTEM_PROMPT = load_prompt("drafting_legal_eval_system")


def _evaluation_model_text(form: TenderBuyerForm) -> str:
    if form.evaluation_model:
        if "/" in form.evaluation_model and "%" not in form.evaluation_model:
            parts = form.evaluation_model.split("/")
            if len(parts) == 2:
                return f"{parts[0]}% Technical / {parts[1]}% Financial"
        return form.evaluation_model
    return f"{form.technical_weight}% Technical / {form.financial_weight}% Financial"


def _build_user_message(form: TenderBuyerForm) -> str:
    return f"""\
Draft the legal terms, confidentiality, evaluation parameters, payment terms, and annexures.

CATEGORY: {form.category} / {form.subcategory}
LOCATION: {form.location or "Kingdom of Saudi Arabia"}
LANGUAGE: {form.language_requirements or "Arabic and English"}

FIXED FACTS (do not change):
- Evaluation model: {_evaluation_model_text(form)}
- Minimum technical score: {form.minimum_score or 70}%

COMMERCIAL PROTECTIONS (use exact values; include only if required):
- Bid security required: {form.bid_security_required} — value: {form.bid_security_amount_or_percentage or "n/a"}
- Performance bond required: {form.performance_bond_required} — {form.performance_bond_percentage or "n/a"}% — validity: {form.performance_bond_validity or "n/a"}
- Retention: {form.retention_percentage if form.retention_percentage is not None else "n/a"}%
- Liquidated damages applicable: {form.liquidated_damages_applicable} — rate: {form.liquidated_damages_rate or "n/a"}

BUYER PAYMENT PREFERENCE:
{form.payment_terms}

SAUDIZATION REQUIRED: {form.saudization_required}
REQUIRED CERTIFICATIONS: {", ".join(form.required_certifications) or "None stated"}
BUYER DISQUALIFICATION CRITERIA:
{chr(10).join(f"  - {c}" for c in (form.mandatory_disqualification_criteria or [])) or "  Not specified"}

Return only the JSON object.
"""


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


_CORE_TECHNICAL_PARAMS = [
    "Completeness of the technical proposal, including all required sections and supporting documents.",
    "Clarity, readability, organization, and internal consistency of the technical proposal.",
    "Alignment of the proposed solution with the scope of work, objectives, and expected outcomes.",
    "Realism and achievability of the proposed timeline, delivery schedule, and resource plan.",
]


def _legal_fallback(form: TenderBuyerForm) -> LegalEvalSections:
    legal_terms = [
        "This RFP and any resulting contract shall be governed by the laws and regulations of the Kingdom of Saudi Arabia.",
        "Submission of a proposal implies acceptance of the tender conditions unless exceptions are clearly declared.",
        "No binding contractual relationship shall exist until a formal written agreement is signed by both parties.",
        "The buyer reserves the right to cancel, amend, extend, partially award, or reject all proposals.",
        "The vendor shall indemnify and hold harmless the buyer against claims arising from vendor breach or negligence.",
    ]
    if form.bid_security_required:
        legal_terms.append(
            f"A bid security of {form.bid_security_amount_or_percentage or 'the buyer-specified amount'} is mandatory and must remain valid as stated."
        )
    if form.performance_bond_required:
        pct = form.performance_bond_percentage if form.performance_bond_percentage is not None else "buyer-specified"
        validity = form.performance_bond_validity or "the implementation and warranty/support period"
        legal_terms.append(f"The successful bidder shall submit a performance bond of {pct}% of the contract value, valid for {validity}.")
    if form.retention_percentage is not None:
        legal_terms.append(f"A retention of {form.retention_percentage}% may be withheld until final acceptance and completion of obligations.")
    if form.liquidated_damages_applicable:
        legal_terms.append(f"Liquidated damages shall apply for vendor-attributable delay at the rate of {form.liquidated_damages_rate or 'the rate stated in the final contract'}.")

    return LegalEvalSections(
        general_terms=GeneralTerms(
            legal_terms=legal_terms,
            compliance_requirements=[
                "The vendor must comply with all applicable Saudi laws, regulations, and technical standards.",
                "The vendor must maintain all required legal, tax, banking, and signatory documents throughout the engagement.",
            ],
            language_requirements=form.language_requirements
            or "All submissions and deliverables must be provided in Arabic and English where required; Arabic prevails in case of conflict.",
            equipment_and_logistics="The vendor shall bear all costs of equipment, logistics, transport, and delivery unless explicitly excluded and accepted by the buyer.",
        ),
        confidentiality="All information exchanged between the buyer and bidders shall be treated as strictly confidential and not disclosed to any third party without prior written consent. The obligation continues beyond the tender and any resulting contract.",
        evaluation_criteria=EvaluationSection(
            evaluation_model=_evaluation_model_text(form),
            technical_weight=form.technical_weight or 70,
            financial_weight=form.financial_weight or 30,
            mandatory_criteria=[MandatoryCriterion(criterion=c) for c in (form.mandatory_disqualification_criteria or [
                "Submission of all mandatory documents.",
                "Compliance with the tender submission deadline.",
            ])],
            technical_parameters=list(_CORE_TECHNICAL_PARAMS) + list(form.technical_evaluation_parameters or []),
            financial_parameters=list(form.financial_evaluation_parameters or [
                "Total proposed price and itemized cost breakdown.",
                "Value for money rather than lowest price alone.",
                "Cost realism and absence of abnormally low pricing.",
            ]),
            scored_criteria=[],
            minimum_technical_score=float(form.minimum_score or 70),
            award_basis=(
                f"The contract will be awarded to the most economically advantageous compliant proposal based on "
                f"{_evaluation_model_text(form)}, subject to passing all mandatory criteria and a minimum technical score of {form.minimum_score or 70}%."
            ),
        ),
        payment_terms=PaymentTerms(
            payment_basis=form.payment_terms or "Milestone-based payment subject to the buyer's written acceptance of each milestone.",
            invoice_requirements=[
                "Valid tax invoice issued by the vendor.",
                "Signed milestone acceptance or completion certificate.",
                "Vendor banking details matching the approved IBAN certificate.",
            ],
            payment_timeline="Approved invoices shall be processed within thirty (30) calendar days of a valid, complete, buyer-approved invoice.",
        ),
        annexures=[
            "Annexure A: Technical Compliance Matrix",
            "Annexure B: Commercial Pricing Schedule",
            "Annexure C: Mandatory and Applicable Document Checklist",
            "Annexure D: Key Personnel CV Template",
            "Annexure E: Deviation / Exception Form",
        ],
    )


def _merge_technical_params(ai_params: list[str], form: TenderBuyerForm) -> list[str]:
    """Always lead with the 4 core parameters, then AI + buyer params, de-duplicated."""
    merged: list[str] = []
    for item in _CORE_TECHNICAL_PARAMS + ai_params + list(form.technical_evaluation_parameters or []):
        if item and item not in merged:
            merged.append(item)
    return merged


class LegalEvalSectionAgent(BaseSectionAgent):
    def run(self, form: TenderBuyerForm) -> LegalEvalSections:
        # Pull standard legal/evaluation clause wording for this category (empty string if
        # the knowledge base is unpopulated — drafting then proceeds exactly as before).
        ref = self._reference_context(
            f"legal terms, confidentiality, evaluation criteria and payment terms for "
            f"{form.category} / {form.subcategory} procurement"
        )
        user = f"{ref}\n{_build_user_message(form)}" if ref else _build_user_message(form)

        data = self._generate(SYSTEM_PROMPT, user, max_tokens=2800)
        fb = _legal_fallback(form)
        if not data:
            return fb

        gt = data.get("general_terms") or {}
        general_terms = GeneralTerms(
            legal_terms=_as_str_list(gt.get("legal_terms")) or fb.general_terms.legal_terms,
            compliance_requirements=_as_str_list(gt.get("compliance_requirements")) or fb.general_terms.compliance_requirements,
            language_requirements=_as_str(gt.get("language_requirements"), fb.general_terms.language_requirements),
            equipment_and_logistics=_as_str(gt.get("equipment_and_logistics"), fb.general_terms.equipment_and_logistics),
        )

        ev = data.get("evaluation") or {}
        mandatory = [MandatoryCriterion(criterion=c) for c in _as_str_list(ev.get("mandatory_criteria"))]
        evaluation_criteria = EvaluationSection(
            # Weighting + minimum score are FACTS — never taken from the model.
            evaluation_model=_evaluation_model_text(form),
            technical_weight=form.technical_weight or 70,
            financial_weight=form.financial_weight or 30,
            mandatory_criteria=mandatory or fb.evaluation_criteria.mandatory_criteria,
            technical_parameters=_merge_technical_params(_as_str_list(ev.get("technical_parameters")), form),
            financial_parameters=_as_str_list(ev.get("financial_parameters")) or fb.evaluation_criteria.financial_parameters,
            scored_criteria=[],
            minimum_technical_score=float(form.minimum_score or 70),
            award_basis=_as_str(ev.get("award_basis"), fb.evaluation_criteria.award_basis),
        )

        pt = data.get("payment_terms") or {}
        payment_terms = PaymentTerms(
            payment_basis=_as_str(pt.get("payment_basis"), fb.payment_terms.payment_basis),
            invoice_requirements=_as_str_list(pt.get("invoice_requirements")) or fb.payment_terms.invoice_requirements,
            payment_timeline=_as_str(pt.get("payment_timeline"), fb.payment_terms.payment_timeline),
        )

        return LegalEvalSections(
            general_terms=general_terms,
            confidentiality=_as_str(data.get("confidentiality"), fb.confidentiality),
            evaluation_criteria=evaluation_criteria,
            payment_terms=payment_terms,
            annexures=_as_str_list(data.get("annexures")) or fb.annexures,
        )
