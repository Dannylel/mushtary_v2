import unittest

from agents.evaluation.agent import EvaluationRankerAgent
from agents.evaluation.schemas import (
    CriterionScore,
    DisqualificationResult,
    EvaluationCriterion,
    FitScoreBreakdown,
    SubmissionSummary,
    TenderPolicy,
    VRIComponents,
    VRIScore,
    VendorScore,
    VendorScoringInput,
)


class TestEvaluationDeterminism(unittest.TestCase):
    def test_model_cannot_control_arithmetic_or_criterion_membership(self):
        policy = TenderPolicy(technical_weight_percent=70, financial_weight_percent=30)
        criteria = [
            EvaluationCriterion(
                id="C1", name="Method", description="Method evidence", weight_percent=100
            )
        ]
        payload = VendorScoringInput(
            tender_id="T1",
            tender_category="IT",
            criteria=criteria,
            submission=SubmissionSummary(
                vendor_id="V1",
                submission_id="S1",
                technical_response="Evidence",
                commercial_summary="Price",
            ),
            vri=VRIScore(
                vendor_id="V1",
                overall=80,
                category_specific=90,
                components=VRIComponents(
                    performance_rating=80,
                    compliance_and_licenses=80,
                    institutional_verification=80,
                    delivery_performance=80,
                    financial_strength=80,
                    tender_success_rate=80,
                    contract_history=80,
                    ai_risk_signals=80,
                ),
                level="strategic_vendor",
            ),
            policy=policy,
        )
        model_score = VendorScore(
            vendor_id="V1",
            submission_id="S1",
            disqualification=DisqualificationResult(disqualified=False),
            scores_by_criterion=[
                CriterionScore(
                    criterion_id="INVENTED",
                    criterion_name="Invented",
                    score=10,
                    reasoning="Model supplied",
                )
            ],
            fit_score_breakdown=FitScoreBreakdown(
                vri_component=1,
                requirement_match=80,
                proposal_quality=70,
                price_competitiveness=60,
                risk_adjustment=5,
                final_fit_score=999,
            ),
            weighted_total=999,
            risk_level="low",
            overall_reasoning="Narrative",
            missing_requirements=[],
            trace_id="trace-test",
        )
        result = EvaluationRankerAgent._enforce_arithmetic(model_score, payload)
        self.assertEqual([item.criterion_id for item in result.scores_by_criterion], ["C1"])
        self.assertEqual(result.fit_score_breakdown.vri_component, 90)
        self.assertEqual(result.fit_score_breakdown.risk_adjustment, 0)
        self.assertEqual(result.fit_score_breakdown.final_fit_score, 80)
        self.assertEqual(result.weighted_total, 18)


if __name__ == "__main__":
    unittest.main()
