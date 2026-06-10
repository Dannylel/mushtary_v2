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
from pathlib import Path

from agents.base import BaseAgent
from agents.llm_config import chat_text
from agents.buyer_form import (
    Deliverable,
    EvaluationCriteria,
    Responsibility,
    TenderBuyerForm,
    TimelineItem,
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

        # Keep input within token limits. Short docs pass through unchanged; long docs go
        # through intra-document retrieval (RAG) so the MIDDLE of the document is no longer
        # silently dropped. Falls back to head+tail truncation if embeddings are unavailable.
        from agents.rag import build_focused_sow_text

        raw_text = build_focused_sow_text(raw_text, max_chars=12000)

        raw_output = chat_text(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(raw_text, hint_category)},
            ],
            temperature=0.2,
            max_tokens=3000,
        )

        form = self._parse_output(raw_output, trace_id)

        logger.info(
            "SoWExtractorAgent complete",
            extra={"trace_id": trace_id, "title": form.tender_title},
        )
        return form

    def _parse_output(self, raw_text: str | None, trace_id: str) -> TenderBuyerForm:
        if not raw_text:
            logger.error("No output from LLM", extra={"trace_id": trace_id})
            return _FALLBACK_FORM

        try:
            text = raw_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError) as e:
            logger.error("JSON parse failed: %s", e, extra={"trace_id": trace_id})
            return _FALLBACK_FORM

        # Coerce nested objects. A single malformed nested dict must not crash extraction
        # — fall back to the safe empty form instead (same contract as guardrails).
        try:
            data["deliverables"] = [
                Deliverable(**d) if isinstance(d, dict) else d
                for d in (data.get("deliverables") or [])
            ]
            data["timeline"] = [
                TimelineItem(**t) if isinstance(t, dict) else t
                for t in (data.get("timeline") or [])
            ]
            data["roles_and_responsibilities"] = [
                Responsibility(**r) if isinstance(r, dict) else r
                for r in (data.get("roles_and_responsibilities") or [])
            ]
            data["evaluation_criteria"] = [
                EvaluationCriteria(**e) if isinstance(e, dict) else e
                for e in (data.get("evaluation_criteria") or [])
            ]
        except Exception as e:
            logger.error("SoW nested coercion failed: %s", e, extra={"trace_id": trace_id})
            return _FALLBACK_FORM

        # Required fields with safe defaults
        data.setdefault("tender_id", "TND-EXTRACTED")
        data.setdefault("buyer_name", "Unknown")
        data.setdefault("buyer_description", data.get("project_objective", ""))
        data.setdefault("payment_terms", "To be agreed")
        data.setdefault("submission_deadline", "To be confirmed")
        data.setdefault("submission_method", "To be confirmed")
        data.setdefault("proposal_format", "Separate Technical and Commercial proposals")
        data.setdefault("confidentiality_required", True)
        data.setdefault("eligibility_criteria", [])
        data.setdefault("required_documents", [])

        return safe_parse(data, TenderBuyerForm, _FALLBACK_FORM, trace_id)
