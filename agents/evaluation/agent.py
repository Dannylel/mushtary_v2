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
from agents.llm_config import chat_with_usage

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

        input_snapshot = self.sanitize_input(payload.model_dump(mode="json"))

        raw_text, usage = chat_with_usage(
            [
                {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                {"role": "user", "content": build_scoring_message(payload)},
            ],
            temperature=0.2,
            max_tokens=2048,
        )

        vendor_score = self._parse_score(raw_text, payload, trace_id)

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

        input_snapshot = {
            "tender_id": payload.tender_id,
            "vendor_count": len(payload.vendor_scores),
            "policy": payload.policy.model_dump(mode="json"),
        }

        raw_text, usage = chat_with_usage(
            [
                {"role": "system", "content": RANKING_SYSTEM_PROMPT},
                {"role": "user", "content": build_ranking_message(payload.vendor_scores, payload.policy)},
            ],
            temperature=0.2,
            max_tokens=2048,
        )

        ranked = self._parse_ranking(raw_text, payload, trace_id)

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
            return fallback

        try:
            text = raw_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            raw_dict = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return fallback

        raw_dict["vendor_id"] = payload.submission.vendor_id
        raw_dict["submission_id"] = payload.submission.submission_id
        raw_dict["trace_id"] = trace_id

        return safe_parse(raw_dict, VendorScore, fallback, trace_id)

    def _parse_ranking(self, raw_text: str | None, payload: RankingInput, trace_id: str) -> RankedResult:
        fallback = RANKING_FALLBACK.model_copy(update={
            "tender_id": payload.tender_id,
            "trace_id": trace_id,
        })

        if not raw_text:
            return fallback

        try:
            text = raw_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            raw_dict = json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return fallback

        raw_dict["tender_id"] = payload.tender_id
        raw_dict["trace_id"] = trace_id
        raw_dict["ai_generated"] = True
        raw_dict["buyer_approved"] = False
        raw_dict["output_detail"] = payload.policy.output_detail

        return safe_parse(raw_dict, RankedResult, fallback, trace_id)
