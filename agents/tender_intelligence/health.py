from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from agents.buyer_form import TenderBuyerForm
from agents.guardrails import safe_parse
from agents.llm_config import chat_json_with_usage
from agents.prompts import load_prompt
from agents.tender_drafting.schemas import TenderDraft

from .schemas import (
    AITenderCommitteeAgentResult,
    AITenderCommitteeOutput,
    TenderHealthAgentResult,
    TenderHealthAggregateOutput,
    TenderHealthFinding,
    TenderHealthScore,
)

logger = logging.getLogger(__name__)

PROMPTS = {
    "scope": load_prompt("tender_health_scope_system"),
    "commercial": load_prompt("tender_health_commercial_system"),
    "compliance": load_prompt("tender_health_compliance_system"),
    "participation": load_prompt("tender_health_participation_system"),
    "aggregator": load_prompt("tender_health_aggregator_system"),
}


def _text_len(value: Any) -> int:
    return len(str(value or "").strip())


def _score_from_checks(base: int, penalties: list[int]) -> int:
    return max(0, min(100, base - sum(penalties)))


def _risk_label(score: int) -> str:
    if score >= 85:
        return "Low"
    if score >= 70:
        return "Medium"
    return "High"


def _participation_label(score: int) -> str:
    if score >= 85:
        return "High"
    if score >= 70:
        return "Medium"
    return "Low"


def _finding(
    area: str,
    severity: str,
    issue: str,
    recommendation: str,
    evidence: str = "",
) -> TenderHealthFinding:
    return TenderHealthFinding(
        area=area,
        severity=severity,
        issue=issue,
        recommendation=recommendation,
        evidence=evidence,
    )


def _agent_result(
    *,
    agent_name: str,
    role: str,
    score: int,
    summary: str,
    reasoning_summary: list[str],
    signals: list[str],
    findings: list[TenderHealthFinding],
) -> TenderHealthAgentResult:
    return TenderHealthAgentResult(
        agent_name=agent_name,
        role=role,
        score=score,
        risk_level=_risk_label(score),
        summary=summary,
        reasoning_summary=reasoning_summary,
        signals=signals,
        findings=findings,
    )


def _scope_fallback(draft: TenderDraft, form: TenderBuyerForm) -> TenderHealthAgentResult:
    findings: list[TenderHealthFinding] = []
    penalties: list[int] = []

    scope_text_size = (
        _text_len(form.scope_of_work)
        + _text_len(form.project_objective)
        + _text_len(form.technical_requirements)
        + sum(_text_len(c.description) + sum(_text_len(r) for r in c.requirements) for c in draft.scope_of_work.categories)
    )
    deliverable_count = len(draft.deliverables.deliverables)
    milestone_count = len(draft.timeline.milestones)

    if scope_text_size < 900:
        penalties.append(14)
        findings.append(
            _finding(
                "Scope",
                "Medium",
                "The scope is present but may not be detailed enough for vendor pricing.",
                "Add more measurable service boundaries, assumptions, exclusions, and acceptance criteria.",
                "Scope text signal is below the target detail threshold.",
            )
        )

    if deliverable_count < 3:
        penalties.append(10)
        findings.append(
            _finding(
                "Deliverables",
                "Medium",
                "The tender has a limited deliverables list.",
                "Add named deliverables with format, owner, review cycle, and acceptance deadline.",
                f"Deliverables defined: {deliverable_count}.",
            )
        )

    if milestone_count < 3:
        penalties.append(8)
        findings.append(
            _finding(
                "Timeline",
                "Low",
                "The timeline has few milestones.",
                "Break the project into clearer phases with target dates and approval gates.",
                f"Milestones defined: {milestone_count}.",
            )
        )

    score = _score_from_checks(100, penalties)
    summary = (
        "Scope, deliverables, and milestones are strong enough for vendor review."
        if score >= 85
        else "Scope can support a draft, but vendors may need more detail before final pricing."
    )
    return _agent_result(
        agent_name="Scope Clarity Agent",
        role="Reviews scope depth, deliverables, milestones, and acceptance clarity.",
        score=score,
        summary=summary,
        reasoning_summary=[
            "Checked scope depth, deliverables, and timeline completeness.",
            "Applied penalties where the draft may create vendor clarification questions.",
        ],
        signals=[
            f"Scope text signal: {scope_text_size} characters",
            f"Deliverables defined: {deliverable_count}",
            f"Milestones defined: {milestone_count}",
        ],
        findings=findings,
    )


