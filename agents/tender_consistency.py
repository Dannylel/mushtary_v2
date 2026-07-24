"""Consistency and compliance gate between tender drafting and publication.

Buyer-entered controls are hard facts and are reconciled deterministically.  The LLM
agent reviews only semantic consistency and explains issues that cannot be reduced to
simple field equality.
"""
from __future__ import annotations

import json
import re
from typing import Any

from agents.buyer_form import TenderBuyerForm
from agents.llm_config import chat_json_text
from agents.prompts import GLOBAL_QUALITY_STANDARD
from agents.observability import emit
from agents.tender_drafting.schemas import TenderDraft, TenderDeliverable, TenderMilestone


def _hard_fact_reconcile(draft: TenderDraft, form: TenderBuyerForm) -> list[dict[str, str]]:
    repairs: list[dict[str, str]] = []
    if form.deliverables:
        expected = [TenderDeliverable(name=d.name, description=d.description, format=d.format) for d in form.deliverables]
        if [d.name for d in draft.deliverables.deliverables] != [d.name for d in expected]:
            draft.deliverables.deliverables = expected
            repairs.append({"area": "Deliverables", "issue": "Replaced generated deliverable names with buyer-approved rows."})
    if form.timeline:
        expected = [TenderMilestone(phase="", milestone=t.milestone, target_date=t.date) for t in form.timeline]
        if [(m.milestone, m.target_date) for m in draft.timeline.milestones] != [(m.milestone, m.target_date) for m in expected]:
            draft.timeline.milestones = expected
            repairs.append({"area": "Timeline", "issue": "Replaced generated milestone dates with buyer-approved rows."})
    if form.saudization_required:
        # The form carries a policy flag, not a percentage. Never allow invented percentages.
        clean = "The vendor shall comply with applicable Saudi Saudization and local-content requirements."
        draft.team_requirements.saudization_note = clean
        draft.award_and_contract.saudization_requirements = clean
    return repairs


def _deterministic_findings(draft: TenderDraft) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    texts = [
        draft.team_requirements.saudization_note,
        draft.award_and_contract.saudization_requirements,
        draft.timeline.total_duration,
        *[m.target_date for m in draft.timeline.milestones],
    ]
    percentages = sorted(set(re.findall(r"\b\d+(?:\.\d+)?%", " ".join(texts))))
    if len(percentages) > 1:
        findings.append({"area": "Cross-section facts", "severity": "High", "issue": f"Conflicting percentage values remain: {', '.join(percentages)}."})
    if not draft.deliverables.deliverables:
        findings.append({"area": "Deliverables", "severity": "High", "issue": "No deliverables are available for publication."})
    if not draft.timeline.milestones:
        findings.append({"area": "Timeline", "severity": "High", "issue": "No timeline milestones are available for publication."})
    return findings


def _agent_review(draft: TenderDraft, form: TenderBuyerForm) -> tuple[list[dict[str, str]], str]:
    payload = {
        "buyer_facts": {
            "title": form.tender_title, "category": form.category, "location": form.location,
            "duration": form.contract_duration, "deliverables": [d.model_dump() for d in form.deliverables],
            "timeline": [t.model_dump() for t in form.timeline], "saudization_required": form.saudization_required,
        },
        "draft": {
            "deliverables": [d.model_dump() for d in draft.deliverables.deliverables],
            "milestones": [m.model_dump() for m in draft.timeline.milestones],
            "saudization": [draft.team_requirements.saudization_note, draft.award_and_contract.saudization_requirements],
            "language": draft.general_terms.language_requirements,
            "payment": draft.payment_terms.payment_basis,
        },
    }
    system = GLOBAL_QUALITY_STANDARD + """
You are the Tender Consistency and Compliance Agent. Compare buyer facts with the assembled tender.
Identify only material unresolved contradictions, invented facts, language mismatch, or missing publication controls.
Do not rewrite the tender and do not invent facts. Return only JSON:
{"findings":[{"area":"...","severity":"High|Medium|Low","issue":"..."}]}."""
    try:
        raw = chat_json_text(
            [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            temperature=0.0, max_tokens=900,
        )
        match = re.search(r"\{.*\}", raw or "", re.S)
        data: Any = json.loads(match.group(0)) if match else {}
        items = data.get("findings", []) if isinstance(data, dict) else []
        return [item for item in items if isinstance(item, dict) and item.get("issue")], "agent"
    except Exception as exc:
        emit(
            "ai.fallback.applied",
            level="WARNING",
            reason="consistency_agent_failed",
            error_type=type(exc).__name__,
            result_mode="DETERMINISTIC_FALLBACK",
        )
        return [], "deterministic_fallback"


def reconcile_tender(draft: TenderDraft, form: TenderBuyerForm) -> tuple[TenderDraft, dict[str, Any]]:
    repairs = _hard_fact_reconcile(draft, form)
    findings = _deterministic_findings(draft)
    agent_findings, mode = _agent_review(draft, form)
    findings.extend(agent_findings)
    has_blocker = any(str(item.get("severity", "")).lower() == "high" for item in findings)
    return draft, {
        "status": "BLOCKED" if has_blocker else "READY_FOR_BUYER_REVIEW",
        "analysis_mode": mode,
        "repairs_applied": repairs,
        "findings": findings,
        "publication_rule": "High-severity consistency findings must be resolved before Buyer-Admin publication.",
    }
