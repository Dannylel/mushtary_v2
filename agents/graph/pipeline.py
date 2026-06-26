"""
LangGraph tender-creation pipeline.

Graph shape (default "all together" flow):

    START
      │
      ▼
    form_source            ← AI fills the form (auto) | provided form | SOW extract
      │
      ├──────────┬───────────┬────────────┐      (parallel fan-out)
      ▼          ▼           ▼            ▼
    context    scope     execution    legal_eval
      └──────────┴───────────┴────────────┘
      │                                          (fan-in)
      ▼
    assemble  → TenderDraft + AIArtifact (status=DRAFT)
      │
      ▼
     END

Each node is independently runnable (see agents/graph/modes.py), so a caller can run
one agent alone or the whole graph.
"""

from __future__ import annotations

import uuid

from agents.base import AIArtifact
from agents.form_generator.agent import FormGeneratorAgent
from agents.llm_config import get_model
from agents.sow_extractor.agent import SoWExtractorAgent
from agents.tender_intelligence import assess_tender_health
from agents.tender_drafting.schemas import assemble_tender_draft
from agents.tender_drafting.sections.context import ContextSectionAgent
from agents.tender_drafting.sections.execution import ExecutionSectionAgent
from agents.tender_drafting.sections.legal_eval import LegalEvalSectionAgent
from agents.tender_drafting.sections.scope import ScopeSectionAgent

from .state import TenderState

PROMPT_NAME = "tender_draft_v2"
PROMPT_VERSION = "3.2.0"


# ── Nodes ──────────────────────────────────────────────────────────────────────

def node_form_source(state: TenderState) -> dict:
    """Resolve the buyer brief: use a provided form, extract from a SOW, or AI-fill it."""
    if state.get("form") is not None:
        return {"form": state["form"]}

    source = state.get("source") or "auto"
    if source == "sow":
        agent = SoWExtractorAgent()
        if state.get("sow_path"):
            return {"form": agent.extract_from_pdf(state["sow_path"])}
        return {"form": agent.extract_from_text(state.get("sow_text") or "")}

    # default: autonomous AI form generation (no user input)
    return {"form": FormGeneratorAgent().generate(state.get("seed"))}


def node_context(state: TenderState) -> dict:
    return {"context_sections": ContextSectionAgent().run(state["form"])}


def node_scope(state: TenderState) -> dict:
    return {"scope_sections": ScopeSectionAgent().run(state["form"])}


def node_execution(state: TenderState) -> dict:
    return {"execution_sections": ExecutionSectionAgent().run(state["form"])}


def node_legal_eval(state: TenderState) -> dict:
    return {"legal_eval_sections": LegalEvalSectionAgent().run(state["form"])}


def node_assemble(state: TenderState) -> dict:
    trace_id = f"trace_{uuid.uuid4().hex}"
    form = state["form"]
    draft = assemble_tender_draft(
        ctx=state["context_sections"],
        scope=state["scope_sections"],
        exec_=state["execution_sections"],
        legal=state["legal_eval_sections"],
        trace_id=trace_id,
    )
    artifact = AIArtifact(
        id=uuid.uuid4().hex,
        trace_id=trace_id,
        type="TENDER_DRAFT",
        tender_id=form.tender_id,
        actor_id=state.get("buyer_id"),
        prompt_name=PROMPT_NAME,
        prompt_version=PROMPT_VERSION,
        input_snapshot=form.model_dump(mode="json"),
        output=draft.model_dump(mode="json"),
        # Record the actual model tag (not just "local") so artifacts stay traceable.
        model_used=get_model(),
        input_tokens=0,
        output_tokens=0,
    )
    return {"draft": draft, "artifact": artifact.model_dump(mode="json")}


def node_tender_intelligence(state: TenderState) -> dict:
    health = assess_tender_health(state["draft"], state["form"]).model_dump(mode="json")
    artifact = dict(state["artifact"])
    output = dict(artifact.get("output") or {})
    output["tender_intelligence"] = health
    artifact["output"] = output
    return {"tender_intelligence": health, "artifact": artifact}


# ── Graph ──────────────────────────────────────────────────────────────────────

def build_tender_graph():
    """Compile the default tender-creation graph (form_source → 4 sections → assemble)."""
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(TenderState)
    g.add_node("form_source", node_form_source)
    g.add_node("context", node_context)
    g.add_node("scope", node_scope)
    g.add_node("execution", node_execution)
    g.add_node("legal_eval", node_legal_eval)
    g.add_node("assemble", node_assemble)
    g.add_node("tender_intelligence", node_tender_intelligence)

    g.add_edge(START, "form_source")
    for section in ("context", "scope", "execution", "legal_eval"):
        g.add_edge("form_source", section)   # fan-out (parallel)
        g.add_edge(section, "assemble")      # fan-in (assemble waits for all four)
    g.add_edge("assemble", "tender_intelligence")
    g.add_edge("tender_intelligence", END)

    return g.compile()


def run_tender_pipeline(
    *,
    source: str = "auto",
    seed: str | None = None,
    form=None,
    sow_text: str | None = None,
    sow_path: str | None = None,
    buyer_id: str = "auto-buyer",
) -> TenderState:
    """Run the full tender-creation graph and return the final state (draft + artifact)."""
    graph = build_tender_graph()
    initial: TenderState = {"source": source, "buyer_id": buyer_id}
    if form is not None:
        initial["form"] = form
        initial["source"] = "form"
    if seed is not None:
        initial["seed"] = seed
    if sow_text is not None:
        initial["sow_text"] = sow_text
    if sow_path is not None:
        initial["sow_path"] = sow_path
    return graph.invoke(initial)
