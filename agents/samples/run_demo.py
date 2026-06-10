"""
Demo script — runs the full evaluation flow against the IT Infrastructure mock data.
Use this to test and tune the evaluation agent before real vendor submissions arrive.

Usage:
    python agents/samples/run_demo.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from agents.evaluation.agent import EvaluationRankerAgent
from agents.evaluation.schemas import (
    EvaluationCriterion,
    RankingInput,
    SubmissionSummary,
    TenderPolicy,
    VRIComponents,
    VRIScore,
    VendorScoringInput,
    DisqualificationCriteria,
)

SAMPLES_DIR = Path(__file__).parent


def load_samples():
    with open(SAMPLES_DIR / "it_infrastructure_tender.json") as f:
        tender = json.load(f)
    with open(SAMPLES_DIR / "vendor_submissions.json") as f:
        submissions = json.load(f)
    return tender, submissions


def build_policy(tender: dict) -> TenderPolicy:
    p = tender["policy"]
    d = p["disqualification"]
    return TenderPolicy(
        technical_weight_percent=p["technical_weight_percent"],
        financial_weight_percent=p["financial_weight_percent"],
        pricing_approach=p["pricing_approach"],
        output_detail=p["output_detail"],
        disqualification=DisqualificationCriteria(**d),
    )


def build_criteria(tender: dict) -> list[EvaluationCriterion]:
    return [EvaluationCriterion(**c) for c in tender["criteria"]]


def build_vri(vri_data: dict) -> VRIScore:
    return VRIScore(
        vendor_id=vri_data["vendor_id"],
        overall=vri_data["overall"],
        category_specific=vri_data["category_specific"],
        level=vri_data["level"],
        components=VRIComponents(**vri_data["components"]),
    )


def build_submission(sub_data: dict) -> SubmissionSummary:
    return SubmissionSummary(**sub_data)


def print_separator():
    print("\n" + "─" * 70 + "\n")


def main():
    # Local-first: the agent resolves the model from agents/llm_config.py (Ollama by
    # default) — no API key is required to run this demo.
    print("Loading mock data...")
    tender, submissions_data = load_samples()

    policy = build_policy(tender)
    criteria = build_criteria(tender)
    agent = EvaluationRankerAgent()

    print(f"\nTender: {tender['title']}")
    print(f"Vendors: {len(submissions_data['submissions'])}")
    print(f"Policy: {policy.technical_weight_percent}/{policy.financial_weight_percent} tech/financial split")
    print(f"Pricing approach: {policy.pricing_approach}")
    print_separator()

    # ── Step 1: Score each vendor in isolation ─────────────────────────────
    vendor_scores = []

    for vendor_data in submissions_data["submissions"]:
        vendor_name = vendor_data["vendor_name"]
        print(f"Scoring: {vendor_name} (VRI: {vendor_data['vri']['category_specific']})")

        payload = VendorScoringInput(
            tender_id=tender["tender_id"],
            tender_category=tender["subcategory"],
            criteria=criteria,
            submission=build_submission(vendor_data["submission"]),
            vri=build_vri(vendor_data["vri"]),
            policy=policy,
            market_avg_price_sar=tender.get("market_avg_price_sar"),
        )

        artifact = agent.run(payload)
        score_output = artifact.output

        print(f"  Disqualified: {score_output['disqualification']['disqualified']}")
        if score_output['disqualification']['disqualified']:
            print(f"  Reasons: {score_output['disqualification']['reasons']}")
        else:
            breakdown = score_output['fit_score_breakdown']
            print(f"  Fit Score: {breakdown['final_fit_score']:.1f}")
            print(f"  Weighted Total: {score_output['weighted_total']:.1f}")
            print(f"  Risk Level: {score_output['risk_level']}")

        vendor_scores.append(score_output)

    print_separator()

    # ── Step 2: Rank all vendors ───────────────────────────────────────────
    print("Ranking vendors...")

    from agents.evaluation.schemas import VendorScore, DisqualificationResult, FitScoreBreakdown, CriterionScore

    score_objects = []
    for s in vendor_scores:
        score_objects.append(VendorScore(
            vendor_id=s["vendor_id"],
            submission_id=s["submission_id"],
            disqualification=DisqualificationResult(**s["disqualification"]),
            scores_by_criterion=[CriterionScore(**c) for c in s["scores_by_criterion"]],
            fit_score_breakdown=FitScoreBreakdown(**s["fit_score_breakdown"]),
            weighted_total=s["weighted_total"],
            risk_level=s["risk_level"],
            overall_reasoning=s["overall_reasoning"],
            missing_requirements=s["missing_requirements"],
            trace_id=s["trace_id"],
        ))

    ranking_payload = RankingInput(
        tender_id=tender["tender_id"],
        policy=policy,
        vendor_scores=score_objects,
    )

    ranking_artifact = agent.rank(ranking_payload)
    ranking = ranking_artifact.output

    print_separator()
    print("RANKING RESULTS")
    print_separator()

    print("Ranked List:")
    for v in ranking.get("ranked_list", []):
        print(f"  #{v['rank']} {v['vendor_id']} — Score: {v['weighted_total']:.1f} | VRI: {v['vri']} | Risk: {v['risk_level']}")
        print(f"       {v['summary']}")

    if ranking.get("disqualified_vendors"):
        print(f"\nDisqualified: {ranking['disqualified_vendors']}")

    print(f"\nRecommendation:\n{ranking['recommendation']}")
    print(f"\nExplainability:\n{ranking['explainability_summary']}")
    print_separator()
    print("Demo complete. Artifacts ready for DB persistence.")


if __name__ == "__main__":
    main()
