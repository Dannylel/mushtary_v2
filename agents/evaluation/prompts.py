"""
Prompts for EvaluationRankerAgent — VRI + Vendor Fit Score model.
System prompts live in `agents/prompts/` (one prompt per file):
  - evaluation_scoring_system.md
  - evaluation_ranking_system.md
"""
from agents.prompts import load_prompt

SCORE_PROMPT_NAME = "vendor_score_v1"
SCORE_PROMPT_VERSION = "2.2.0"

RANK_PROMPT_NAME = "evaluation_rank_v1"
RANK_PROMPT_VERSION = "2.2.0"

SCORING_SYSTEM_PROMPT = load_prompt("evaluation_scoring_system")
RANKING_SYSTEM_PROMPT = load_prompt("evaluation_ranking_system")


def build_scoring_message(inp) -> str:
    criteria_text = "\n".join(
        f"  - {c.id}: {c.name} (weight: {c.weight_percent}%, mandatory: {c.mandatory}) — {c.description}"
        for c in inp.criteria
    )

    disq = inp.policy.disqualification
    active_disq = [k for k, v in disq.model_dump().items() if v is True]
    if disq.custom_criteria:
        active_disq += [f"custom: {c}" for c in disq.custom_criteria]

    return f"""\
Please evaluate the following vendor submission.

## Tender Policy
Technical Weight: {inp.policy.technical_weight_percent}%
Financial Weight: {inp.policy.financial_weight_percent}%
Pricing Approach: {inp.policy.pricing_approach}
{f"Pricing Formula: {inp.policy.pricing_formula_note}" if inp.policy.pricing_formula_note else ""}
Output Detail: {inp.policy.output_detail}

## Active Disqualification Criteria
{chr(10).join(f"  - {d}" for d in active_disq) or "  None specified"}

## Evaluation Criteria
{criteria_text}

## Vendor VRI
Overall VRI: {inp.vri.overall} ({inp.vri.level})
Category-Specific VRI ({inp.tender_category}): {inp.vri.category_specific}
Delivery Performance: {inp.vri.components.delivery_performance}
Compliance & Licenses: {inp.vri.components.compliance_and_licenses}
Tender Success Rate: {inp.vri.components.tender_success_rate}
AI Risk Signal Score: {inp.vri.components.ai_risk_signals}

## Vendor Submission
Vendor ID: {inp.submission.vendor_id}
Technical Response: {inp.submission.technical_response}
Commercial Summary: {inp.submission.commercial_summary}
Proposed Price (SAR): {inp.submission.proposed_price_sar or "Not stated"}
{f"Market Average Price (SAR): {inp.market_avg_price_sar}" if inp.market_avg_price_sar else ""}
Timeline Commitment: {inp.submission.timeline_commitment_days or "Not stated"} days
Years of Experience: {inp.submission.declared_experience_years or "Not stated"}
Certifications: {", ".join(inp.submission.certifications) or "None stated"}
Submitted Documents: {", ".join(inp.submission.submitted_doc_types) or "None"}

Return the full evaluation JSON.
"""


def build_ranking_message(vendor_scores: list, policy) -> str:
    scores_text = "\n".join(
        f"  - vendor_id: {s.vendor_id}, weighted_total: {s.weighted_total:.1f}, "
        f"fit_score: {s.fit_score_breakdown.final_fit_score:.1f}, "
        f"vri: {s.fit_score_breakdown.vri_component:.1f}, "
        f"risk: {s.risk_level}, "
        f"disqualified: {s.disqualification.disqualified}, "
        f"reasoning: {s.overall_reasoning}, "
        f"missing_requirements: {', '.join(s.missing_requirements) or 'none stated'}"
        for s in vendor_scores
    )
    return f"""\
Please rank the following vendor scores and produce a recommendation.

Output Detail Level: {policy.output_detail}
Technical/Financial Split: {policy.technical_weight_percent}/{policy.financial_weight_percent}

## Vendor Scores
{scores_text}

Return the full ranking JSON.
"""
