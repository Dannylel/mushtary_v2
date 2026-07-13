"""
ExecutionSectionAgent — AI-generated, category-agnostic.

Generates Deliverables, Timeline, and Team Requirements for ANY category.

Facts the buyer entered (deliverable names/descriptions/formats, milestone dates,
contract duration) are preserved verbatim and never invented; the AI supplies the
surrounding professional content (work-order process, deadlines, phases, team roles,
escalation matrix). Falls back to a buyer-derived draft on LLM failure.
"""

from __future__ import annotations

from typing import Any

from agents.buyer_form import TenderBuyerForm
from agents.tender_drafting.schemas import (
    DeliverablesSection,
    EscalationTier,
    ExecutionSections,
    TeamRequirements,
    TeamRole,
    TenderDeliverable,
    TenderMilestone,
    Timeline,
)

from .base import BaseSectionAgent
from agents.prompts import load_prompt

SYSTEM_PROMPT = load_prompt("drafting_execution_system")


def _build_user_message(form: TenderBuyerForm) -> str:
    deliverables = "\n".join(
        f"  - {d.name}: {d.description}" + (f" [{d.format}]" if d.format else "")
        for d in (form.deliverables or [])
    ) or "  Not specified"

    timeline = "\n".join(
        f"  - {t.milestone}: {t.date}" for t in (form.timeline or [])
    ) or "  Not specified"

    responsibilities = "\n".join(
        f"  {r.party}: " + "; ".join(r.responsibilities)
        for r in (form.roles_and_responsibilities or [])
    ) or "  Not specified"

    return f"""\
Draft the Deliverables, Timeline, and Team Requirements for this tender.

CATEGORY: {form.category} / {form.subcategory}
PROJECT OBJECTIVE: {form.project_objective}
SCOPE OF WORK:
{form.scope_of_work}

TECHNICAL / METHODOLOGY REQUIREMENTS:
{form.technical_requirements or "Derive operational requirements from the SOW"}
{form.methodology_requirements or "Derive a suitable delivery method from the SOW"}

CONTRACT DURATION: {form.contract_duration or "Not specified"}
SAUDIZATION REQUIRED: {form.saudization_required}
MINIMUM YEARS EXPERIENCE: {form.minimum_years_experience or "Not specified"}
MINIMUM SIMILAR PROJECTS: {form.minimum_similar_projects or "Not specified"}

DELIVERABLES (use these names exactly):
{deliverables}

BUYER TIMELINE / MILESTONES (use these dates exactly):
{timeline}

ROLES & RESPONSIBILITIES (buyer brief):
{responsibilities}

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


def _buyer_deliverables(form: TenderBuyerForm, deadlines: dict | None = None) -> list[TenderDeliverable]:
    deadlines = deadlines or {}
    out: list[TenderDeliverable] = []
    for d in (form.deliverables or []):
        out.append(
            TenderDeliverable(
                name=d.name,
                description=d.description,
                format=d.format,
                deadline_note=_as_str(deadlines.get(d.name), "As per approved project plan"),
            )
        )
    return out


def _buyer_milestones(form: TenderBuyerForm) -> list[TenderMilestone]:
    return [
        TenderMilestone(phase="", milestone=t.milestone, target_date=t.date)
        for t in (form.timeline or [])
    ]


def _buyer_team(form: TenderBuyerForm) -> list[TeamRole]:
    roles: list[TeamRole] = []
    exp = (
        f"Minimum {form.minimum_years_experience} years of relevant experience."
        if form.minimum_years_experience
        else "As required by the buyer."
    )
    for r in (form.roles_and_responsibilities or []):
        roles.append(
            TeamRole(
                position=f"{r.party} team",
                responsibilities="; ".join(r.responsibilities),
                minimum_experience=exp,
            )
        )
    return roles


_GENERIC_ESCALATION = [
    EscalationTier(level="First Escalation", trigger_delay="1-2 calendar days", contact_role="Vendor Project Manager and Buyer Focal Point"),
    EscalationTier(level="Second Escalation", trigger_delay="3-5 calendar days", contact_role="Vendor and Buyer Department Managers"),
    EscalationTier(level="Final Escalation", trigger_delay="More than 5 calendar days", contact_role="Vendor and Buyer Executive Management"),
]


def _execution_fallback(form: TenderBuyerForm) -> ExecutionSections:
    return ExecutionSections(
        deliverables=DeliverablesSection(
            work_order_process=[
                "The buyer may issue Work Orders describing tasks, outputs, timelines, and acceptance criteria.",
                "The vendor shall respond within three (3) business days with team lead, duration, and cost breakdown where applicable.",
                "No work shall commence until the relevant Work Order is approved by the buyer.",
                "Each Work Order shall be closed with completed deliverables, buyer acceptance, and a valid invoice.",
            ],
            deliverables=_buyer_deliverables(form),
            approval_process="All deliverables are subject to buyer review and written approval.",
            reporting_requirements=[
                "Periodic project status reports covering progress, risks, and issues.",
                "Final project completion report upon delivery of all outputs.",
            ],
            escalation_tiers=list(_GENERIC_ESCALATION),
        ),
        timeline=Timeline(
            total_duration=form.contract_duration or "As per the approved project plan",
            project_phases=[],
            milestones=_buyer_milestones(form),
        ),
        team_requirements=TeamRequirements(
            roles=_buyer_team(form),
            saudization_note=(
                "The vendor shall comply with applicable Saudization and local-content requirements."
                if form.saudization_required
                else "Saudization is not specifically required unless mandated by applicable law."
            ),
        ),
    )


class ExecutionSectionAgent(BaseSectionAgent):
    def run(self, form: TenderBuyerForm) -> ExecutionSections:
        data = self._generate(SYSTEM_PROMPT, _build_user_message(form), max_tokens=4000)
        if not data:
            return _execution_fallback(form)

        fb = _execution_fallback(form)

        dl = _as_dict(data.get("deliverables"))
        deadlines = dl.get("deliverable_deadlines") if isinstance(dl.get("deliverable_deadlines"), dict) else {}

        escalation = []
        for t in (dl.get("escalation_tiers") or []):
            if isinstance(t, dict):
                escalation.append(
                    EscalationTier(
                        level=_as_str(t.get("level"), "Escalation"),
                        trigger_delay=_as_str(t.get("trigger_delay")),
                        contact_role=_as_str(t.get("contact_role")),
                    )
                )

        deliverables = DeliverablesSection(
            work_order_process=_as_str_list(dl.get("work_order_process")) or fb.deliverables.work_order_process,
            # Deliverable list stays sourced from the buyer (facts); AI only supplies deadline notes.
            deliverables=_buyer_deliverables(form, deadlines) or fb.deliverables.deliverables,
            approval_process=_as_str(dl.get("approval_process"), fb.deliverables.approval_process),
            reporting_requirements=_as_str_list(dl.get("reporting_requirements")) or fb.deliverables.reporting_requirements,
            escalation_tiers=escalation or fb.deliverables.escalation_tiers,
        )

        tl = _as_dict(data.get("timeline"))
        ai_milestones = []
        for m in (tl.get("milestones") or []):
            if isinstance(m, dict):
                ai_milestones.append(
                    TenderMilestone(
                        phase=_as_str(m.get("phase")),
                        milestone=_as_str(m.get("milestone"), "Milestone"),
                        target_date=_as_str(m.get("target_date")),
                    )
                )
        # Prefer buyer-provided milestones (truthful dates); use AI's only if the buyer gave none.
        milestones = _buyer_milestones(form) or ai_milestones
        timeline = Timeline(
            total_duration=_as_str(tl.get("total_duration"), fb.timeline.total_duration),
            project_phases=_as_str_list(tl.get("project_phases")),
            milestones=milestones,
        )

        tr = _as_dict(data.get("team_requirements"))
        roles = []
        for r in (tr.get("roles") or []):
            if isinstance(r, dict):
                roles.append(
                    TeamRole(
                        position=_as_str(r.get("position"), "Role"),
                        responsibilities=_as_str(r.get("responsibilities")),
                        minimum_experience=_as_str(r.get("minimum_experience")),
                    )
                )
        team_requirements = TeamRequirements(
            roles=roles or fb.team_requirements.roles,
            saudization_note=_as_str(tr.get("saudization_note"), fb.team_requirements.saudization_note),
        )

        return ExecutionSections(
            deliverables=deliverables,
            timeline=timeline,
            team_requirements=team_requirements,
        )
