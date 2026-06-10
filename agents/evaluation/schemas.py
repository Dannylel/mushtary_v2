from typing import Literal
from pydantic import BaseModel, Field


# ── TENDER POLICY (Buyer-Admin configures, max 2 saved policies) ───────────────

class DisqualificationCriteria(BaseModel):
    """
    Buyer selects from this list — multi-select dropdown.
    All selected criteria are hard disqualifiers (vendor excluded before scoring).
    Policies can be saved and reused. Max 2 saved policies per org (additional charged).
    """
    late_submission: bool = True
    missing_mandatory_docs: bool = True
    no_bid_security: bool = False           # bank guarantee / LC / SME certificate
    non_compliant_format: bool = True
    fails_minimum_eligibility: bool = True  # turnover, certifications, local content
    legal_violations: bool = True           # blacklisted, debarred, fraud/corruption
    conflict_of_interest: bool = True
    non_compliant_technical_specs: bool = True
    non_compliant_pricing: bool = False     # unpriced items, forbidden price variations
    insufficient_experience: bool = False   # min years, certifications, KSA presence
    custom_criteria: list[str] = []         # buyer writes free-text additional rules


class TenderPolicy(BaseModel):
    """
    Buyer-Admin configures this per tender.
    Default is applied if buyer doesn't customise.
    Policy can be saved (max 2 per org).
    """
    policy_id: str | None = None
    policy_name: str | None = None

    # Technical vs Financial split — buyer sets, default 70/30
    technical_weight_percent: float = Field(default=70.0, ge=0.0, le=100.0)
    financial_weight_percent: float = Field(default=30.0, ge=0.0, le=100.0)

    # Pricing evaluation approach — buyer sets
    pricing_approach: Literal[
        "lowest_cost",
        "best_value",
        "custom_formula",
    ] = "best_value"
    pricing_formula_note: str = ""          # buyer describes custom formula if used

    # Preferred detail level in evaluation output
    output_detail: Literal["high_level_summary", "detailed_with_justification"] = "detailed_with_justification"

    # Disqualification criteria
    disqualification: DisqualificationCriteria = DisqualificationCriteria()


# ── VRI — Vendor Reputation Index (0–100) ─────────────────────────────────────

class VRIComponents(BaseModel):
    """8-component composite score. Weights must sum to 100."""
    performance_rating: float = Field(ge=0.0, le=100.0)        # 20% weight
    compliance_and_licenses: float = Field(ge=0.0, le=100.0)   # 15%
    institutional_verification: float = Field(ge=0.0, le=100.0) # 15%
    delivery_performance: float = Field(ge=0.0, le=100.0)      # 15%
    financial_strength: float = Field(ge=0.0, le=100.0)        # 10%
    tender_success_rate: float = Field(ge=0.0, le=100.0)       # 10%
    contract_history: float = Field(ge=0.0, le=100.0)          # 10%
    ai_risk_signals: float = Field(ge=0.0, le=100.0)           # 5%

    @property
    def composite(self) -> float:
        """VRI = Σ (component × weight)"""
        return round(
            self.performance_rating       * 0.20 +
            self.compliance_and_licenses  * 0.15 +
            self.institutional_verification * 0.15 +
            self.delivery_performance     * 0.15 +
            self.financial_strength       * 0.10 +
            self.tender_success_rate      * 0.10 +
            self.contract_history         * 0.10 +
            self.ai_risk_signals          * 0.05,
            2,
        )


class VRIScore(BaseModel):
    vendor_id: str
    overall: float = Field(ge=0.0, le=100.0)
    category_specific: float = Field(ge=0.0, le=100.0)  # VRI for this tender's category
    components: VRIComponents
    level: Literal[
        "elite_vendor",       # 85–100
        "strategic_vendor",   # 75–84
        "trusted_vendor",     # 65–74
        "verified_vendor",    # 50–64
        "under_review",       # <50
    ]


# ── INPUT ──────────────────────────────────────────────────────────────────────

class EvaluationCriterion(BaseModel):
    id: str
    name: str
    description: str
    weight_percent: float = Field(ge=0.0, le=100.0)
    mandatory: bool = False     # if True and vendor fails this, it's a disqualifier


