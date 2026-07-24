from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.llm_config import chat_json_text, chat_text
from agents.observability import emit
from agents.prompts import GLOBAL_QUALITY_STANDARD

logger = logging.getLogger(__name__)


class SoWReviewResult(BaseModel):
    score: int = Field(ge=0, le=100)
    readiness: str
    summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    rewritten_scope: str


SYSTEM_PROMPT = GLOBAL_QUALITY_STANDARD + "\n\n" + """\
You are a senior Saudi-market procurement scope-of-work reviewer.

Evaluate the buyer's draft scope before it is used to generate a formal tender.
Focus on whether vendors can price, plan, staff, and deliver the work with minimal clarification.

Return ONLY valid JSON with this exact shape:
{
  "score": 0-100,
  "readiness": "weak" | "needs_review" | "ready",
  "summary": "short plain-English assessment",
  "strengths": ["max 4 bullets"],
  "gaps": ["max 6 bullets"],
  "recommendations": ["max 6 bullets"],
  "rewritten_scope": "professional tender-ready scope of work"
}

The rewrite must preserve the buyer's intent, add missing structure, remove ambiguity,
and sound like a formal tender document. Do not invent highly specific budgets, dates,
brand names, or quantities unless the buyer provided them.

The rewritten_scope must be a DETAILED, DENSE procurement-ready document, not an executive
summary. Write 800-1,400 words unless the buyer supplied a substantially longer scope. Use
numbered headings for: 1) purpose and intended outcomes; 2) scope and workstreams; 3) vendor
activities and methodology; 4) deliverables and their minimum contents; 5) buyer and vendor
responsibilities; 6) quality assurance, testing, and acceptance evidence; 7) reporting and
governance; 8) dependencies and assumptions; 9) exclusions and change control; and 10) handover
and support. Make every heading useful with concrete, priceable requirements grounded in the
buyer brief. Where a necessary fact is absent, write a precise buyer-confirmation requirement
rather than silently inventing it. Do not reduce, omit, or summarize buyer-provided detail.
Each gap and recommendation must identify the affected phrase/topic and the practical effect on
vendor pricing, staffing, delivery, compliance, or acceptance.
"""


def _detailed_scope(project_name: str, scope_text: str) -> str:
    """A dense, safe fallback when a local model returns an overly brief rewrite."""
    title = project_name.strip() or "the project"
    source = (scope_text or "Buyer requirements to be confirmed.").strip()
    return f"""1. Purpose and intended outcomes
The purpose of {title} is to procure a qualified vendor to plan, manage, deliver, test, document, and hand over the buyer's stated requirements in a controlled and measurable manner. The required outcome is a complete, operational, buyer-accepted result that can be supported after handover. The vendor shall use the buyer brief as the baseline and shall identify any ambiguity that could affect price, staffing, timing, quality, or acceptance before commencing the affected work.

2. Scope and workstreams
The scope includes all activities explicitly described in the buyer brief, reproduced below as the governing project context:\n{source}\nThe vendor shall convert this context into a coordinated work breakdown covering mobilisation, requirements confirmation, detailed planning, execution, quality control, testing, issue resolution, documentation, training or knowledge transfer where applicable, and final handover. The proposal shall clearly distinguish included activities, optional items, assumptions, dependencies, and exclusions.

3. Vendor activities and methodology
The vendor shall appoint an accountable project lead and provide suitably qualified personnel, tools, supervision, and resources. Before execution, the vendor shall submit a delivery methodology and work plan showing workstreams, sequence, resources, interfaces, risks, controls, and proposed review points. The vendor shall coordinate access, protect buyer operations, maintain an issue and risk log, manage corrective actions, and obtain buyer confirmation before proceeding where a buyer decision or dependency is required.

4. Deliverables and minimum contents
At a minimum, the vendor shall provide: a mobilisation and project plan; a detailed implementation or service-delivery plan; progress and quality reports; evidence of testing, inspections, or verification relevant to the scope; an up-to-date register of assumptions, issues, risks, and decisions; final as-built or handover documentation where applicable; training or knowledge-transfer materials where applicable; and a final completion and handover report. Each deliverable shall state its purpose, minimum contents, owner, submission format, review period, acceptance evidence, and any dependency on buyer input.

5. Responsibilities
The buyer shall provide available baseline information, nominated points of contact, required access or approvals, and timely review comments. The vendor remains responsible for planning and performing the work, coordinating its personnel and subcontractors, maintaining quality, protecting information and assets, correcting non-conforming work, and submitting complete evidence for acceptance. Neither party may treat an unclear requirement as approved; clarification requests shall be raised through the buyer-approved channel.

6. Quality assurance, testing, and acceptance
The vendor shall operate documented quality controls appropriate to the work and shall inspect or test each material output before submission. Acceptance shall be based on agreed requirements, completeness, functionality or service performance where relevant, required documentation, and closure of material defects. The buyer may accept, conditionally accept with observations, or reject a deliverable. A rejected or conditionally accepted deliverable shall be corrected and resubmitted without reducing the buyer's review rights. Specific acceptance thresholds not stated in the buyer brief shall be proposed by the vendor for buyer confirmation.

7. Reporting and governance
The vendor shall provide regular status reports at a frequency agreed during mobilisation. Reports shall cover completed work, next activities, delivery status, risks, issues, decisions required, changes, quality results, and forecast impact on the plan. The vendor project lead shall attend governance or progress meetings requested by the buyer and shall maintain action records. Material risks, delays, safety or security concerns, and changes affecting price or scope shall be escalated promptly.

8. Dependencies and assumptions
The vendor shall identify all dependencies on buyer information, site access, third parties, approvals, existing systems, utilities, data, or operational windows. Assumptions must be explicit, reasonable, and traceable to the buyer brief. If an assumption proves incorrect, the vendor shall notify the buyer with the impact, options, and recommended mitigation before making a change to the agreed work.

9. Exclusions and change control
No activity is excluded merely because it was not separately itemised if it is reasonably necessary to deliver and evidence the stated scope. Any proposed exclusion, deviation, or additional work shall be clearly listed in the proposal. Changes to scope, price, timeline, deliverables, or acceptance criteria require documented buyer approval before implementation. The vendor shall not proceed on verbal change instructions.

10. Handover and support
Before final completion, the vendor shall submit all required deliverables, resolve or document outstanding items, provide relevant records and credentials through the approved process, and support an orderly transition to the buyer or its nominated representative. The final handover report shall confirm delivered scope, acceptance status, open items, support obligations, and any recommended next actions. Warranty, maintenance, or post-handover support requirements not stated in the buyer brief shall be proposed for buyer confirmation rather than assumed."""