def _commercial_fallback(draft: TenderDraft) -> TenderHealthAgentResult:
    findings: list[TenderHealthFinding] = []
    penalties: list[int] = []

    technical_count = len(draft.evaluation_criteria.technical_parameters)
    financial_count = len(draft.evaluation_criteria.financial_parameters)
    payment_detail = _text_len(draft.payment_terms.payment_basis)
    invoice_count = len(draft.payment_terms.invoice_requirements)

    if technical_count == 0:
        penalties.append(12)
        findings.append(
            _finding(
                "Evaluation",
                "High",
                "Technical evaluation parameters are missing or too thin.",
                "Define the technical parameters vendors will be assessed against.",
                "No technical evaluation parameters were found.",
            )
        )

    if financial_count == 0:
        penalties.append(10)
        findings.append(
            _finding(
                "Commercial",
                "Medium",
                "Financial evaluation parameters are missing or too thin.",
                "State the pricing format, VAT treatment, currency, and comparison basis.",
                "No financial evaluation parameters were found.",
            )
        )

    if payment_detail < 80:
        penalties.append(8)
        findings.append(
            _finding(
                "Payment",
                "Low",
                "Payment terms may be too brief for vendor confidence.",
                "Clarify milestones, required acceptance documents, invoice approval path, and payment timing.",
                "Payment basis text is brief.",
            )
        )

    score = _score_from_checks(100, penalties)
    summary = (
        "Commercial and evaluation instructions are clear for a market-facing draft."
        if score >= 85
        else "Commercial details are usable but should be tightened before publication."
    )
    return _agent_result(
        agent_name="Commercial Clarity Agent",
        role="Reviews evaluation parameters, pricing clarity, payment basis, and invoice controls.",
        score=score,
        summary=summary,
        reasoning_summary=[
            "Checked whether vendors can price and package a commercial proposal.",
            "Weighted missing evaluation or payment details as commercial risk.",
        ],
        signals=[
            f"Technical evaluation parameters: {technical_count}",
            f"Financial evaluation parameters: {financial_count}",
            f"Invoice requirements: {invoice_count}",
        ],
        findings=findings,
    )


def _compliance_fallback(draft: TenderDraft) -> TenderHealthAgentResult:
    findings: list[TenderHealthFinding] = []
    penalties: list[int] = []

    mandatory_doc_count = len(draft.award_and_contract.mandatory_documents)
    pass_fail_count = len(draft.evaluation_criteria.mandatory_criteria)
    compliance_count = len(draft.general_terms.compliance_requirements)
    has_submission_controls = draft.instructions_to_bidders.submission_controls is not None

    if mandatory_doc_count == 0:
        penalties.append(12)
        findings.append(
            _finding(
                "Eligibility",
                "High",
                "Mandatory vendor documents are not formalized.",
                "List mandatory, conditional, sector-specific, and optional documents separately.",
                "No mandatory document objects were found.",
            )
        )

    if pass_fail_count < 2:
        penalties.append(10)
        findings.append(
            _finding(
                "Compliance",
                "Medium",
                "Mandatory pass/fail criteria are limited.",
                "Add pass/fail checks for eligibility, documents, submission format, and conflict of interest.",
                f"Pass/fail criteria count: {pass_fail_count}.",
            )
        )

    if compliance_count == 0:
        penalties.append(8)
        findings.append(
            _finding(
                "Terms",
                "Medium",
                "Compliance requirements are not clearly listed.",
                "Add regulatory, platform, confidentiality, data protection, and conduct requirements.",
                "No compliance requirement list items were found.",
            )
        )

    if not has_submission_controls:
        penalties.append(8)
        findings.append(
            _finding(
                "Submission",
                "Low",
                "Platform submission controls are not attached.",
                "Confirm submission channel, file formats, lock-after-deadline behavior, and timestamp rules.",
                "Submission controls object is missing.",
            )
        )

    score = _score_from_checks(100, penalties)
    summary = (
        "Compliance controls are present and suitable for Buyer-Admin review."
        if score >= 85
        else "Compliance controls are mostly present, with some items to strengthen before publication."
    )
    return _agent_result(
        agent_name="Compliance Readiness Agent",
        role="Reviews eligibility, mandatory documents, pass/fail controls, and platform submission governance.",
        score=score,
        summary=summary,
        reasoning_summary=[
            "Checked whether eligibility, document, and submission controls are explicit.",
            "Flagged missing controls that could create review or disqualification ambiguity.",
        ],
        signals=[
            f"Mandatory documents: {mandatory_doc_count}",
            f"Pass/fail criteria: {pass_fail_count}",
            f"Compliance requirements: {compliance_count}",
            f"Submission controls attached: {'Yes' if has_submission_controls else 'No'}",
        ],
        findings=findings,
    )


