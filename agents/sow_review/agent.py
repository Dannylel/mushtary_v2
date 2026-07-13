from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.llm_config import chat_json_text
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

The rewritten_scope must be substantive and organize the available facts into: purpose and
outcome; included workstreams and boundaries; vendor activities; concrete deliverables with
minimum contents; buyer/vendor responsibilities; quality review and acceptance evidence;
reporting/governance; dependencies, assumptions, exclusions, and handover. Where a necessary
fact is absent, write a precise buyer-confirmation requirement rather than silently inventing it.
Each gap and recommendation must identify the affected phrase/topic and the practical effect on
vendor pricing, staffing, delivery, compliance, or acceptance.
"""


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
    rewritten = (
        f"The scope of work for {title} includes the planning, execution, delivery, "
        "testing, handover, and support activities required to meet the buyer's stated "
        "objectives. The vendor shall review the buyer requirements, propose a delivery "
        "methodology, provide the required personnel and resources, submit deliverables "
        "for buyer review, address comments, and complete final handover through the "
        "Mushtarry platform.\n\n"
        f"Buyer-provided scope:\n{text or 'To be completed by the buyer.'}"
    )
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
                max_tokens=3400,
            )
            return SoWReviewResult.model_validate(_extract_json(raw))
        except Exception as e:
            logger.warning("SoW review failed; using fallback: %s", e)
            return _fallback(project_name, scope_text)
