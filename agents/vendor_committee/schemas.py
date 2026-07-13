from __future__ import annotations

from pydantic import BaseModel, Field


class CommitteeAgentAssessment(BaseModel):
    agent: str
    score: int = Field(ge=0, le=100)
    summary: str
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendation: str


class VendorCommitteeOutput(BaseModel):
    final_score: int = Field(ge=0, le=100)
    recommendation_status: str
    final_recommendation: str
    confidence: str
    agents: list[CommitteeAgentAssessment] = Field(default_factory=list)
    buyer_questions: list[str] = Field(default_factory=list)
    committee_reasoning: list[str] = Field(default_factory=list)
    llm_backed: bool = True
    fallback_used: bool = False
