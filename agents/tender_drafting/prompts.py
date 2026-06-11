"""
Prompts for TenderDrafterAgent (LEGACY single-call 16-section RFP generator).

NOTE: the active drafting path is the per-section AI agents in `sections/`. This whole-document
prompt is retained for reference / a possible single-call mode. Its text lives in
`agents/prompts/drafting_legacy_full_system.md` (one prompt per file).
"""
from agents.prompts import load_prompt

PROMPT_NAME = "tender_draft_v2"
PROMPT_VERSION = "3.2.0"

SYSTEM_PROMPT = load_prompt("drafting_legacy_full_system")


def build_user_message(inp) -> str:
    f = inp.form

    deliverables_text = "\n".join(
        f"  - {d.name}: {d.description}" + (f" [{d.format}]" if d.format else "")
        for d in (f.deliverables or [])
    ) or "  Not specified"

    timeline_text = "\n".join(
        f"  - {t.milestone}: {t.date}" for t in (f.timeline or [])
    ) or "  Not specified"

    responsibilities_text = "\n".join(
        f"  {r.party}: " + "; ".join(r.responsibilities)
        for r in (f.roles_and_responsibilities or [])
    ) or "  Not specified"

    eval_text = "\n".join(
        f"  - {e.name} ({e.weight}%): {e.description}"
        for e in (f.evaluation_criteria or [])
    ) or "  Not specified"

    return f"""\
Draft a complete enterprise-grade Saudi procurement RFP (16 sections) from the buyer brief below.

TENDER ID: {f.tender_id}
BUYER ORGANISATION: {f.buyer_name}
CATEGORY: {f.category}
SUBCATEGORY: {f.subcategory}

PROJECT OBJECTIVE:
{f.project_objective}

BUYER DESCRIPTION:
{f.buyer_description}

SCOPE OF WORK:
{f.scope_of_work}

DELIVERABLES:
{deliverables_text}

TIMELINE:
{timeline_text}

ROLES & RESPONSIBILITIES:
{responsibilities_text}

TECHNICAL REQUIREMENTS (buyer-specified):
{f.technical_requirements or "Not specified — derive from scope and category standards"}

METHODOLOGY REQUIREMENTS:
{f.methodology_requirements or "Not specified"}

ESTIMATED VALUE (SAR): {f.estimated_value_sar or "Not specified — do not invent a value"}
BUDGET RANGE: {f.budget_range or "Not specified"}
PAYMENT TERMS (buyer preference): {f.payment_terms}
SUBMISSION DEADLINE: {f.submission_deadline}
SUBMISSION METHOD: {f.submission_method}
PROPOSAL FORMAT: {f.proposal_format}
CONTRACT DURATION: {f.contract_duration or "Not specified"}
LOCATION: {f.location or "Kingdom of Saudi Arabia"}
ON-SITE REQUIRED: {f.onsite_required}
LANGUAGE REQUIREMENTS: {f.language_requirements or "Arabic and English"}

BUYER-SPECIFIED ELIGIBILITY:
{chr(10).join(f"  - {e}" for e in (f.eligibility_criteria or []))}

BUYER-SPECIFIED REQUIRED DOCUMENTS:
{chr(10).join(f"  - {d}" for d in (f.required_documents or []))}

BUYER-SPECIFIED EVALUATION CRITERIA:
{eval_text}
MINIMUM SCORE: {f.minimum_score or 70}%

PERFORMANCE BOND REQUIRED: {f.performance_bond_required}
CONFIDENTIALITY REQUIRED: {f.confidentiality_required}

Use all buyer-provided information as the foundation. Generate the complete 16-section RFP JSON. \
Return only the JSON — no markdown fences, no commentary.
"""
