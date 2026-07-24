"""
Shared base for all section agents.
Each section agent gets a focused prompt covering only its sections,
calls the LLM once, and returns validated Pydantic models.
"""
import json
import logging
import re

from agents.llm_config import chat_json_text
from agents.observability import emit

logger = logging.getLogger(__name__)


class BaseSectionAgent:
    """Base for LLM-backed section agents (native LangChain via agents.llm_config).

    The optional ``client`` argument is accepted for backward compatibility with the
    legacy ThreadPoolExecutor orchestrator; it is ignored — the model is resolved
    centrally so the same section agent works as a LangGraph node too.
    """

    def __init__(self, client=None):
        self.client = client

    def _call(self, system: str, user: str, max_tokens: int = 2500) -> str | None:
        # Tag this worker thread so streamed tokens show up under this section's name
        # in the live activity console.
        from agents import activity

        activity.set_label(self.__class__.__name__.replace("SectionAgent", " section"))
        try:
            return chat_json_text(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.4,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error("%s LLM call failed (%s)", self.__class__.__name__, type(e).__name__)
            emit(
                "ai.fallback.applied",
                level="WARNING",
                agent=self.__class__.__name__,
                reason="llm_call_failed",
                error_type=type(e).__name__,
                result_mode="DETERMINISTIC_FALLBACK",
            )
            return None

    def _generate(self, system: str, user: str, max_tokens: int = 2500) -> dict:
        """Call the LLM and return parsed JSON (empty dict on any failure)."""
        return self._parse_json(self._call(system, user, max_tokens))

    def _reference_context(self, query: str) -> str:
        """Pull a few grounding excerpts from the Tender knowledge base for this query.

        Returns a prompt-ready block, or "" when the corpus is empty / the embedding
        server is unreachable. Section agents prepend this to their user message so the
        model can mirror approved precedent and standard clause wording. RAG never gates
        drafting: an empty string just means "draft as before, with no extra context".
        """
        try:
            from agents.rag import get_tender_kb
            from agents.rag.knowledge_base import TenderKnowledgeBase

            hits = get_tender_kb().retrieve(query)
            emit(
                "rag.query.completed",
                agent=self.__class__.__name__,
                hit_count=len(hits),
                query_sha256=__import__("hashlib").sha256(query.encode("utf-8")).hexdigest(),
                chunk_ids=[hit.metadata.get("chunk_id", "legacy") for hit in hits],
                source_sha256=[
                    hit.metadata.get("source_sha256", "legacy") for hit in hits
                ],
                scores=[round(hit.score, 4) for hit in hits],
            )
            return TenderKnowledgeBase.format_context(hits)
        except Exception as e:  # importing/retrieval must never break a section draft
            logger.debug("%s reference-context lookup skipped: %s", self.__class__.__name__, e)
            emit(
                "rag.query.failed",
                level="WARNING",
                agent=self.__class__.__name__,
                error_type=type(e).__name__,
            )
            return ""

    def _parse_json(self, raw: str | None) -> dict:
        if not raw:
            emit(
                "ai.fallback.applied",
                level="WARNING",
                reason="empty_model_output",
                result_mode="DETERMINISTIC_FALLBACK",
            )
            return {}
        text = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        try:
            parsed = json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error("%s JSON parse failed (%s)", self.__class__.__name__, type(e).__name__)
            emit(
                "ai.fallback.applied",
                level="WARNING",
                reason="json_parse_failed",
                result_mode="DETERMINISTIC_FALLBACK",
            )
            return {}
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            first_dict = next((item for item in parsed if isinstance(item, dict)), None)
            if first_dict is not None:
                logger.warning("%s returned a JSON list; using the first object", self.__class__.__name__)
                return first_dict
        logger.error("%s JSON root must be an object, got %s", self.__class__.__name__, type(parsed).__name__)
        return {}
