"""
SoWExtractorAgent — reads a SoW or RFP PDF and returns a populated TenderBuyerForm.

Flow:
  1. Extract raw text from PDF using PyMuPDF
  2. Send text to LLM with extraction prompt
  3. Parse JSON response into TenderBuyerForm
  4. Return TenderBuyerForm ready for TenderDrafterAgent
"""
import json
import logging
import re
from pathlib import Path

from agents.base import BaseAgent
from agents.llm_config import chat_json_text
from agents.buyer_form import (
    Deliverable,
    EvaluationCriteria,
    Responsibility,
    TenderBuyerForm,
    TimelineItem,
    VendorDocumentRequirement,
)
from agents.guardrails import safe_parse

from .prompts import PROMPT_NAME, PROMPT_VERSION, SYSTEM_PROMPT, build_user_message

logger = logging.getLogger(__name__)

_FALLBACK_FORM = TenderBuyerForm(
    tender_title="Extracted Tender (please review and complete)",
    tender_id="TND-EXTRACTED",
    buyer_name="Unknown",
    buyer_description="SoW extraction failed — please fill in manually.",
    category="Other",
    subcategory="Other / Not Listed Above",
    project_objective="",
    scope_of_work="",
    deliverables=[],
    timeline=[],
    roles_and_responsibilities=[],
    payment_terms="To be agreed",
    eligibility_criteria=[],
    required_documents=[],
    evaluation_criteria=[],
    submission_deadline="To be confirmed",
    submission_method="To be confirmed",
    proposal_format="Separate Technical and Commercial proposals",
    confidentiality_required=True,
)


def _clean_text(text: str | None, limit: int = 1800) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text[:limit].rstrip()


def _text_value(value, default: str | None = None) -> str | None:
    if value is None:
        return default
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return "; ".join(items) if items else default
    text = str(value).strip()
    return text or default


