"""LangGraph buyer committee for a single shortlisted vendor.

The deterministic shortlist remains the eligibility gate.  This graph adds advisory,
evidence-bound LLM judgement for buyers; it must not invent vendor facts or award work.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, TypedDict

from agents.guardrails import safe_parse
from agents.llm_config import chat_json_text
from agents.prompts import GLOBAL_QUALITY_STANDARD

from .schemas import CommitteeAgentAssessment, VendorCommitteeOutput

logger = logging.getLogger(__name__)

PROMPT_NAME = "vendor_committee_v1"
PROMPT_VERSION = "1.1.0"

_ROLES = {
    "technical": "Technical Agent: assess the submitted technical proposal against tender scope, category fit, certifications, and similar-project evidence.",
    "commercial": "Commercial Agent: assess the submitted price, commercial summary, and timeline against the tender budget and needs; never invent a bid or price.",
    "compliance": "Compliance Agent: assess stated registration, certification, status, eligibility evidence, and proposal compliance gaps.",
    "delivery": "Delivery Agent: assess the submitted timeline alongside delivery reliability, capacity indicators, location, and relevant experience.",
    "risk": "Risk Agent: identify evidence-based delivery, compliance, dispute, price-signal, proposal, or uncertainty risks.",
}


class CommitteeState(TypedDict, total=False):
    tender: dict[str, Any]
    vendor: dict[str, Any]
    proposal: dict[str, Any]
    baseline: dict[str, Any]
    technical: CommitteeAgentAssessment
    commercial: CommitteeAgentAssessment
    compliance: CommitteeAgentAssessment
    delivery: CommitteeAgentAssessment
    risk: CommitteeAgentAssessment
    committee: VendorCommitteeOutput


def _json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        raise ValueError("empty LLM response")
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        text = re.sub(r"^json\s*", "", text.strip(), flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM result must be a JSON object")
    return parsed


def _fallback_agent(name: str, baseline: dict[str, Any]) -> CommitteeAgentAssessment:
    previous = next((x for x in baseline.get("agents", []) if x.get("agent") == name), {})
    score = int(previous.get("score", baseline.get("final_score", 50)))
    return CommitteeAgentAssessment(
        agent=name,
        score=max(0, min(100, score)),
        summary=previous.get("summary", "Deterministic profile signal; LLM assessment unavailable."),
        evidence=[],
        risks=[],
        recommendation="Buyer review required.",
    )


def _specialist_node(key: str):
    name = _ROLES[key].split(":", 1)[0]

    def node(state: CommitteeState) -> dict[str, CommitteeAgentAssessment]:
        fallback = _fallback_agent(name, state["baseline"])
        payload = {
            "tender_requirements": state["tender"],
            "vendor_profile": state["vendor"],
            "submitted_proposal": state.get("proposal") or {},
            "deterministic_baseline": state["baseline"],
        }
        system = GLOBAL_QUALITY_STANDARD + "\n\n" + f"""You are the {name} on a buyer-side procurement committee.
{_ROLES[key]}
Use only supplied facts. Do not infer missing licenses, capacity, prices, or performance.
This is advisory only and cannot approve, exclude, or award a vendor.
Evaluate requirement by requirement where the input permits. Provide at least three precise
evidence items when available. Each evidence item must name the proposal/profile field and the
claim or value examined. Risks must state the missing/weak evidence and procurement consequence.
The recommendation must tell the buyer what to accept, verify, clarify, negotiate, or reject
within this specialist's remit; a generic "buyer review required" is insufficient when evidence exists.
Return only JSON: {{"agent":"{name}","score":0-100,"summary":"...","evidence":["..."],"risks":["..."],"recommendation":"..."}}."""
        try:
            raw = chat_json_text(
                [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                temperature=0.1,
                max_tokens=1100,
            )
            parsed = _json_object(raw)
            parsed["agent"] = name
            return {key: safe_parse(parsed, CommitteeAgentAssessment, fallback, f"vendor_committee_{key}")}
        except Exception as exc:
            logger.warning("Vendor committee %s agent failed; using baseline: %s", key, exc)
            return {key: fallback}

    return node


def _aggregate(state: CommitteeState) -> dict[str, VendorCommitteeOutput]:
    agents = [state[key] for key in _ROLES]
    baseline = state["baseline"]
    fallback = VendorCommitteeOutput(
        final_score=int(baseline.get("final_score", 50)),
        recommendation_status="needs_human_review",
        final_recommendation="Deterministic shortlist result retained; buyer review is required.",
        confidence="low",
        agents=agents,
        buyer_questions=[],
        committee_reasoning=["LLM aggregation was unavailable; deterministic baseline remains advisory."],
        llm_backed=False,
        fallback_used=True,
    )
    payload = {"tender_requirements": state["tender"], "vendor_profile": state["vendor"], "submitted_proposal": state.get("proposal") or {}, "baseline": baseline, "specialist_assessments": [a.model_dump() for a in agents]}
    try:
        raw = chat_json_text(
            [{"role": "system", "content": GLOBAL_QUALITY_STANDARD + "\n\n" + """You are the Buyer Committee Aggregator. Combine the supplied specialist assessments for ONE vendor. Use only their evidence and the supplied data. Do not invent facts, bids, or competitor comparisons. Calculate final_score using Technical 30%, Commercial 20%, Compliance 20%, Delivery 15%, and Risk 15% (a higher Risk Agent score means lower risk). Explain the decisive evidence, material gaps, and any score conflict in 4-6 committee_reasoning bullets. buyer_questions must be concrete questions whose answers could change compliance, score, risk, price/value, delivery confidence, or award suitability. Return only JSON: {"final_score":0-100,"recommendation_status":"strong_match|possible_match|not_recommended|needs_human_review","final_recommendation":"...","confidence":"high|medium|low","buyer_questions":["..."],"committee_reasoning":["..."],"agents":[]}. Keep the provided specialist assessments unchanged in agents. This is advisory only; the buyer makes every decision."""}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            temperature=0.1,
            max_tokens=1300,
        )
        parsed = _json_object(raw)
        parsed["agents"] = [a.model_dump() for a in agents]
        parsed["llm_backed"] = True
        parsed["fallback_used"] = False
        return {"committee": safe_parse(parsed, VendorCommitteeOutput, fallback, "vendor_committee_aggregate")}
    except Exception as exc:
        logger.warning("Vendor committee aggregation failed; using baseline: %s", exc)
        return {"committee": fallback}


def build_vendor_committee_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(CommitteeState)
    for key in _ROLES:
        graph.add_node(key, _specialist_node(key))
        graph.add_edge(START, key)
        graph.add_edge(key, "aggregate")
    graph.add_node("aggregate", _aggregate)
    graph.add_edge("aggregate", END)
    return graph.compile()


def run_vendor_committee(*, tender: dict[str, Any], vendor: dict[str, Any], proposal: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Run a buyer-only committee for one vendor's submitted proposal."""
    result = build_vendor_committee_graph().invoke({"tender": tender, "vendor": vendor, "proposal": proposal, "baseline": baseline})
    return result["committee"].model_dump(mode="json")