def _participation_fallback(
    scope_agent: TenderHealthAgentResult,
    commercial_agent: TenderHealthAgentResult,
    compliance_agent: TenderHealthAgentResult,
) -> TenderHealthAgentResult:
    findings: list[TenderHealthFinding] = []
    penalties: list[int] = []

    if scope_agent.score < 75:
        penalties.append(12)
        findings.append(
            _finding(
                "Vendor Questions",
                "Medium",
                "Scope ambiguity may increase clarification questions.",
                "Resolve scope and deliverable findings before inviting vendors.",
                f"Scope agent score: {scope_agent.score}.",
            )
        )

    if commercial_agent.score < 80:
        penalties.append(8)
        findings.append(
            _finding(
                "Vendor Participation",
                "Low",
                "Commercial uncertainty can reduce vendor confidence.",
                "Clarify pricing basis and payment terms to improve participation.",
                f"Commercial agent score: {commercial_agent.score}.",
            )
        )

    if compliance_agent.score < 80:
        penalties.append(8)
        findings.append(
            _finding(
                "Compliance Burden",
                "Low",
                "Unclear compliance expectations can increase disqualification risk.",
                "Make mandatory documents and pass/fail rules explicit.",
                f"Compliance agent score: {compliance_agent.score}.",
            )
        )

    score = _score_from_checks(100, penalties)
    summary = (
        "The tender is likely to attract strong vendor participation."
        if score >= 85
        else "Vendor participation should be acceptable, but clarity improvements would reduce questions."
    )
    return _agent_result(
        agent_name="Vendor Participation Agent",
        role="Estimates vendor question risk and likely market participation from the other health-agent signals.",
        score=score,
        summary=summary,
        reasoning_summary=[
            "Used the specialist health scores as a proxy for vendor confidence.",
            "Reduced participation score where scope, commercial, or compliance ambiguity may increase burden.",
        ],
        signals=[
            f"Scope agent score: {scope_agent.score}",
            f"Commercial agent score: {commercial_agent.score}",
            f"Compliance agent score: {compliance_agent.score}",
        ],
        findings=findings,
    )


def _weak_requirements(findings: list[TenderHealthFinding]) -> list[str]:
    mapping = {
        "Scope": "Scope needs more measurable acceptance criteria.",
        "Deliverables": "Deliverables should include format, owner, and acceptance conditions.",
        "Timeline": "Timeline should include phased milestones and approval gates.",
        "Evaluation": "Technical evaluation parameters are required.",
        "Commercial": "Financial evaluation parameters should be explicit.",
        "Payment": "Payment terms should explain milestone and acceptance linkage.",
        "Eligibility": "Mandatory vendor document list is required.",
        "Compliance": "Mandatory pass/fail criteria should be expanded.",
        "Terms": "Compliance requirements should be listed.",
        "Submission": "Submission controls should be attached.",
        "Vendor Questions": "Clarification risk should be reduced before publication.",
        "Vendor Participation": "Vendor confidence can improve with stronger commercial clarity.",
        "Compliance Burden": "Compliance burden should be clearer for vendors.",
    }
    seen: set[str] = set()
    weak: list[str] = []
    for finding in findings:
        item = mapping.get(finding.area)
        if item and item not in seen:
            seen.add(item)
            weak.append(item)
    return weak


def _ai_committee_agent(
    *,
    agent_name: str,
    score: int,
    focus: str,
    strong_summary: str,
    weak_summary: str,
    recommendation: str,
    findings: list[TenderHealthFinding],
) -> AITenderCommitteeAgentResult:
    return AITenderCommitteeAgentResult(
        agent_name=agent_name,
        score=max(0, min(100, score)),
        focus=focus,
        summary=strong_summary if score >= 85 else weak_summary,
        recommendation=recommendation,
        findings=findings,
    )


