"""LangGraph orchestration for isolated vendor scoring followed by ranking."""
from __future__ import annotations

from typing import Any, TypedDict


class EvaluationState(TypedDict, total=False):
    tender: dict[str, Any]
    submissions: list[dict[str, Any]]
    policy: Any
    criteria: Any
    score_artifacts: list[dict[str, Any]]
    scores: list[dict[str, Any]]
    ranking_artifact: dict[str, Any]
    ranking: dict[str, Any]
    vendor_names: dict[str, str]


def _score_isolated(state: EvaluationState) -> dict[str, Any]:
    from .agent import EvaluationRankerAgent
    from .schemas import VendorScoringInput
    from agents.samples.run_demo import build_submission, build_vri

    agent = EvaluationRankerAgent()
    artifacts, scores = [], []
    for vendor_data in state["submissions"]:
        payload = VendorScoringInput(
            tender_id=state["tender"]["tender_id"], tender_category=state["tender"]["subcategory"],
            criteria=state["criteria"], submission=build_submission(vendor_data["submission"]),
            vri=build_vri(vendor_data["vri"]), policy=state["policy"],
            market_avg_price_sar=state["tender"].get("market_avg_price_sar"),
        )
        artifact = agent.run(payload).model_dump(mode="json")
        score = dict(artifact["output"])
        score["vendor_name"] = vendor_data["vendor_name"]
        artifacts.append(artifact); scores.append(score)
    return {"score_artifacts": artifacts, "scores": scores}


def _rank_scores(state: EvaluationState) -> dict[str, Any]:
    from .agent import EvaluationRankerAgent
    from .schemas import RankingInput, VendorScore

    artifact = EvaluationRankerAgent().rank(RankingInput(
        tender_id=state["tender"]["tender_id"], policy=state["policy"],
        vendor_scores=[VendorScore.model_validate(score) for score in state["scores"]],
    )).model_dump(mode="json")
    return {"ranking_artifact": artifact, "ranking": artifact["output"]}


def run_evaluation_graph(tender: dict[str, Any], submissions: list[dict[str, Any]]) -> EvaluationState:
    """Run the two lifecycle stages in LangGraph while preserving scoring isolation."""
    from langgraph.graph import END, START, StateGraph
    from agents.samples.run_demo import build_criteria, build_policy

    graph = StateGraph(EvaluationState)
    graph.add_node("score_isolated_vendors", _score_isolated)
    graph.add_node("rank_scores", _rank_scores)
    graph.add_edge(START, "score_isolated_vendors")
    graph.add_edge("score_isolated_vendors", "rank_scores")
    graph.add_edge("rank_scores", END)
    return graph.compile().invoke({
        "tender": tender, "submissions": submissions,
        "policy": build_policy(tender), "criteria": build_criteria(tender),
        "vendor_names": {item["submission"]["vendor_id"]: item["vendor_name"] for item in submissions},
    })
