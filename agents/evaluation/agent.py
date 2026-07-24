"""
EvaluationRankerAgent — local LLM (Ollama via agents/llm_config), VRI + Vendor Fit Score model.

Two-step process:
  Step 1 — score_vendor(): scores ONE vendor in isolation (one Celery task per vendor)
  Step 2 — rank_vendors(): aggregates all scores into a ranked recommendation list

Vendors are never compared to each other during scoring — isolation is enforced by design.
"""
import json
import logging

from agents.base import AIArtifact, BaseAgent
from agents.guardrails import safe_parse
from agents.llm_config import chat_json_with_usage
from agents.observability import emit

from .prompts import (
    RANK_PROMPT_NAME,
    RANK_PROMPT_VERSION,
    RANKING_SYSTEM_PROMPT,
    SCORE_PROMPT_NAME,
    SCORE_PROMPT_VERSION,
    SCORING_SYSTEM_PROMPT,
    build_ranking_message,
    build_scoring_message,
)
from .schemas import (
    RANKING_FALLBACK,
    SCORE_FALLBACK,
    RankedResult,
    RankingInput,
    VendorScore,
    VendorScoringInput,
)

logger = logging.getLogger(__name__)


class EvaluationRankerAgent(BaseAgent):
    artifact_type = "EVALUATION"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    # ── Public entry points ───────────────────────────────────────────────────

    def run(self, payload: VendorScoringInput) -> AIArtifact:
        """Score a single vendor submission. Called once per vendor."""
        return self._score_vendor(payload)

    def rank(self, payload: RankingInput) -> AIArtifact:
        """Aggregate scores into a ranked list. Called once after all vendors scored."""
        return self._rank_vendors(payload)

    # ── Step 1: Per-vendor scoring ────────────────────────────────────────────

    def _score_vendor(self, payload: VendorScoringInput) -> AIArtifact:
        trace_id = self.new_trace_id()
        logger.info(
            "Scoring vendor",
            extra={"trace_id": trace_id, "vendor_id": payload.submission.vendor_id},
        )

        # Label for the live activity console.
        from agents import activity

        activity.set_label(f"Scoring {payload.submission.vendor_id}")

        input_snapshot = self.sanitize_input(payload.model_dump(mode="json"))

        raw_text, usage, _repair_used = chat_json_with_usage(
            [
                {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                {"role": "user", "content": build_scoring_message(payload)},
            ],
            temperature=0.2,
            max_tokens=3200,
        )

        vendor_score = self._parse_score(raw_text, payload, trace_id)
        vendor_score = self._enforce_arithmetic(vendor_score, payload)

        artifact = self.build_artifact(
            trace_id=trace_id,
            prompt_name=SCORE_PROMPT_NAME,
            prompt_version=SCORE_PROMPT_VERSION,
            input_snapshot=input_snapshot,
            output=vendor_score.model_dump(mode="json"),
            usage=usage,
            vendor_id=payload.submission.vendor_id,
            tender_id=payload.tender_id,
        )

        logger.info(
            "Vendor scored",
            extra={
                "trace_id": trace_id,
                "vendor_id": payload.submission.vendor_id,
                "fit_score": vendor_score.fit_score_breakdown.final_fit_score,
                "disqualified": vendor_score.disqualification.disqualified,
            },
        )
        return artifact

    # ── Step 2: Ranking aggregation ───────────────────────────────────────────

    def _rank_vendors(self, payload: RankingInput) -> AIArtifact:
        trace_id = self.new_trace_id()
        logger.info(
            "Ranking vendors",
            extra={"trace_id": trace_id, "tender_id": payload.tender_id, "count": len(payload.vendor_scores)},
        )

        # Label for the live activity console.
        from agents import activity

        activity.set_label("Ranking")

        input_snapshot = {
            "tender_id": payload.tender_id,
            "vendor_count": len(payload.vendor_scores),
            "policy": payload.policy.model_dump(mode="json"),
        }

        raw_text, usage, _repair_used = chat_json_with_usage(
            [
                {"role": "system", "content": RANKING_SYSTEM_PROMPT},
                {"role": "user", "content": build_ranking_message(payload.vendor_scores, payload.policy)},
            ],
            temperature=0.2,
            max_tokens=2600,
        )

        ranked = self._parse_ranking(raw_text, payload, trace_id)
        ranked = self._enforce_ranking(ranked, payload)

        artifact = self.build_artifact(
            trace_id=trace_id,
            prompt_name=RANK_PROMPT_NAME,
            prompt_version=RANK_PROMPT_VERSION,
            input_snapshot=input_snapshot,
            output=ranked.model_dump(mode="json"),
            usage=usage,
            tender_id=payload.tender_id,
        )

        logger.info("Ranking complete", extra={"trace_id": trace_id})
        return artifact

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_score(self, raw_text: str | None, payload: VendorScoringInput, trace_id: str) -> VendorScore:
        fallback = SCORE_FALLBACK.model_copy(update={
            "vendor_id": payload.submission.vendor_id,
            "submission_id": payload.submission.submission_id,
            "trace_id": trace_id,
        })

        if not raw_text:
            emit("ai.fallback.applied", level="WARNING", reason="empty_score_output", result_mode="DETERMINISTIC_FALLBACK")
            return fallback

        try:
            text = raw_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            raw_dict = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            emit("ai.fallback.applied", level="WARNING", reason="invalid_score_json", result_mode="DETERMINISTIC_FALLBACK")
            return fallback

        raw_dict["vendor_id"] = payload.submission.vendor_id
        raw_dict["submission_id"] = payload.submission.submission_id
        raw_dict["trace_id"] = trace_id

        return safe_parse(raw_dict, VendorScore, fallback, trace_id)

    @staticmethod
    def _enforce_arithmetic(score: VendorScore, payload: VendorScoringInput) -> VendorScore:
        """Keep narrative judgement in the model, but make all arithmetic deterministic."""
        if score.disqualification.disqualified:
            zero_breakdown = score.fit_score_breakdown.model_copy(update={
                "vri_component": 0.0,
                "requirement_match": 0.0,
                "proposal_quality": 0.0,
                "price_competitiveness": 0.0,
                "risk_adjustment": 0.0,
                "final_fit_score": 0.0,
            })
            zero_criteria = [
                item.model_copy(update={"score": 0.0}) for item in score.scores_by_criterion
            ]
            return score.model_copy(update={
                "scores_by_criterion": zero_criteria,
                "fit_score_breakdown": zero_breakdown,
                "weighted_total": 0.0,
                "risk_level": "high",
            })

        by_id = {item.criterion_id: item for item in score.scores_by_criterion}
        normalized = []
        for criterion in payload.criteria:
            item = by_id.get(criterion.id)
            if item is None:
                from .schemas import CriterionScore
                item = CriterionScore(
                    criterion_id=criterion.id,
                    criterion_name=criterion.name,
                    score=0.0,
                    reasoning="No valid model score was returned for this configured criterion.",
                    missing_requirements=["Criterion requires human review."],
                )
            else:
                item = item.model_copy(update={"criterion_name": criterion.name})
            normalized.append(item)

        breakdown = score.fit_score_breakdown
        requirement = min(100.0, max(0.0, breakdown.requirement_match))
        quality = min(100.0, max(0.0, breakdown.proposal_quality))
        price = min(100.0, max(0.0, breakdown.price_competitiveness))
        risk = min(0.0, max(-15.0, breakdown.risk_adjustment))
        vri = payload.vri.category_specific
        final_fit = round(min(100.0, max(
            0.0, 0.40 * vri + 0.30 * requirement + 0.20 * quality + 0.10 * price + risk
        )), 2)

        criterion_weight_total = sum(c.weight_percent for c in payload.criteria)
        technical = (
            sum(
                item.score * 10.0 * criterion.weight_percent
                for item, criterion in zip(normalized, payload.criteria)
            ) / criterion_weight_total
            if criterion_weight_total else 0.0
        )
        policy_weight_total = (
            payload.policy.technical_weight_percent + payload.policy.financial_weight_percent
        ) or 100.0
        weighted_total = round(
            (
                technical * payload.policy.technical_weight_percent
                + price * payload.policy.financial_weight_percent
            ) / policy_weight_total,
            2,
        )
        risk_level = "low" if final_fit > 75 and risk == 0 else "medium" if final_fit >= 50 else "high"
        return score.model_copy(update={
            "scores_by_criterion": normalized,
            "fit_score_breakdown": breakdown.model_copy(update={
                "vri_component": vri,
                "requirement_match": requirement,
                "proposal_quality": quality,
                "price_competitiveness": price,
                "risk_adjustment": risk,
                "final_fit_score": final_fit,
            }),
            "weighted_total": weighted_total,
            "risk_level": risk_level,
        })

    def _parse_ranking(self, raw_text: str | None, payload: RankingInput, trace_id: str) -> RankedResult:
        fallback = RANKING_FALLBACK.model_copy(update={
            "tender_id": payload.tender_id,
            "trace_id": trace_id,
        })

        if not raw_text:
            emit("ai.fallback.applied", level="WARNING", reason="empty_ranking_output", result_mode="DETERMINISTIC_FALLBACK")
            return fallback

        try:
            text = raw_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            raw_dict = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            emit("ai.fallback.applied", level="WARNING", reason="invalid_ranking_json", result_mode="DETERMINISTIC_FALLBACK")
            return fallback

        raw_dict["tender_id"] = payload.tender_id
        raw_dict["trace_id"] = trace_id
        raw_dict["ai_generated"] = True
        raw_dict["buyer_approved"] = False
        raw_dict["output_detail"] = payload.policy.output_detail

        return safe_parse(raw_dict, RankedResult, fallback, trace_id)

    @staticmethod
    def _enforce_ranking(ranked: RankedResult, payload: RankingInput) -> RankedResult:
        """LLM writes explanations; eligibility, membership, ordering and ranks are deterministic."""
        from .schemas import RankedVendor

        summaries = {item.vendor_id: item.summary for item in ranked.ranked_list}
        eligible = sorted(
            (score for score in payload.vendor_scores if not score.disqualification.disqualified),
            key=lambda item: (-item.weighted_total, item.vendor_id),
        )
        normalized = [
            RankedVendor(
                rank=index,
                vendor_id=score.vendor_id,
                weighted_total=score.weighted_total,
                vri=score.fit_score_breakdown.vri_component,
                risk_level=score.risk_level,
                summary=summaries.get(
                    score.vendor_id,
                    "Deterministically ranked from the validated evaluation score; buyer review required.",
                ),
            )
            for index, score in enumerate(eligible, 1)
        ]
        disqualified = sorted(
            score.vendor_id
            for score in payload.vendor_scores
            if score.disqualification.disqualified
        )
        return ranked.model_copy(update={
            "ranked_list": normalized,
            "disqualified_vendors": disqualified,
            "buyer_approved": False,
            "ai_generated": True,
        })