def _assess_ai_tender_committee(draft: TenderDraft, form: TenderBuyerForm) -> AITenderCommitteeOutput:
    technical_findings: list[TenderHealthFinding] = []
    technical_penalties: list[int] = []
    technical_text = (
        _text_len(form.technical_requirements)
        + _text_len(form.methodology_requirements)
        + sum(_text_len(c.description) + sum(_text_len(r) for r in c.requirements) for c in draft.scope_of_work.categories)
    )
    tech_params = len(draft.evaluation_criteria.technical_parameters)
    if technical_text < 900:
        technical_penalties.append(12)
        technical_findings.append(_finding("Technical", "Medium", "Technical requirements may be too thin for technical comparison.", "Add measurable technical specifications, acceptance criteria, and implementation constraints.", "Technical content depth is below target."))
    if tech_params < 4:
        technical_penalties.append(10)
        technical_findings.append(_finding("Technical", "Medium", "Technical scoring parameters are limited.", "Define clearer technical evaluation parameters for solution quality, methodology, team, and support.", f"Technical parameters: {tech_params}."))
    if not form.methodology_requirements:
        technical_penalties.append(6)
    technical_score = _score_from_checks(100, technical_penalties)

    commercial_findings: list[TenderHealthFinding] = []
    commercial_penalties: list[int] = []
    financial_params = len(draft.evaluation_criteria.financial_parameters)
    pricing_rules = len(draft.proposal_format.commercial_proposal.pricing_requirements)
    payment_detail = _text_len(draft.payment_terms.payment_basis) + sum(_text_len(x) for x in draft.payment_terms.invoice_requirements)
    if financial_params < 3:
        commercial_penalties.append(10)
        commercial_findings.append(_finding("Commercial", "Medium", "Financial comparison rules need more structure.", "Clarify price breakdown, VAT, currency, assumptions, exclusions, and comparison basis.", f"Financial parameters: {financial_params}."))
    if pricing_rules < 3:
        commercial_penalties.append(8)
        commercial_findings.append(_finding("Commercial", "Low", "Commercial proposal pricing rules are brief.", "Add pricing schedule, total cost ownership, validity, and exception requirements.", f"Pricing rules: {pricing_rules}."))
    if payment_detail < 140:
        commercial_penalties.append(8)
    commercial_score = _score_from_checks(100, commercial_penalties)

    compliance_findings: list[TenderHealthFinding] = []
    compliance_penalties: list[int] = []
    mandatory_docs = len(draft.award_and_contract.mandatory_documents)
    pass_fail = len(draft.evaluation_criteria.mandatory_criteria)
    controls = draft.instructions_to_bidders.submission_controls
    if mandatory_docs < 3:
        compliance_penalties.append(12)
        compliance_findings.append(_finding("Compliance", "Medium", "Mandatory document coverage is limited.", "Require core legal, tax, authorization, and sector documents with validity rules.", f"Mandatory documents: {mandatory_docs}."))
    if pass_fail < 3:
        compliance_penalties.append(10)
        compliance_findings.append(_finding("Compliance", "Medium", "Pass/fail compliance gates are too light.", "Add explicit eligibility, document, submission, conflict, and deadline pass/fail gates.", f"Pass/fail criteria: {pass_fail}."))
    if not controls:
        compliance_penalties.append(8)
    compliance_score = _score_from_checks(100, compliance_penalties)

    delivery_findings: list[TenderHealthFinding] = []
    delivery_penalties: list[int] = []
    deliverables = len(draft.deliverables.deliverables)
    milestones = len(draft.timeline.milestones)
    roles = len(draft.team_requirements.roles)
    if deliverables < 4:
        delivery_penalties.append(10)
        delivery_findings.append(_finding("Delivery", "Medium", "Delivery package needs more named deliverables.", "Add deliverables with format, owner, review cycle, and acceptance rule.", f"Deliverables: {deliverables}."))
    if milestones < 4:
        delivery_penalties.append(10)
        delivery_findings.append(_finding("Delivery", "Medium", "Delivery timeline needs clearer gates.", "Add milestones for kickoff, design, implementation, testing, handover, and acceptance.", f"Milestones: {milestones}."))
    if roles < 2:
        delivery_penalties.append(6)
    delivery_score = _score_from_checks(100, delivery_penalties)

    risk_findings: list[TenderHealthFinding] = []
    risk_penalties: list[int] = []
    for label, score in [
        ("technical", technical_score),
        ("commercial", commercial_score),
        ("compliance", compliance_score),
        ("delivery", delivery_score),
    ]:
        if score < 80:
            risk_penalties.append(7)
            risk_findings.append(_finding("Risk", "Medium", f"{label.title()} readiness is below target.", f"Resolve {label} findings before inviting vendors.", f"{label.title()} score: {score}."))
    if _text_len(draft.instructions_to_bidders.clarifications_process) < 80:
        risk_penalties.append(6)
        risk_findings.append(_finding("Risk", "Low", "Clarification handling may be too brief.", "Clarify question channel, deadline, response publishing, and addenda controls.", "Clarifications process is brief."))
    risk_score = _score_from_checks(100, risk_penalties)

    agents = [
        _ai_committee_agent(
            agent_name="Technical Agent",
            score=technical_score,
            focus="Technical completeness, specifications, methodology, and acceptance criteria.",
            strong_summary="Technical requirements are strong enough for vendor comparison.",
            weak_summary="Technical requirements need more measurable detail before publication.",
            recommendation="Tighten technical specs, methodology requirements, and technical evaluation parameters.",
            findings=technical_findings,
        ),
        _ai_committee_agent(
            agent_name="Commercial Agent",
            score=commercial_score,
            focus="Pricing structure, payment terms, commercial proposal readiness, and comparison basis.",
            strong_summary="Commercial instructions are clear for vendor pricing.",
            weak_summary="Commercial instructions need stronger pricing and payment detail.",
            recommendation="Clarify financial evaluation, pricing schedules, VAT/currency rules, and payment linkage.",
            findings=commercial_findings,
        ),
        _ai_committee_agent(
            agent_name="Compliance Agent",
            score=compliance_score,
            focus="Documents, eligibility, legal gates, submission governance, and approval controls.",
            strong_summary="Compliance controls are ready for buyer review.",
            weak_summary="Compliance controls need stronger document and pass/fail coverage.",
            recommendation="Expand mandatory documents, pass/fail gates, and submission controls.",
            findings=compliance_findings,
        ),
        _ai_committee_agent(
            agent_name="Delivery Agent",
            score=delivery_score,
            focus="Deliverables, milestones, roles, implementation readiness, and handover clarity.",
            strong_summary="Delivery plan is clear enough for implementation planning.",
            weak_summary="Delivery plan needs clearer deliverables, milestones, or roles.",
            recommendation="Add named deliverables, phased milestones, owners, and acceptance gates.",
            findings=delivery_findings,
        ),
        _ai_committee_agent(
            agent_name="Risk Agent",
            score=risk_score,
            focus="Ambiguity, vendor question risk, participation confidence, and publication readiness.",
            strong_summary="Overall tender risk is controlled for buyer review.",
            weak_summary="Tender risk should be reduced before inviting vendors.",
            recommendation="Prioritize the lowest committee scores and clarify vendor question controls.",
            findings=risk_findings,
        ),
    ]
    final_score = min(92, round(
        technical_score * 0.25
        + commercial_score * 0.20
        + compliance_score * 0.20
        + delivery_score * 0.20
        + risk_score * 0.15
    ))
    if final_score >= 85:
        recommendation = "Ready for Buyer-Admin review with normal human approval controls."
    elif final_score >= 70:
        recommendation = "Needs targeted edits before publication; use the committee priorities to regenerate."
    else:
        recommendation = "Needs revision before buyer approval; committee risks are too high for vendor issue."

    all_findings = [finding for agent in agents for finding in agent.findings]
    priorities = []
    for finding in all_findings:
        if finding.recommendation and finding.recommendation not in priorities:
            priorities.append(finding.recommendation)
    if not priorities:
        priorities.append("Maintain committee strengths and complete final Buyer-Admin review.")

    return AITenderCommitteeOutput(
        final_score=final_score,
        final_recommendation=recommendation,
        agents=agents,
        improvement_priorities=priorities[:8],
        committee_reasoning=[
            "Technical, commercial, compliance, delivery, and risk were scored as separate buyer-facing AI committee roles.",
            "Final score uses 25/20/20/20/15 weighting across the five AI agents.",
            "This committee is site-only and supports iterative tender improvement; it is not inserted into the issued PDF.",
        ],
    )


