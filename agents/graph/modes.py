"""
Mode dispatch — run any single agent alone, or the full pipeline together.

Default mode is "full" (the LangGraph tender-creation pipeline). Every other mode runs
exactly one agent/node in isolation, which is useful for testing and for the lifecycle
stages (vendor validation, evaluation) that aren't part of the drafting graph.
"""

from __future__ import annotations

from typing import Any

from agents.buyer_form import TenderBuyerForm
from agents.form_generator.agent import FormGeneratorAgent
from agents.sow_extractor.agent import SoWExtractorAgent
from agents.tender_drafting.sections.context import ContextSectionAgent
from agents.tender_drafting.sections.execution import ExecutionSectionAgent
from agents.tender_drafting.sections.legal_eval import LegalEvalSectionAgent
from agents.tender_drafting.sections.scope import ScopeSectionAgent

from .pipeline import run_tender_pipeline

SECTION_AGENTS = {
    "context": ContextSectionAgent,
    "scope": ScopeSectionAgent,
    "execution": ExecutionSectionAgent,
    "legal": LegalEvalSectionAgent,
}

MODES = [
    "full",       # default: form_source → 4 sections → assemble
    "form",       # autonomous buyer-form generation
    "extract",    # SOW/RFP document → buyer form
    "context", "scope", "execution", "legal",  # single drafting sections
    "validate",   # vendor validation (tool-use loop)
    "score",      # evaluate a single vendor
    "rank",       # rank pre-scored vendors
]


def _resolve_form(form: TenderBuyerForm | None, seed: str | None) -> TenderBuyerForm:
    """A form for a single-section run: use the provided one, else AI-generate it."""
    if form is not None:
        return form
    return FormGeneratorAgent().generate(seed)


def run_mode(mode: str, *, seed: str | None = None, form: TenderBuyerForm | None = None,
             sow_text: str | None = None, sow_path: str | None = None,
             payload: Any = None) -> Any:
    """Run one mode. Returns Pydantic models / dicts depending on the mode."""
    mode = (mode or "full").lower()

    if mode == "full":
        if form is not None:
            return run_tender_pipeline(form=form, seed=seed)
        if sow_text or sow_path:
            return run_tender_pipeline(source="sow", sow_text=sow_text, sow_path=sow_path, seed=seed)
        return run_tender_pipeline(source="auto", seed=seed)

    if mode == "form":
        return FormGeneratorAgent().generate(seed)

    if mode == "extract":
        agent = SoWExtractorAgent()
        if sow_path:
            return agent.extract_from_pdf(sow_path)
        return agent.extract_from_text(sow_text or "")

    if mode in SECTION_AGENTS:
        resolved = _resolve_form(form, seed)
        return SECTION_AGENTS[mode]().run(resolved)

    if mode == "validate":
        from agents.vendor_validation.agent import VendorValidationAgent
        from agents.vendor_validation.schemas import VendorValidationInput

        if payload is None:
            raise ValueError("validate mode requires a VendorValidationInput payload (--input)")
        data = payload if isinstance(payload, VendorValidationInput) else VendorValidationInput.model_validate(payload)
        return VendorValidationAgent().run(data)

    if mode == "score":
        from agents.evaluation.agent import EvaluationRankerAgent
        from agents.evaluation.schemas import VendorScoringInput

        if payload is None:
            raise ValueError("score mode requires a VendorScoringInput payload (--input)")
        data = payload if isinstance(payload, VendorScoringInput) else VendorScoringInput.model_validate(payload)
        return EvaluationRankerAgent().run(data)

    if mode == "rank":
        from agents.evaluation.agent import EvaluationRankerAgent
        from agents.evaluation.schemas import RankingInput

        if payload is None:
            raise ValueError("rank mode requires a RankingInput payload (--input)")
        data = payload if isinstance(payload, RankingInput) else RankingInput.model_validate(payload)
        return EvaluationRankerAgent().rank(data)

    raise ValueError(f"Unknown mode '{mode}'. Valid modes: {', '.join(MODES)}")