def _needs_expansion(source: str, rewritten: str) -> bool:
    minimum_words = max(650, min(1000, len((source or "").split()) * 2))
    has_structure = len(re.findall(r"(?:^|\n)\d+[.)]", rewritten or "")) >= 6
    return len((rewritten or "").split()) < minimum_words or not has_structure


def _expand_rewrite_with_ai(project_name: str, source: str, draft: str) -> str | None:
    """Ask the model for a full expansion before using the deterministic safety net."""
    expansion_prompt = f"""Expand the draft Scope of Work below into a detailed, dense, procurement-ready document.
Return only the rewritten Scope of Work, without commentary or JSON.

Requirements:
- Preserve every relevant fact from the buyer brief and the draft; never shorten it.
- Write 800-1,400 words with numbered headings 1 through 10: purpose/outcomes; scope/workstreams;
  vendor activities/methodology; deliverables; responsibilities; quality/testing/acceptance;
  reporting/governance; dependencies/assumptions; exclusions/change control; handover/support.
- Make requirements concrete and priceable, but do not invent dates, amounts, brands, quantities,
  laws, or acceptance thresholds. State "subject to buyer confirmation" where information is absent.

Project name: {project_name or "Not provided"}

Buyer brief:
{source}

Initial AI draft to expand:
{draft}
"""
    expanded = chat_text(
        [{"role": "system", "content": "You are a senior procurement Scope of Work writer. Follow the requested structure exactly."},
         {"role": "user", "content": expansion_prompt}],
        temperature=0.2,
        max_tokens=5600,
    )
    return (expanded or "").strip() or None


def _ensure_detailed_rewrite(project_name: str, source: str, rewritten: str) -> str:
    if not _needs_expansion(source, rewritten):
        return rewritten.strip()
    return _detailed_scope(project_name, source)


def _fallback(project_name: str, scope_text: str) -> SoWReviewResult:
    text = (scope_text or "").strip()
    gaps = []
    if len(text) < 300:
        gaps.append("Scope is short and may not give vendors enough detail to price accurately.")
    if not re.search(r"deliverable|handover|report|document|training|support", text, re.I):
        gaps.append("Deliverables are not clearly listed.")
    if not re.search(r"timeline|duration|phase|week|month|day", text, re.I):
        gaps.append("Timeline, phases, or duration are not clearly stated.")
    if not re.search(r"acceptance|approve|testing|criteria|kpi", text, re.I):
        gaps.append("Acceptance criteria or quality expectations are not explicit.")

    score = max(45, 82 - len(gaps) * 10)
    title = project_name.strip() or "the project"
    rewritten = _detailed_scope(title, text)
    return SoWReviewResult(
        score=score,
        readiness="ready" if score >= 80 else "needs_review",
        summary="Initial automated review completed. The scope can be improved before tender drafting.",
        strengths=["The buyer has provided an initial project direction."],
        gaps=gaps or ["No major gaps detected in the basic scope text."],
        recommendations=[
            "Confirm deliverables, acceptance criteria, responsibilities, and timeline before publication.",
            "Avoid brand-specific or overly narrow requirements unless technically justified.",
        ],
        rewritten_scope=rewritten,
    )


def _extract_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        raise ValueError("empty LLM response")
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM response was not a JSON object")
    return data


class SoWReviewAgent(BaseAgent):
    artifact_type = "SOW_REVIEW"

    def run(self, project_name: str, scope_text: str) -> SoWReviewResult:  # type: ignore[override]
        from agents import activity

        activity.set_label("SoW reviewer")
        prompt = f"""\
Project name:
{project_name or "Not provided"}

Buyer draft scope of work:
{scope_text or "Not provided"}
"""
        try:
            raw = chat_json_text(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.25,
            max_tokens=5600,
            )
            result = SoWReviewResult.model_validate(_extract_json(raw))
            if _needs_expansion(scope_text, result.rewritten_scope):
                activity.publish("info", "Initial rewrite was concise; expanding it into a detailed tender-ready scope.", label="SoW reviewer")
                expanded = _expand_rewrite_with_ai(project_name, scope_text, result.rewritten_scope)
                if expanded:
                    result.rewritten_scope = expanded
            result.rewritten_scope = _ensure_detailed_rewrite(project_name, scope_text, result.rewritten_scope)
            return result
        except Exception as e:
            logger.warning("SoW review failed; using fallback (%s)", type(e).__name__)
            emit(
                "ai.fallback.applied", level="WARNING",
                reason="sow_review_failed", error_type=type(e).__name__,
                result_mode="DETERMINISTIC_FALLBACK",
            )
            return _fallback(project_name, scope_text)