def _aggregate_fallback(agents: list[TenderHealthAgentResult], draft: TenderDraft) -> TenderHealthAggregateOutput:
    scope, commercial, compliance, participation = agents
    quality = round(
        (scope.score * 0.35)
        + (commercial.score * 0.25)
        + (compliance.score * 0.25)
        + (participation.score * 0.15)
    )
    all_findings = [finding for agent in agents for finding in agent.findings]
    strengths = [
        "Tender is assembled into a complete formal RFP structure.",
        "Human approval remains required before publication.",
        "Mushtarry platform submission and record controls are included.",
    ]
    if draft.award_and_contract.mandatory_documents:
        strengths.append("Vendor document requirements are separated from evaluation methodology.")
    if draft.evaluation_criteria.technical_parameters and draft.evaluation_criteria.financial_parameters:
        strengths.append("Technical and financial evaluation parameters are both present.")
    if len(draft.deliverables.deliverables) >= 3:
        strengths.append("Deliverables are defined with enough structure for vendor response planning.")

    if quality >= 85:
        readiness = "Ready for Buyer-Admin review"
        summary = "The health-agent committee rates this tender as strong for MVP review. Buyer-Admin should still confirm commercial values, dates, and final legal wording before publication."
    elif quality >= 70:
        readiness = "Needs buyer review before publication"
        summary = "The health-agent committee rates this tender as usable, but the highlighted agent findings should be strengthened before it is issued to vendors."
    else:
        readiness = "Needs revision before buyer approval"
        summary = "The health-agent committee found material gaps that should be resolved before this tender can credibly support vendor pricing, compliance checks, and award decisions."

    return TenderHealthAggregateOutput(
        tender_quality_score=quality,
        risk_of_vendor_questions=_risk_label(participation.score),
        estimated_vendor_participation=_participation_label(participation.score),
        publish_readiness=readiness,
        strengths=strengths,
        missing_or_weak_requirements=_weak_requirements(all_findings),
        improvement_summary=summary,
        committee_reasoning=[
            "Aggregated specialist health-agent scores using the configured 35/25/25/15 weighting.",
            f"Lowest specialist score: {min(agent.score for agent in agents)}/100.",
            "Final readiness remains advisory and requires Buyer-Admin approval.",
        ],
    )


