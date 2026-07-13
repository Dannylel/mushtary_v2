"""
TenderDrafterAgent — orchestrates 4 parallel section agents.

Flow:
  1. Split TenderBuyerForm fields across 4 section agents
  2. Run all 4 agents in parallel via ThreadPoolExecutor
  3. Assemble outputs into a single TenderDraft
  4. Return AIArtifact (status=DRAFT — buyer must approve before publish)
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base import AIArtifact, BaseAgent
from agents.llm_config import make_client
from agents.tender_drafting.schemas import (
    DRAFT_FALLBACK,
    TenderDraftInput,
    assemble_tender_draft,
)
from agents.tender_drafting.sections.context   import ContextSectionAgent
from agents.tender_drafting.sections.execution import ExecutionSectionAgent
from agents.tender_drafting.sections.legal_eval import LegalEvalSectionAgent
from agents.tender_drafting.sections.scope     import ScopeSectionAgent

logger = logging.getLogger(__name__)

PROMPT_NAME    = "tender_draft_v2"
PROMPT_VERSION = "3.3.0"


class TenderDrafterAgent(BaseAgent):
    artifact_type = "TENDER_DRAFT"

    def __init__(self, api_key: str | None = None):
        self._client = make_client(api_key)

    def run(self, payload: TenderDraftInput) -> AIArtifact:
        trace_id = self.new_trace_id()
        form = payload.form

        logger.info(
            "TenderDrafterAgent started — 4 section agents in parallel",
            extra={"trace_id": trace_id, "tender_id": form.tender_id},
        )

        input_snapshot = self.sanitize_input(payload.model_dump(mode="json"))

        # ── Run 4 section agents in parallel ──────────────────────────────────
        ctx_agent   = ContextSectionAgent(self._client)
        scope_agent = ScopeSectionAgent(self._client)
        exec_agent  = ExecutionSectionAgent(self._client)
        legal_agent = LegalEvalSectionAgent(self._client)

        agents = {
            "context":   (ctx_agent.run,   form),
            "scope":     (scope_agent.run,  form),
            "execution": (exec_agent.run,   form),
            "legal_eval":(legal_agent.run,  form),
        }

        results = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(fn, arg): name
                for name, (fn, arg) in agents.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                    logger.info("Section agent done: %s", name, extra={"trace_id": trace_id})
                except Exception as e:
                    logger.error("Section agent failed: %s — %s", name, e, extra={"trace_id": trace_id})

        # ── Assemble or fall back ─────────────────────────────────────────────
        try:
            draft = assemble_tender_draft(
                ctx=results["context"],
                scope=results["scope"],
                exec_=results["execution"],
                legal=results["legal_eval"],
                trace_id=trace_id,
            )
        except Exception as e:
            logger.error("Assembly failed: %s", e, extra={"trace_id": trace_id})
            draft = DRAFT_FALLBACK.model_copy(update={"trace_id": trace_id})

        artifact = self.build_artifact(
            trace_id=trace_id,
            prompt_name=PROMPT_NAME,
            prompt_version=PROMPT_VERSION,
            input_snapshot=input_snapshot,
            output=draft.model_dump(mode="json"),
            usage={"input_tokens": 0, "output_tokens": 0},
            tender_id=form.tender_id,
            actor_id=payload.buyer_id,
        )

        logger.info(
            "TenderDrafterAgent complete",
            extra={"trace_id": trace_id, "title": draft.metadata.title},
        )
        return artifact