def _list_value(value, default: list | None = None) -> list:
    if value is None:
        return list(default or [])
    if isinstance(value, list):
        return [item for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else list(default or [])


def _project_name_from_text(raw_text: str) -> str:
    match = re.search(r"Project Name:\s*(.+)", raw_text, flags=re.I)
    if match:
        return match.group(1).strip()[:120]
    match = re.search(r"(?:Scope of Work|Project Description):\s*(.+)", raw_text, flags=re.I)
    if match:
        return match.group(1).strip()[:120]
    first = _clean_text(raw_text, 90)
    return first or "Guided Scope Tender"


def _derive_deliverables(scope_text: str) -> list[Deliverable]:
    text = scope_text.lower()
    deliverables = [
        Deliverable(
            name="Mobilization and Work Plan",
            description="Detailed mobilization plan covering staffing, equipment, schedule, methodology, and service readiness.",
            format="PDF",
        ),
        Deliverable(
            name="Implementation / Service Delivery Plan",
            description="Operational plan explaining how the vendor will deliver the scope, manage quality, and comply with buyer requirements.",
            format="PDF",
        ),
        Deliverable(
            name="Progress and Quality Reports",
            description="Periodic reports covering completed work, issues, corrective actions, staffing, and quality performance.",
            format="PDF",
        ),
        Deliverable(
            name="Final Completion and Handover Report",
            description="Final report confirming completion of the required scope and closure of outstanding observations.",
            format="PDF",
        ),
    ]
    if any(word in text for word in ("clean", "hygiene", "school", "facility")):
        deliverables.insert(
            2,
            Deliverable(
                name="Cleaning Schedule and Quality Checklist",
                description="Area-by-area cleaning schedule with inspection checklist, acceptance criteria, and evidence of completed activities.",
                format="PDF/Excel",
            ),
        )
    return deliverables


def _default_mandatory_documents() -> list[VendorDocumentRequirement]:
    return [
        VendorDocumentRequirement(
            name="Commercial Registration Certificate",
            requirement_level="mandatory",
            category="Legal",
            issuing_authority="Ministry of Commerce",
        ),
        VendorDocumentRequirement(
            name="VAT Registration Certificate",
            requirement_level="mandatory",
            category="Tax",
            applicability="If applicable",
            issuing_authority="ZATCA",
        ),
        VendorDocumentRequirement(
            name="National Address Certificate",
            requirement_level="mandatory",
            category="Legal",
        ),
        VendorDocumentRequirement(
            name="IBAN Certificate / Bank Letter",
            requirement_level="mandatory",
            category="Banking",
        ),
        VendorDocumentRequirement(
            name="GOSI Certificate",
            requirement_level="mandatory",
            category="Compliance",
            applicability="Where employees will be assigned to the project",
            issuing_authority="GOSI",
        ),
        VendorDocumentRequirement(
            name="Saudization / Nitaqat Certificate",
            requirement_level="mandatory",
            category="Compliance",
            issuing_authority="Ministry of Human Resources and Social Development",
        ),
    ]


def _fallback_from_text(raw_text: str, trace_id: str) -> TenderBuyerForm:
    from agents.tender_ids import next_tender_id

    scope = _clean_text(raw_text, 3000)
    project_name = _project_name_from_text(raw_text)
    return TenderBuyerForm(
        tender_title=f"{project_name} Tender",
        tender_id=next_tender_id(),
        buyer_name="Buyer Admin",
        buyer_description=f"Buyer-provided guided scope for {project_name}.",
        category="General Services",
        subcategory="Other / Not Listed Above",
        project_objective=f"Procure qualified vendor services to deliver {project_name} in accordance with the approved scope, quality standards, and Mushtarry platform controls.",
        scope_of_work=scope,
        deliverables=_derive_deliverables(scope),
        timeline=[
            TimelineItem(milestone="Mobilization and kickoff", date="Within 5 business days from contract award"),
            TimelineItem(milestone="Service delivery / implementation period", date="As per buyer-approved work plan"),
            TimelineItem(milestone="Final acceptance and handover", date="Upon completion of all accepted deliverables"),
        ],
        roles_and_responsibilities=[
            Responsibility(party="Buyer", responsibilities=["Confirm requirements, provide approvals, and review submitted deliverables through Mushtarry."]),
            Responsibility(party="Vendor", responsibilities=["Provide qualified resources, deliver the approved scope, submit reports, and correct rejected deliverables."]),
        ],
        technical_requirements=scope,
        methodology_requirements="Vendor shall submit a detailed methodology, staffing plan, quality control approach, and risk mitigation plan aligned with the scope.",
        payment_terms="Milestone-based payment after buyer acceptance of submitted deliverables.",
        eligibility_criteria=[
            "Valid Saudi commercial registration relevant to the scope.",
            "Demonstrated experience delivering similar services in the Kingdom of Saudi Arabia.",
            "Compliance with applicable Saudi labor, tax, Saudization, and sector requirements.",
        ],
        mandatory_documents=_default_mandatory_documents(),
        required_documents=[doc.name for doc in _default_mandatory_documents()],
        mandatory_disqualification_criteria=[
            "Failure to submit all mandatory documents.",
            "Submission after the official deadline.",
            "Material non-compliance with the scope of work or submission format.",
            "Undisclosed conflict of interest.",
        ],
        technical_evaluation_parameters=[
            "Understanding of the scope of work and buyer objectives.",
            "Quality and completeness of the proposed methodology.",
            "Relevant experience and qualifications of proposed team.",
            "Realism of implementation plan, timeline, and quality controls.",
        ],
        financial_evaluation_parameters=[
            "Total price and itemized cost breakdown.",
            "Value for money against the proposed methodology and resources.",
            "Clarity of assumptions, exclusions, and recurring costs.",
        ],
        submission_deadline="To be confirmed by Buyer Admin",
        submission_method="Mushtarry platform only",
        proposal_format="Separate Technical and Commercial proposals",
        contract_duration="To be confirmed by Buyer Admin",
        confidentiality_required=True,
    )


def _normalize_extraction_data(data: dict, source_text: str, fallback: TenderBuyerForm) -> dict:
    """Accept common local-model aliases instead of throwing away useful extraction."""
    data = dict(data)
    data.setdefault("tender_title", data.get("title") or f"{fallback.tender_title}")
    data.setdefault("buyer_description", _text_value(data.get("description"), fallback.buyer_description))
    data.setdefault("project_objective", _text_value(data.get("objective") or data.get("description"), fallback.project_objective))
    data.setdefault("scope_of_work", _text_value(data.get("scope") or data.get("scope_of_services"), fallback.scope_of_work))
    data.setdefault("technical_requirements", _text_value(data.get("technical_requirements") or data.get("requirements") or data.get("specifications") or data.get("required_qualifications"), fallback.technical_requirements))
    data.setdefault("methodology_requirements", _text_value(data.get("methodology"), fallback.methodology_requirements))
    data.setdefault("eligibility_criteria", data.get("eligibility_criteria") or data.get("required_qualifications") or fallback.eligibility_criteria)
    data.setdefault("required_documents", data.get("required_documents") or data.get("required_licenses") or fallback.required_documents)
    data.setdefault("mandatory_documents", data.get("mandatory_documents") or [d.model_dump() for d in fallback.mandatory_documents])
    data.setdefault("mandatory_disqualification_criteria", fallback.mandatory_disqualification_criteria)
    data.setdefault("technical_evaluation_parameters", data.get("technical_evaluation_parameters") or fallback.technical_evaluation_parameters)
    data.setdefault("financial_evaluation_parameters", data.get("financial_evaluation_parameters") or fallback.financial_evaluation_parameters)
    data.setdefault("category", data.get("category") or fallback.category)
    data.setdefault("subcategory", data.get("subcategory") or fallback.subcategory)
    data.setdefault("buyer_name", data.get("buyer_name") or data.get("buyer") or fallback.buyer_name)
    data.setdefault("payment_terms", data.get("payment_terms") or fallback.payment_terms)
    data.setdefault("submission_deadline", data.get("submission_deadline") or fallback.submission_deadline)
    data.setdefault("submission_method", data.get("submission_method") or fallback.submission_method)
    data.setdefault("proposal_format", data.get("proposal_format") or fallback.proposal_format)
    data.setdefault("contract_duration", data.get("contract_duration") or data.get("duration") or fallback.contract_duration)
    data.setdefault("confidentiality_required", True)

    for key in ("buyer_description", "project_objective", "scope_of_work", "technical_requirements", "methodology_requirements", "payment_terms"):
        data[key] = _text_value(data.get(key), getattr(fallback, key, None))
    data["eligibility_criteria"] = _list_value(data.get("eligibility_criteria"), fallback.eligibility_criteria)
    data["required_documents"] = _list_value(data.get("required_documents"), fallback.required_documents)

    if not isinstance(data.get("deliverables"), list) or not data.get("deliverables"):
        data["deliverables"] = [d.model_dump() for d in _derive_deliverables(data.get("scope_of_work") or source_text)]
    else:
        data["deliverables"] = [
            {
                "name": _text_value(item.get("name"), "Deliverable") if isinstance(item, dict) else _text_value(item, "Deliverable"),
                "description": _text_value(item.get("description"), "Details to be confirmed during buyer review.") if isinstance(item, dict) else _text_value(item, "Details to be confirmed during buyer review."),
                "format": _text_value(item.get("format")) if isinstance(item, dict) else None,
            }
            for item in data["deliverables"]
        ]
    if not isinstance(data.get("timeline"), list) or not data.get("timeline"):
        data["timeline"] = [t.model_dump() for t in fallback.timeline]
    else:
        data["timeline"] = [
            {
                "milestone": _text_value(item.get("milestone") or item.get("name"), "Project milestone") if isinstance(item, dict) else _text_value(item, "Project milestone"),
                "date": _text_value(item.get("date") or item.get("target_date"), "As per buyer-approved plan") if isinstance(item, dict) else "As per buyer-approved plan",
            }
            for item in data["timeline"]
        ]
    if not isinstance(data.get("roles_and_responsibilities"), list) or not data.get("roles_and_responsibilities"):
        data["roles_and_responsibilities"] = [r.model_dump() for r in fallback.roles_and_responsibilities]
    return data


class SoWExtractorAgent(BaseAgent):
    artifact_type = "SOW_EXTRACTION"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    def extract_from_pdf(
        self,
        pdf_path: str | Path,
        hint_category: str | None = None,
    ) -> TenderBuyerForm:
        """Read a PDF file and extract a TenderBuyerForm from its contents."""
        raw_text = self._read_pdf(pdf_path)
        return self._extract(raw_text, hint_category)

    def run(
        self,
        raw_text: str,
        hint_category: str | None = None,
    ) -> TenderBuyerForm:  # type: ignore[override]
        """BaseAgent entry point for text-based SoW extraction."""
        return self.extract_from_text(raw_text, hint_category)

    def extract_from_text(
        self,
        raw_text: str,
        hint_category: str | None = None,
    ) -> TenderBuyerForm:
        """Extract a TenderBuyerForm from pre-read document text."""
        return self._extract(raw_text, hint_category)

    # ── internals ─────────────────────────────────────────────────────────────

    def _read_pdf(self, pdf_path: str | Path) -> str:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise RuntimeError("PyMuPDF not installed — run: pip install PyMuPDF")

        doc = fitz.open(str(pdf_path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(pages)

    def _extract(self, raw_text: str, hint_category: str | None) -> TenderBuyerForm:
        trace_id = self.new_trace_id()
        logger.info("SoWExtractorAgent started", extra={"trace_id": trace_id})

        # Label for the live activity console.
        from agents import activity

        activity.set_label("SoW extractor")

        # Keep input within token limits. Short docs pass through unchanged; long docs go
        # through intra-document retrieval (RAG) so the MIDDLE of the document is no longer
        # silently dropped. Falls back to head+tail truncation if embeddings are unavailable.
        from agents.rag import build_focused_sow_text

        raw_text = build_focused_sow_text(raw_text, max_chars=12000)

        raw_output = chat_json_text(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(raw_text, hint_category)},
            ],
            temperature=0.2,
            max_tokens=4200,
        )

        form = self._parse_output(raw_output, trace_id, raw_text)

        logger.info(
            "SoWExtractorAgent complete",
            extra={"trace_id": trace_id, "title": form.tender_title},
        )
        return form

    def _parse_output(self, raw_text: str | None, trace_id: str, source_text: str = "") -> TenderBuyerForm:
        fallback = _fallback_from_text(source_text, trace_id) if source_text else _FALLBACK_FORM
        if not raw_text:
            logger.error("No output from LLM", extra={"trace_id": trace_id})
            return fallback

        try:
            text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.S).strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                text = text[start:end + 1]
            data = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError) as e:
            logger.error("JSON parse failed: %s", e, extra={"trace_id": trace_id})
            return fallback

        if isinstance(data, list):
            data = next((item for item in data if isinstance(item, dict)), {})
        if not isinstance(data, dict):
            logger.error("SoW extraction JSON root must be object", extra={"trace_id": trace_id})
            return fallback

        data = _normalize_extraction_data(data, source_text, fallback)

        # Coerce nested objects. A single malformed nested dict must not crash extraction
        # — fall back to the safe empty form instead (same contract as guardrails).
        try:
            data["deliverables"] = [
                Deliverable(**d) if isinstance(d, dict) else Deliverable(name=str(d), description=str(d), format=None)
                for d in (data.get("deliverables") or [])
            ]
            data["timeline"] = [
                TimelineItem(**t) if isinstance(t, dict) else TimelineItem(milestone=str(t), date="As per approved project plan")
                for t in (data.get("timeline") or [])
            ]
            data["roles_and_responsibilities"] = [
                Responsibility(**r) if isinstance(r, dict) else Responsibility(party="Vendor", responsibilities=[str(r)])
                for r in (data.get("roles_and_responsibilities") or [])
            ]
            data["evaluation_criteria"] = [
                EvaluationCriteria(**e) if isinstance(e, dict) else e
                for e in (data.get("evaluation_criteria") or [])
            ]
        except Exception as e:
            logger.error("SoW nested coercion failed: %s", e, extra={"trace_id": trace_id})
            return fallback

        # The platform assigns its own tender reference (TND-ID-NNNN) — the source
        # document's reference belongs to the issuing organisation, not Mushtarry.
        from agents.tender_ids import next_tender_id

        data["tender_id"] = next_tender_id()

        # Required fields with safe defaults
        data.setdefault("buyer_name", "Unknown")
        data.setdefault("buyer_description", data.get("project_objective", ""))
        data.setdefault("payment_terms", "To be agreed")
        data.setdefault("submission_deadline", "To be confirmed")
        data.setdefault("submission_method", "To be confirmed")
        data.setdefault("proposal_format", "Separate Technical and Commercial proposals")
        data.setdefault("confidentiality_required", True)
        data.setdefault("eligibility_criteria", [])
        data.setdefault("required_documents", [])

        return safe_parse(data, TenderBuyerForm, fallback, trace_id)