def _compact_form(form: TenderBuyerForm) -> dict:
    return {
        "tender_title": form.tender_title,
        "buyer_name": form.buyer_name,
        "buyer_description": form.buyer_description,
        "category": form.category,
        "subcategory": form.subcategory,
        "project_objective": form.project_objective,
        "scope_of_work": form.scope_of_work,
        "technical_requirements": form.technical_requirements,
        "methodology_requirements": form.methodology_requirements,
        "deliverables": [d.model_dump(mode="json") for d in form.deliverables],
        "timeline": [t.model_dump(mode="json") for t in form.timeline],
        "roles_and_responsibilities": [r.model_dump(mode="json") for r in form.roles_and_responsibilities],
        "payment_terms": form.payment_terms,
        "estimated_value_sar": form.estimated_value_sar,
        "budget_range": form.budget_range,
        "eligibility_criteria": form.eligibility_criteria,
        "technical_evaluation_parameters": form.technical_evaluation_parameters,
        "financial_evaluation_parameters": form.financial_evaluation_parameters,
        "submission_method": form.submission_method,
        "proposal_format": form.proposal_format,
        "contract_duration": form.contract_duration,
        "warranty_duration": form.warranty_duration,
    }


def _shrink(value: Any, *, max_text: int = 1800, max_items: int = 15) -> Any:
    if isinstance(value, str):
        text = value.strip()
        return text if len(text) <= max_text else text[:max_text].rstrip() + "..."
    if isinstance(value, list):
        return [_shrink(item, max_text=max_text, max_items=max_items) for item in value[:max_items]]
    if isinstance(value, dict):
        return {k: _shrink(v, max_text=max_text, max_items=max_items) for k, v in value.items()}
    return value