class SubmissionSummary(BaseModel):
    """
    Sanitized view of a vendor submission — no raw file content reaches the LLM.
    Backend extracts key fields; documents referenced by metadata only.
    """
    vendor_id: str
    submission_id: str
    technical_response: str
    commercial_summary: str
    proposed_price_sar: float | None = None
    declared_experience_years: int | None = None
    certifications: list[str] = []
    submitted_doc_types: list[str] = []
    timeline_commitment_days: int | None = None


class VendorScoringInput(BaseModel):
    """Input for scoring a SINGLE vendor — runs in isolation, never sees other submissions."""
    tender_id: str
    tender_category: str            # e.g. "IT Infrastructure"
    criteria: list[EvaluationCriterion]
    submission: SubmissionSummary
    vri: VRIScore                   # pre-computed VRI for this vendor
    policy: TenderPolicy            # buyer's configured policy
    market_avg_price_sar: float | None = None   # for price competitiveness calc


class RankingInput(BaseModel):
    """Input for the final ranking step — aggregates all per-vendor scores."""
    tender_id: str
    policy: TenderPolicy
    vendor_scores: list["VendorScore"]


# ── OUTPUT ─────────────────────────────────────────────────────────────────────

class DisqualificationResult(BaseModel):
    disqualified: bool
    reasons: list[str] = []


class FitScoreBreakdown(BaseModel):
    """
    Vendor Fit Score = (VRI × 40%) + (Requirement Match × 30%)
                     + (Proposal Quality × 20%) + (Price Competitiveness × 10%)
    """
    vri_component: float            # VRI score contribution (40%)
    requirement_match: float        # 0–100
    proposal_quality: float         # 0–100
    price_competitiveness: float    # 0–100
    risk_adjustment: float          # negative penalty (e.g. -5)
    final_fit_score: float          # 0–100 after risk adjustment


class CriterionScore(BaseModel):
    criterion_id: str
    criterion_name: str
    score: float = Field(ge=0.0, le=10.0)
    reasoning: str
    missing_requirements: list[str] = []


class VendorScore(BaseModel):
    vendor_id: str
    submission_id: str
    disqualification: DisqualificationResult
    scores_by_criterion: list[CriterionScore]       # detailed technical scoring
    fit_score_breakdown: FitScoreBreakdown          # Vendor Fit Score components
    weighted_total: float                           # 0–100 final score
    risk_level: Literal["low", "medium", "high"]
    overall_reasoning: str
    missing_requirements: list[str]
    trace_id: str


class RankedVendor(BaseModel):
    rank: int
    vendor_id: str
    weighted_total: float
    vri: float
    risk_level: str
    summary: str                    # one-line explainability for buyer


class RankedResult(BaseModel):
    tender_id: str
    ranked_list: list[RankedVendor]
    disqualified_vendors: list[str]         # vendor_ids excluded before scoring
    recommendation: str                     # buyer-facing recommendation paragraph
    explainability_summary: str             # how scores were derived
    output_detail: str                      # mirrors policy.output_detail used
    ai_generated: bool = True
    buyer_approved: bool = False            # must be True before award is recorded
    trace_id: str


# ── Safe fallbacks ─────────────────────────────────────────────────────────────

SCORE_FALLBACK = VendorScore(
    vendor_id="unknown",
    submission_id="unknown",
    disqualification=DisqualificationResult(disqualified=False),
    scores_by_criterion=[],
    fit_score_breakdown=FitScoreBreakdown(
        vri_component=0,
        requirement_match=0,
        proposal_quality=0,
        price_competitiveness=0,
        risk_adjustment=0,
        final_fit_score=0,
    ),
    weighted_total=0.0,
    risk_level="high",
    overall_reasoning="AI scoring failed — manual evaluation required.",
    missing_requirements=["guardrail_failure"],
    trace_id="fallback",
)

RANKING_FALLBACK = RankedResult(
    tender_id="unknown",
    ranked_list=[],
    disqualified_vendors=[],
    recommendation="AI ranking failed — please evaluate submissions manually.",
    explainability_summary="",
    output_detail="high_level_summary",
    trace_id="fallback",
)
