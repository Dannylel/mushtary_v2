"""
Shared base for all section agents.
Each section agent gets a focused prompt covering only its sections,
calls the LLM once, and returns validated Pydantic models.
"""
import json
import logging

from agents.llm_config import chat_text

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
            return chat_text(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.4,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error("%s LLM call failed: %s", self.__class__.__name__, e)
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
            return TenderKnowledgeBase.format_context(hits)
        except Exception as e:  # importing/retrieval must never break a section draft
            logger.debug("%s reference-context lookup skipped: %s", self.__class__.__name__, e)
            return ""

    def _parse_json(self, raw: str | None) -> dict:
        if not raw:
            return {}
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error("%s JSON parse failed: %s", self.__class__.__name__, e)
            return {}
