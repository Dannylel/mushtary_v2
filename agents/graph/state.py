"""Shared state for the LangGraph tender-creation pipeline."""

from __future__ import annotations

from typing import Any, Optional, TypedDict

from agents.buyer_form import TenderBuyerForm
from agents.tender_drafting.schemas import (
    ContextSections,
    ExecutionSections,
    LegalEvalSections,
    ScopeSections,
    TenderDraft,
)


class TenderState(TypedDict, total=False):
    # ── inputs (any one path) ──────────────────────────────────────────────────
    source: str            # "auto" (AI fills form) | "form" (form provided) | "sow"
    seed: Optional[str]    # topic/category hint for the autonomous form generator
    sow_text: Optional[str]
    sow_path: Optional[str]
    buyer_id: str

    # ── the buyer brief (provided or AI-generated) ─────────────────────────────
    form: TenderBuyerForm

    # ── per-section outputs (written in parallel) ──────────────────────────────
    context_sections: ContextSections
    scope_sections: ScopeSections
    execution_sections: ExecutionSections
    legal_eval_sections: LegalEvalSections

    # ── assembled result ───────────────────────────────────────────────────────
    draft: TenderDraft
    tender_intelligence: dict[str, Any]
    consistency_report: dict[str, Any]
    artifact: dict[str, Any]