def _compact_draft(draft: TenderDraft, area: str) -> dict:
    common = {
        "metadata": draft.metadata.model_dump(mode="json"),
        "tender_data_sheet": draft.tender_data_sheet.model_dump(mode="json"),
        "trace_id": draft.trace_id,
        "ai_generated": draft.ai_generated,
    }
    if area == "scope":
        return _shrink({
            **common,
            "project_overview": draft.project_overview.model_dump(mode="json"),
            "objectives": draft.objectives.model_dump(mode="json"),
            "scope_of_work": draft.scope_of_work.model_dump(mode="json"),
            "deliverables": draft.deliverables.model_dump(mode="json"),
            "timeline": draft.timeline.model_dump(mode="json"),
            "team_requirements": draft.team_requirements.model_dump(mode="json"),
        })
    if area == "commercial":
        return _shrink({
            **common,
            "proposal_format": draft.proposal_format.model_dump(mode="json"),
            "evaluation_criteria": draft.evaluation_criteria.model_dump(mode="json"),
            "payment_terms": draft.payment_terms.model_dump(mode="json"),
            "award_and_contract": draft.award_and_contract.model_dump(mode="json"),
        })
    if area == "compliance":
        return _shrink({
            **common,
            "instructions_to_bidders": draft.instructions_to_bidders.model_dump(mode="json"),
            "award_and_contract": draft.award_and_contract.model_dump(mode="json"),
            "general_terms": draft.general_terms.model_dump(mode="json"),
            "confidentiality": draft.confidentiality,
            "annexures": draft.annexures,
        })
    return _shrink({
        **common,
        "scope_of_work": draft.scope_of_work.model_dump(mode="json"),
        "proposal_format": draft.proposal_format.model_dump(mode="json"),
        "evaluation_criteria": draft.evaluation_criteria.model_dump(mode="json"),
        "payment_terms": draft.payment_terms.model_dump(mode="json"),
        "general_terms": draft.general_terms.model_dump(mode="json"),
    })


