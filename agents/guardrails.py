"""
Guardrails — validate AI output schema before storing.
If output is malformed, return a safe fallback instead of crashing.
"""
import logging
import json
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError
from agents.observability import emit
from agents.observability import sha256_text

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def validate_output(raw: dict, schema: Type[T], trace_id: str) -> T | None:
    """
    Validate raw LLM output against a Pydantic schema.
    Returns None on failure — caller must apply fallback.
    """
    try:
        return schema.model_validate(raw)
    except ValidationError as e:
        emit(
            "ai.schema_validation.failed",
            level="WARNING",
            schema=schema.__name__,
            error_count=len(e.errors()),
        )
        logger.error(
            "Guardrail schema validation failed",
            extra={
                "trace_id": trace_id,
                "error_count": len(e.errors()),
                "raw_sha256": sha256_text(json.dumps(raw, ensure_ascii=False, default=str)),
            },
        )
        return None


def safe_parse(raw: dict, schema: Type[T], fallback: T, trace_id: str) -> T:
    """
    Validate and return fallback if validation fails.
    Guarantees a valid object is always returned — workflow never crashes.
    """
    result = validate_output(raw, schema, trace_id)
    if result is None:
        emit(
            "ai.fallback.applied",
            level="WARNING",
            reason="schema_validation",
            schema=schema.__name__,
            result_mode="DETERMINISTIC_FALLBACK",
        )
        logger.warning(
            "Applying safe fallback due to guardrail failure",
            extra={"trace_id": trace_id, "fallback_schema": type(fallback).__name__},
        )
        return fallback
    return result
