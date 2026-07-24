"""
Celery task wrappers for all three agents.

Each task:
  - Accepts plain dicts (JSON-serializable) — Celery can't serialize Pydantic models
  - Deserializes into the correct input schema
  - Runs the agent
  - Returns the AIArtifact as a dict for the caller to persist to DB

Usage from FastAPI:
    from agents.tasks import run_vendor_validation
    job = run_vendor_validation.delay(payload_dict)
    # store job.id so client can poll status
"""
import logging
import os

from celery import Celery
from pydantic import ValidationError

from .evaluation.agent import EvaluationRankerAgent
from .evaluation.schemas import RankingInput, VendorScore, VendorScoringInput
from .tender_drafting.agent import TenderDrafterAgent
from .tender_drafting.schemas import TenderDraftInput
from .vendor_validation.agent import VendorValidationAgent
from .vendor_validation.schemas import VendorValidationInput

logger = logging.getLogger(__name__)

# ── Celery app ─────────────────────────────────────────────────────────────────
# Broker and backend URLs come from env vars — never hardcoded.
celery_app = Celery(
    "mushtary_agents",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,            # re-queue on worker crash
    worker_prefetch_multiplier=1,   # one task at a time per worker (AI tasks are heavy)
    result_expires=86400,           # 24 hours
    task_soft_time_limit=int(os.environ.get("AI_TASK_SOFT_TIME_LIMIT", "300")),
    task_time_limit=int(os.environ.get("AI_TASK_HARD_TIME_LIMIT", "330")),
    task_reject_on_worker_lost=True,
)


def _get_api_key() -> str:
    # Local-first: defaults to a harmless placeholder for local servers (e.g. Ollama).
    from .llm_config import get_api_key

    return get_api_key()


def _retry_or_raise(task, exc: Exception):
    """Do not retry permanent input/schema failures; back off transient runtime failures."""
    if isinstance(exc, (ValidationError, ValueError, TypeError)):
        raise exc
    raise task.retry(exc=exc, countdown=min(120, 15 * (2 ** task.request.retries)))


# ── Task 1: Vendor Validation ──────────────────────────────────────────────────

@celery_app.task(name="agents.validate_vendor", bind=True, max_retries=2)
def run_vendor_validation(self, payload_dict: dict) -> dict:
    """
    Validate a vendor registration.
    payload_dict must match VendorValidationInput schema.
    Returns AIArtifact as dict — backend persists to ai_artifacts table.
    """
    try:
        payload = VendorValidationInput.model_validate(payload_dict)
        agent = VendorValidationAgent(api_key=_get_api_key())
        artifact = agent.run(payload)
        return artifact.model_dump(mode="json")
    except Exception as exc:
        logger.error("Vendor validation task failed (%s)", type(exc).__name__)
        _retry_or_raise(self, exc)


# ── Task 2: Tender Drafting ────────────────────────────────────────────────────

@celery_app.task(name="agents.draft_tender", bind=True, max_retries=2)
def run_tender_draft(self, payload_dict: dict) -> dict:
    """
    Generate an AI tender draft.
    payload_dict must match TenderDraftInput schema.
    Returns AIArtifact as dict with status=DRAFT (buyer must approve before publish).
    """
    try:
        payload = TenderDraftInput.model_validate(payload_dict)
        agent = TenderDrafterAgent(api_key=_get_api_key())
        artifact = agent.run(payload)
        return artifact.model_dump(mode="json")
    except Exception as exc:
        logger.error("Tender draft task failed (%s)", type(exc).__name__)
        _retry_or_raise(self, exc)


# ── Task 3a: Per-vendor scoring ────────────────────────────────────────────────

@celery_app.task(name="agents.score_vendor", bind=True, max_retries=2)
def run_vendor_scoring(self, payload_dict: dict) -> dict:
    """
    Score a single vendor submission.
    payload_dict must match VendorScoringInput schema.
    Run one task per vendor — they execute in parallel.
    """
    try:
        payload = VendorScoringInput.model_validate(payload_dict)
        agent = EvaluationRankerAgent(api_key=_get_api_key())
        artifact = agent.run(payload)
        return artifact.model_dump(mode="json")
    except Exception as exc:
        logger.error("Vendor scoring task failed (%s)", type(exc).__name__)
        _retry_or_raise(self, exc)


# ── Task 3b: Ranking aggregation ───────────────────────────────────────────────

@celery_app.task(name="agents.rank_vendors", bind=True, max_retries=2)
def run_vendor_ranking(self, vendor_score_dicts: list[dict], tender_id: str) -> dict:
    """
    Aggregate per-vendor scores into a ranked recommendation list.
    Call this AFTER all run_vendor_scoring tasks have completed.
    Returns AIArtifact with buyer_approved=False — buyer must approve before award.
    """
    try:
        vendor_scores = [VendorScore.model_validate(d) for d in vendor_score_dicts]
        payload = RankingInput(tender_id=tender_id, vendor_scores=vendor_scores)
        agent = EvaluationRankerAgent(api_key=_get_api_key())
        artifact = agent.rank(payload)
        return artifact.model_dump(mode="json")
    except Exception as exc:
        logger.error("Vendor ranking task failed (%s)", type(exc).__name__)
        _retry_or_raise(self, exc)
