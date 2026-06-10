"""
Guardrails — validate AI output schema before storing.
If output is malformed, return a safe fallback instead of crashing.
"""
import logging
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

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
        logger.error(
            "Guardrail schema validation failed",
            extra={"trace_id": trace_id, "errors": e.errors(), "raw": raw},
        )
        return None


def safe_parse(raw: dict, schema: Type[T], fallback: T, trace_id: str) -> T:
    """
    Validate and return fallback if validation fails.
    Guarantees a valid object is always returned — workflow never crashes.
    """
    result = validate_output(raw, schema, trace_id)
    if result is None:
        logger.warning(
            "Applying safe fallback due to guardrail failure",
            extra={"trace_id": trace_id, "fallback": fallback.model_dump()},
        )
        return fallback
    return result
