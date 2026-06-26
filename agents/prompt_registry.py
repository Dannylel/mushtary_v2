"""
Prompt Registry — single source of truth for all prompt versions.
Every prompt must be registered here before use in production.

Schema per entry:
    name:        unique identifier
    version:     semver string
    intent:      what this prompt does in plain English
    agent:       which agent uses it
    inputs:      list of input field names the prompt expects
    outputs:     list of output field names the prompt produces
    model:       intended model
    notes:       any caveats or gotchas
"""

REGISTRY: dict[str, dict] = {
    "vendor_validation_v1": {
        "name": "vendor_validation_v1",
        "version": "1.1.0",
        "intent": (
            "Reason over vendor registration data and tool results "
            "to produce a structured validation outcome."
        ),
        "agent": "VendorValidationAgent",
        "inputs": [
            "cr_number",
            "legal_name_ar",
            "legal_name_en",
            "selected_categories",
            "documents",
            "tool_results",       # injected after tool calls complete
        ],
        "outputs": [
            "outcome",
            "cr_status",
            "name_match",
            "name_match_confidence",
            "category_alignment",
            "is_duplicate",
            "missing_documents",
            "flags",
            "vendor_message",
            "admin_note",
        ],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "Tool use loop — may call up to 4 tools before final answer.",
    },
    "tender_draft_v2": {
        "name": "tender_draft_v2",
        "version": "3.2.0",
        "intent": (
            "Generate a full RFP tender draft from a TenderBuyerForm via four parallel "
            "section prompts (context, scope, execution, legal/eval), assembled into one "
            "TenderDraft aligned with Saudi Arabia procurement standards."
        ),
        "agent": "TenderDrafterAgent / LangGraph tender pipeline",
        "inputs": ["form (TenderBuyerForm — all fields)"],
        "outputs": [
            "context_sections",
            "scope_sections",
            "execution_sections",
            "legal_eval_sections",
            "assembled TenderDraft",
        ],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": (
            "Section system prompts live in agents/prompts/drafting_*_system.md. "
            "Scope and legal/eval sections additionally receive reference excerpts "
            "retrieved from the tender knowledge base (agents/rag) when available. "
            "v3.0.0 = 4-section parallel architecture; v1 single-call prompt retired."
        ),
    },
    "sow_extract_v1": {
        "name": "sow_extract_v1",
        "version": "1.1.0",
        "intent": (
            "Extract a structured TenderBuyerForm from raw SoW/RFP document text "
            "so the drafting pipeline can run from an uploaded PDF."
        ),
        "agent": "SoWExtractorAgent",
        "inputs": ["document_text", "hint_category"],
        "outputs": ["TenderBuyerForm (all extractable fields)"],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": (
            "Long documents pass through intra-document RAG (agents/rag/sow_retrieval) "
            "to keep field-relevant chunks; falls back to head+tail truncation."
        ),
    },
    "form_generator_v1": {
        "name": "form_generator_v1",
        "version": "1.2.0",
        "intent": (
            "Autonomously invent a complete, internally-consistent TenderBuyerForm "
            "from a short seed (or nothing), standing in for a real buyer."
        ),
        "agent": "FormGeneratorAgent",
        "inputs": ["seed (optional topic string)"],
        "outputs": ["TenderBuyerForm (all fields)"],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "Output is still a DRAFT input to the same human-approval gate downstream.",
    },
    "vendor_score_v1": {
        "name": "vendor_score_v1",
        "version": "2.1.0",
        "intent": (
            "Score a single vendor submission against tender evaluation criteria. "
            "Runs in isolation — agent never sees other vendors' submissions."
        ),
        "agent": "EvaluationRankerAgent",
        "inputs": [
            "tender_id",
            "vendor_id",
            "criteria",
            "submission_summary",
        ],
        "outputs": [
            "vendor_id",
            "scores_by_criterion",
            "total_score",
            "reasoning",
            "missing_requirements",
        ],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "One task per vendor. Ranking aggregation runs as a separate step.",
    },
    "evaluation_rank_v1": {
        "name": "evaluation_rank_v1",
        "version": "2.1.0",
        "intent": (
            "Aggregate per-vendor scores into a ranked recommendation list "
            "with an explainability summary for the buyer."
        ),
        "agent": "EvaluationRankerAgent",
        "inputs": ["vendor_scores"],
        "outputs": [
            "ranked_list",
            "recommendation",
            "explainability_summary",
        ],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "Buyer must approve this output before any award is recorded.",
    },
    "tender_health_scope_v1": {
        "name": "tender_health_scope_v1",
        "version": "1.0.0",
        "intent": "Review tender scope clarity, deliverables, milestones, and responsibility clarity.",
        "agent": "TenderHealthCommittee / Scope Clarity Agent",
        "inputs": ["buyer_form", "tender_draft"],
        "outputs": ["score", "risk_level", "summary", "reasoning_summary", "signals", "findings"],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "Advisory only; falls back to deterministic scoring if the local model fails.",
    },
    "tender_health_commercial_v1": {
        "name": "tender_health_commercial_v1",
        "version": "1.0.0",
        "intent": "Review pricing clarity, payment terms, commercial proposal requirements, bonds, and evaluation commercial logic.",
        "agent": "TenderHealthCommittee / Commercial Clarity Agent",
        "inputs": ["buyer_form", "tender_draft"],
        "outputs": ["score", "risk_level", "summary", "reasoning_summary", "signals", "findings"],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "Advisory only; falls back to deterministic scoring if the local model fails.",
    },
    "tender_health_compliance_v1": {
        "name": "tender_health_compliance_v1",
        "version": "1.0.0",
        "intent": "Review eligibility, document requirements, submission governance, compliance terms, and approval controls.",
        "agent": "TenderHealthCommittee / Compliance Readiness Agent",
        "inputs": ["buyer_form", "tender_draft"],
        "outputs": ["score", "risk_level", "summary", "reasoning_summary", "signals", "findings"],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "Advisory only; falls back to deterministic scoring if the local model fails.",
    },
    "tender_health_participation_v1": {
        "name": "tender_health_participation_v1",
        "version": "1.0.0",
        "intent": "Estimate vendor question risk and likely participation based on tender clarity and burden.",
        "agent": "TenderHealthCommittee / Vendor Participation Agent",
        "inputs": ["buyer_form", "tender_draft", "specialist_health_agent_outputs"],
        "outputs": ["score", "risk_level", "summary", "reasoning_summary", "signals", "findings"],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "Advisory only; falls back to deterministic scoring if the local model fails.",
    },
    "tender_health_aggregator_v1": {
        "name": "tender_health_aggregator_v1",
        "version": "1.0.0",
        "intent": "Aggregate specialist health-agent scores into final tender quality, readiness, and improvement summary.",
        "agent": "TenderHealthCommittee / Aggregator Agent",
        "inputs": ["specialist_health_agent_outputs", "tender_metadata"],
        "outputs": ["tender_quality_score", "publish_readiness", "committee_reasoning", "strengths", "missing_or_weak_requirements"],
        "model": "local (configurable via LLM_MODEL env var)",
        "notes": "Uses weighted specialist scores; advisory only; falls back to deterministic aggregation if the local model fails.",
    },
}


def get(name: str) -> dict:
    if name not in REGISTRY:
        raise KeyError(f"Prompt '{name}' not found in registry. Register it before use.")
    return REGISTRY[name]
