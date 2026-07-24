import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from agents.llm_config import get_model
from agents.llm_config import get_provider
from agents.observability import emit, ensure_trace, trace_result_mode


class ArtifactStatus:
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AIArtifact(BaseModel):
    """Represents a stored AI output — maps to ai_artifacts DB table."""
    id: str
    trace_id: str
    type: str                   # VENDOR_VALIDATION | TENDER_DRAFT | EVALUATION
    vendor_id: str | None = None
    tender_id: str | None = None
    actor_id: str | None = None
    status: str = ArtifactStatus.DRAFT
    prompt_name: str
    prompt_version: str
    input_snapshot: dict        # sanitized copy of inputs used
    output: dict                # structured AI output
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = "unknown"
    result_mode: str = "AI_SUCCESS"
    prompt_sha256: str = ""
    parent_artifact_id: str | None = None
    revision_number: int = 1
    created_at: datetime = None

    def model_post_init(self, __context: Any) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class BaseAgent(ABC):
    """
    All agents inherit from this. Provides:
    - trace_id generation
    - input sanitization hook
    - output schema validation via guardrails
    - artifact construction ready for DB persistence
    """

    artifact_type: str          # must be set by subclass

    @property
    def model(self) -> str:
        """Resolved at call time from env (LLM_MODEL) — defaults to the local model."""
        return get_model()

    def new_trace_id(self) -> str:
        return ensure_trace().trace_id

    def sanitize_input(self, raw: dict) -> dict:
        """
        Strip fields that must never reach the LLM.
        Override in subclass to add agent-specific rules.
        """
        forbidden = {"password", "otp", "token", "secret", "api_key", "authorization", "raw_file_content"}

        def clean(value: Any):
            if isinstance(value, dict):
                return {
                    key: clean(item)
                    for key, item in value.items()
                    if key.lower() not in forbidden
                }
            if isinstance(value, list):
                return [clean(item) for item in value]
            return value

        return clean(raw)

    def build_artifact(
        self,
        trace_id: str,
        prompt_name: str,
        prompt_version: str,
        input_snapshot: dict,
        output: dict,
        usage: dict,
        vendor_id: str | None = None,
        tender_id: str | None = None,
        actor_id: str | None = None,
    ) -> AIArtifact:
        observed_mode = trace_result_mode(trace_id)
        requested_mode = usage.get("result_mode", "AI_SUCCESS")
        result_mode = observed_mode if observed_mode != "AI_SUCCESS" else requested_mode
        artifact = AIArtifact(
            id=uuid.uuid4().hex,
            trace_id=trace_id,
            type=self.artifact_type,
            vendor_id=vendor_id,
            tender_id=tender_id,
            actor_id=actor_id,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            input_snapshot=input_snapshot,
            output=output,
            model_used=self.model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            provider=get_provider(),
            result_mode=result_mode,
            prompt_sha256=usage.get("prompt_sha256", ""),
        )
        emit(
            "artifact.created",
            artifact_id=artifact.id,
            artifact_type=artifact.type,
            result_mode=artifact.result_mode,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            prompt_sha256=artifact.prompt_sha256,
        )
        return artifact

    @abstractmethod
    def run(self, *args, **kwargs) -> AIArtifact:
        """Entry point for each agent. Must return an AIArtifact."""
        ...
