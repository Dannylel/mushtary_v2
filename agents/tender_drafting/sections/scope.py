"""
ScopeSectionAgent — AI-generated, category-agnostic.

Generates Project Overview, Objectives, and Scope of Work for ANY procurement
category by reasoning over the buyer's brief. Nothing here is hardcoded to a
specific sector; the buyer form is the only source of facts.

On LLM failure it falls back to a minimal draft derived directly from the buyer's
own inputs (never invented), so the PDF is never blank.
"""

from __future__ import annotations

from typing import Any

from agents.buyer_form import TenderBuyerForm
from agents.tender_drafting.schemas import (
    Objectives,
    ProjectOverview,
    ScopeCategory,
    ScopeOfWork,
    ScopeSections,
)

from .base import BaseSectionAgent
from agents.prompts import load_prompt

SYSTEM_PROMPT = load_prompt("drafting_scope_system")


def _build_user_message(form: TenderBuyerForm) -> str:
    deliverables = "\n".join(
        f"  - {d.name}: {d.description}" + (f" [{d.format}]" if d.format else "")
        for d in (form.deliverables or [])
    ) or "  Not specified"

    return f"""\
Draft the Project Overview, Objectives, and Scope of Work for this tender.

BUYER: {form.buyer_name}
BUYER DESCRIPTION: {form.buyer_description}
CATEGORY: {form.category} / {form.subcategory}
LOCATION: {form.location or "Kingdom of Saudi Arabia"}
LANGUAGE: {form.language_requirements or "Arabic and English"}

PROJECT OBJECTIVE:
{form.project_objective}

SCOPE OF WORK (buyer brief):
{form.scope_of_work}

DELIVERABLES:
{deliverables}

TECHNICAL REQUIREMENTS (buyer-specified):
{form.technical_requirements or "Not specified — derive from scope and category"}

METHODOLOGY REQUIREMENTS:
{form.methodology_requirements or "Not specified"}

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


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        first = next((item for item in value if isinstance(item, dict)), None)
        return first or {}
    return {}


def _scope_fallback(form: TenderBuyerForm) -> ScopeSections:
    """Minimal draft built ONLY from buyer inputs — used if the LLM output is unusable."""
    return ScopeSections(
        project_overview=ProjectOverview(
            project_introduction=(
                f"{form.buyer_name} is issuing this tender for '{form.tender_title}' "
                f"under the category '{form.category} / {form.subcategory}'."
            ),
            background=form.buyer_description or "",
            context=form.project_objective or "",
        ),
        objectives=Objectives(
            business_goals=[form.project_objective] if form.project_objective else [],
            expected_outcomes=[d.description for d in (form.deliverables or []) if d.description],
            kpis=[],
        ),
        scope_of_work=ScopeOfWork(
            categories=[
                ScopeCategory(
                    name="Scope of Work",
                    description=form.scope_of_work or "As described in the buyer brief.",
                    requirements=list(form.eligibility_criteria or []),
                )
            ],
            phases=[],
            general_requirements=[],
        ),
    )


class ScopeSectionAgent(BaseSectionAgent):
    def run(self, form: TenderBuyerForm) -> ScopeSections:
        # Ground on approved precedent for this category/objective (empty string if the
        # knowledge base is unpopulated — drafting then proceeds exactly as before).
        ref = self._reference_context(
            f"scope of work and objectives for {form.category} / {form.subcategory}: "
            f"{form.project_objective}"
        )
        user = f"{ref}\n{_build_user_message(form)}" if ref else _build_user_message(form)

        data = self._generate(SYSTEM_PROMPT, user, max_tokens=2800)
        if not data:
            return _scope_fallback(form)

        fb = _scope_fallback(form)

        po = _as_dict(data.get("project_overview"))
        project_overview = ProjectOverview(
            project_introduction=_as_str(po.get("project_introduction"), fb.project_overview.project_introduction),
            background=_as_str(po.get("background"), fb.project_overview.background),
            context=_as_str(po.get("context"), fb.project_overview.context),
        )

        ob = _as_dict(data.get("objectives"))
        objectives = Objectives(
            business_goals=_as_str_list(ob.get("business_goals")) or fb.objectives.business_goals,
            expected_outcomes=_as_str_list(ob.get("expected_outcomes")) or fb.objectives.expected_outcomes,
            kpis=_as_str_list(ob.get("kpis")),
        )

        sow = _as_dict(data.get("scope_of_work"))
        categories = []
        for c in (sow.get("categories") or []):
            if not isinstance(c, dict):
                continue
            categories.append(
                ScopeCategory(
                    name=_as_str(c.get("name"), "Work Category"),
                    description=_as_str(c.get("description")),
                    requirements=_as_str_list(c.get("requirements")),
                )
            )

        phases = []
        from agents.tender_drafting.schemas import ScopePhase

        for p in (sow.get("phases") or []):
            if not isinstance(p, dict):
                continue
            phases.append(
                ScopePhase(
                    phase=_as_str(p.get("phase"), "Phase"),
                    activities=_as_str_list(p.get("activities")),
                )
            )

        scope_of_work = ScopeOfWork(
            categories=categories or fb.scope_of_work.categories,
            phases=phases,
            general_requirements=_as_str_list(sow.get("general_requirements")),
        )

        return ScopeSections(
            project_overview=project_overview,
            objectives=objectives,
            scope_of_work=scope_of_work,
        )
