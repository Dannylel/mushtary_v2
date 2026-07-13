from __future__ import annotations

from pydantic import BaseModel, Field


class TenderHealthFinding(BaseModel):
    area: str
    severity: str
    issue: str
    recommendation: str
    evidence: str = ""


class TenderHealthAgentResult(BaseModel):
    agent_name: str
    role: str
    score: int = Field(ge=0, le=100)
    risk_level: str
    summary: str
    reasoning_summary: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    findings: list[TenderHealthFinding] = Field(default_factory=list)


class TenderHealthAggregateOutput(BaseModel):
    tender_quality_score: int = Field(ge=0, le=100)
    risk_of_vendor_questions: str
    estimated_vendor_participation: str
    publish_readiness: str
    strengths: list[str] = Field(default_factory=list)
    missing_or_weak_requirements: list[str] = Field(default_factory=list)
    improvement_summary: str
    committee_reasoning: list[str] = Field(default_factory=list)


class AITenderCommitteeAgentResult(BaseModel):
    agent_name: str
    score: int = Field(ge=0, le=100)
    focus: str
    summary: str
    recommendation: str
    findings: list[TenderHealthFinding] = Field(default_factory=list)


class AITenderCommitteeOutput(BaseModel):
    final_score: int = Field(ge=0, le=100)
    final_recommendation: str
    agents: list[AITenderCommitteeAgentResult] = Field(default_factory=list)
    improvement_priorities: list[str] = Field(default_factory=list)
    committee_reasoning: list[str] = Field(default_factory=list)


class TenderHealthScore(BaseModel):
    tender_quality_score: int = Field(ge=0, le=100)
    scope_clarity: int = Field(ge=0, le=100)
    commercial_clarity: int = Field(ge=0, le=100)
    compliance_readiness: int = Field(ge=0, le=100)
    vendor_participation_score: int = Field(ge=0, le=100)
    risk_of_vendor_questions: str
    estimated_vendor_participation: str
    document_status: str = "DRAFT - Pending Buyer Approval"
    analysis_mode: str = "LLM_PRIMARY_WITH_DETERMINISTIC_FALLBACK"
    publish_readiness: str
    generated_at: str
    health_agents: list[TenderHealthAgentResult] = Field(default_factory=list)
    ai_tender_committee: AITenderCommitteeOutput | None = None
    strengths: list[str] = Field(default_factory=list)
    findings: list[TenderHealthFinding] = Field(default_factory=list)
    missing_or_weak_requirements: list[str] = Field(default_factory=list)
    improvement_summary: str
    committee_reasoning: list[str] = Field(default_factory=list)
