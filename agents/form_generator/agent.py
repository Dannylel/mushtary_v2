"""
FormGeneratorAgent — autonomous buyer-form synthesis (no user input required).

Given only a short seed (a topic, a category, or nothing at all), the LLM invents a
complete, internally-consistent TenderBuyerForm — every field from Input Fields.docx —
so the tender-drafting pipeline can produce a full DRAFT tender with zero human input.

This is the "no user input" mode: until a real buyer fills the form, this agent stands
in for the buyer. Everything it produces is still a DRAFT and still flows through the
same human-approval gate downstream.
"""
import json
import logging

from agents.base import BaseAgent
from agents.buyer_form import (
    Deliverable,
    EvaluationCriteria,
    Responsibility,
    SubmissionControls,
    TenderBuyerForm,
    TimelineItem,
    VendorDocumentRequirement,
)
from agents.categories import ALL_CATEGORIES, CATEGORIES
from agents.guardrails import safe_parse
from agents.llm_config import chat_text
from agents.prompts import load_prompt

logger = logging.getLogger(__name__)

PROMPT_NAME = "form_generator_v1"
PROMPT_VERSION = "1.2.0"

SYSTEM_PROMPT = load_prompt("form_generator_system")


def _build_user_message(seed: str | None) -> str:
    categories_hint = ", ".join(ALL_CATEGORIES)
    if seed:
        ask = f"Generate the buyer brief for this seed/topic: {seed}"
    else:
        ask = "Generate a buyer brief for any realistic Saudi tender of your choice."
    return f"""\
{ask}

Available platform categories (choose one and a matching subcategory):
{categories_hint}

Return only the JSON object.
"""


def _fallback_form(seed: str | None) -> TenderBuyerForm:
    from agents.tender_ids import next_tender_id

    title = (seed or "General Services").strip().title()
    category = ALL_CATEGORIES[0]
    subcategory = (CATEGORIES.get(category) or ["General"])[0]
    return TenderBuyerForm(
        tender_title=f"{title} Tender",
        tender_id=next_tender_id(),
        buyer_name="Mushtarry Auto-Generated Buyer",
        buyer_description=f"Auto-generated draft buyer brief for: {title}.",
        submission_deadline="To be confirmed",
        category=category,
        subcategory=subcategory,
        project_objective=f"Procure {title.lower()} services to meet the buyer's operational needs.",
        scope_of_work=f"Provision of {title.lower()} as required by the buyer.",
        deliverables=[Deliverable(name="Final Deliverable", description="Completed scope of work", format="PDF")],
        timeline=[TimelineItem(milestone="Project Handover", date="Day 90 from contract award")],
        roles_and_responsibilities=[
            Responsibility(party="Buyer", responsibilities=["Provide access and approvals."]),
            Responsibility(party="Vendor", responsibilities=["Deliver the agreed scope."]),
        ],
        payment_terms="Milestone-based payment subject to buyer acceptance.",
        eligibility_criteria=["Valid Saudi commercial registration and required documents."],
        submission_method="Mushtarry platform only",
        proposal_format="Separate Technical and Commercial proposals",
        confidentiality_required=True,
    )


def _coerce(data: dict) -> dict:
    data["deliverables"] = [
        Deliverable(**d) if isinstance(d, dict) else d for d in (data.get("deliverables") or [])
    ]
    data["timeline"] = [
        TimelineItem(**t) if isinstance(t, dict) else t for t in (data.get("timeline") or [])
    ]
    data["roles_and_responsibilities"] = [
        Responsibility(**r) if isinstance(r, dict) else r
        for r in (data.get("roles_and_responsibilities") or [])
    ]
    data["evaluation_criteria"] = [
        EvaluationCriteria(**e) if isinstance(e, dict) else e
        for e in (data.get("evaluation_criteria") or [])
    ]
    for key in ("mandatory_documents", "conditional_documents", "optional_documents",
                "sector_specific_documents", "prestige_documents"):
        if data.get(key):
            data[key] = [
                VendorDocumentRequirement(**d) if isinstance(d, dict) else d for d in data[key]
            ]
    if isinstance(data.get("submission_controls"), dict):
        data["submission_controls"] = SubmissionControls(**data["submission_controls"])

    # Tender reference is ALWAYS platform-assigned (TND-ID-NNNN) — never model-invented.
    from agents.tender_ids import next_tender_id

    data["tender_id"] = next_tender_id()

    # Required-without-default fields get safe placeholders if the model omitted them.
    data.setdefault("buyer_name", "Mushtarry Auto-Generated Buyer")
    data.setdefault("buyer_description", data.get("project_objective", ""))
    data.setdefault("submission_deadline", "To be confirmed")
    data.setdefault("payment_terms", "Milestone-based payment subject to buyer acceptance.")
    data.setdefault("submission_method", "Mushtarry platform only")
    data.setdefault("proposal_format", "Separate Technical and Commercial proposals")
    data.setdefault("eligibility_criteria", [])
    return data


class FormGeneratorAgent(BaseAgent):
    artifact_type = "FORM_GENERATION"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    def generate(self, seed: str | None = None) -> TenderBuyerForm:
        trace_id = self.new_trace_id()
        logger.info("FormGeneratorAgent started", extra={"trace_id": trace_id, "seed": seed})

        # Label for the live activity console.
        from agents import activity

        activity.set_label("Form generator")

        raw = chat_text(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(seed)},
            ],
            temperature=0.8,
            max_tokens=3000,
        )
        form = self._parse(raw, seed, trace_id)
        logger.info("FormGeneratorAgent complete", extra={"trace_id": trace_id, "title": form.tender_title})
        return form

    # BaseAgent requires run(); expose generate() through it too.
    def run(self, seed: str | None = None):  # type: ignore[override]
        return self.generate(seed)

    def _parse(self, raw: str | None, seed: str | None, trace_id: str) -> TenderBuyerForm:
        fallback = _fallback_form(seed)
        if not raw:
            return fallback
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError) as e:
            logger.error("Form generation JSON parse failed: %s", e, extra={"trace_id": trace_id})
            return fallback
        try:
            data = _coerce(data)
        except Exception as e:  # malformed nested objects
            logger.error("Form coercion failed: %s", e, extra={"trace_id": trace_id})
            return fallback
        return safe_parse(data, TenderBuyerForm, fallback, trace_id)