def _clean_json_text(raw: str | None) -> str:
    text = (raw or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return text.strip()


def _loads_json(raw: str | None) -> dict:
    parsed = json.loads(_clean_json_text(raw))
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        first_dict = next((item for item in parsed if isinstance(item, dict)), None)
        if first_dict is not None:
            return first_dict
    raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")


def _llm_enabled() -> bool:
    return os.getenv("TENDER_HEALTH_USE_LLM", "1").strip().lower() not in {"0", "false", "no"}


def _run_llm_agent(
    *,
    label: str,
    system_prompt: str,
    payload: dict,
    fallback: TenderHealthAgentResult,
) -> TenderHealthAgentResult:
    if not _llm_enabled():
        return fallback
    try:
        from agents import activity

        activity.set_label(label)
        raw, _usage, _repair_used = chat_json_with_usage(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "/no_think\n"
                        "Evaluate this tender health area. Be concise. Return only JSON.\n\n"
                        + json.dumps(_shrink(payload), ensure_ascii=False, indent=2, default=str)
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=1600,
        )
        parsed = _loads_json(raw)
        parsed["agent_name"] = fallback.agent_name
        parsed["role"] = fallback.role
        return safe_parse(parsed, TenderHealthAgentResult, fallback, f"health_{label}")
    except Exception as e:
        logger.warning("Tender health LLM agent failed; using fallback", extra={"agent": label, "error": str(e)})
        return fallback


def _run_llm_aggregator(
    *,
    draft: TenderDraft,
    agents: list[TenderHealthAgentResult],
    fallback: TenderHealthAggregateOutput,
) -> TenderHealthAggregateOutput:
    if not _llm_enabled():
        return fallback
    payload = {
        "tender_metadata": draft.metadata.model_dump(mode="json"),
        "weighting": {
            "Scope Clarity Agent": 35,
            "Commercial Clarity Agent": 25,
            "Compliance Readiness Agent": 25,
            "Vendor Participation Agent": 15,
        },
        "health_agents": [agent.model_dump(mode="json") for agent in agents],
    }
    try:
        from agents import activity

        activity.set_label("Health aggregator")
        raw, _usage, _repair_used = chat_json_with_usage(
            [
                {"role": "system", "content": PROMPTS["aggregator"]},
                {
                    "role": "user",
                    "content": (
                        "/no_think\n"
                        "Aggregate these tender health agent outputs. Be concise. Return only JSON.\n\n"
                        + json.dumps(_shrink(payload), ensure_ascii=False, indent=2, default=str)
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=1200,
        )
        parsed = _loads_json(raw)
        return safe_parse(parsed, TenderHealthAggregateOutput, fallback, "health_aggregator")
    except Exception as e:
        logger.warning("Tender health aggregator failed; using fallback", extra={"error": str(e)})
        return fallback


def assess_tender_health(draft: TenderDraft, form: TenderBuyerForm) -> TenderHealthScore:
    """Run the LLM-backed tender-health committee and aggregate its recommendation.

    The local LLM is the primary path. Deterministic specialist checks remain as a
    guardrail fallback so tender drafting never fails because health review failed.
    """
    scope_fallback = _scope_fallback(draft, form)
    scope_agent = _run_llm_agent(
        label="Scope health",
        system_prompt=PROMPTS["scope"],
        payload={"buyer_form": _compact_form(form), "tender_draft": _compact_draft(draft, "scope")},
        fallback=scope_fallback,
    )

    commercial_fallback = _commercial_fallback(draft)
    commercial_agent = _run_llm_agent(
        label="Commercial health",
        system_prompt=PROMPTS["commercial"],
        payload={"buyer_form": _compact_form(form), "tender_draft": _compact_draft(draft, "commercial")},
        fallback=commercial_fallback,
    )

    compliance_fallback = _compliance_fallback(draft)
    compliance_agent = _run_llm_agent(
        label="Compliance health",
        system_prompt=PROMPTS["compliance"],
        payload={"buyer_form": _compact_form(form), "tender_draft": _compact_draft(draft, "compliance")},
        fallback=compliance_fallback,
    )

    participation_fallback = _participation_fallback(scope_agent, commercial_agent, compliance_agent)
    participation_agent = _run_llm_agent(
        label="Participation health",
        system_prompt=PROMPTS["participation"],
        payload={
            "buyer_form": _compact_form(form),
            "tender_draft": _compact_draft(draft, "participation"),
            "prior_health_agents": [
                scope_agent.model_dump(mode="json"),
                commercial_agent.model_dump(mode="json"),
                compliance_agent.model_dump(mode="json"),
            ],
        },
        fallback=participation_fallback,
    )

    agents = [scope_agent, commercial_agent, compliance_agent, participation_agent]
    aggregate_fallback = _aggregate_fallback(agents, draft)
    aggregate = _run_llm_aggregator(draft=draft, agents=agents, fallback=aggregate_fallback)
    # A complete template is not a perfect tender. Calibrate model optimism using
    # concrete unresolved findings and retain headroom for buyer review.
    all_findings = [finding for agent in agents for finding in agent.findings]
    ceiling = max(55, 92 - min(24, len(all_findings) * 3))
    if aggregate.tender_quality_score > ceiling:
        aggregate = aggregate.model_copy(update={
            "tender_quality_score": ceiling,
            "improvement_summary": (aggregate.improvement_summary.rstrip() + " Score calibrated against unresolved agent findings."),
        })
    ai_tender_committee = _assess_ai_tender_committee(draft, form)

    return TenderHealthScore(
        tender_quality_score=aggregate.tender_quality_score,
        scope_clarity=scope_agent.score,
        commercial_clarity=commercial_agent.score,
        compliance_readiness=compliance_agent.score,
        vendor_participation_score=participation_agent.score,
        risk_of_vendor_questions=aggregate.risk_of_vendor_questions,
        estimated_vendor_participation=aggregate.estimated_vendor_participation,
        analysis_mode=("LLM_PRIMARY_WITH_DETERMINISTIC_FALLBACK" if _llm_enabled() else "DETERMINISTIC_FALLBACK"),
        publish_readiness=aggregate.publish_readiness,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        health_agents=agents,
        ai_tender_committee=ai_tender_committee,
        strengths=aggregate.strengths,
        findings=all_findings,
        missing_or_weak_requirements=aggregate.missing_or_weak_requirements,
        improvement_summary=aggregate.improvement_summary,
        committee_reasoning=aggregate.committee_reasoning,
    )
