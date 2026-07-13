"""Pydantic API contract (CLAUDE.md §7).

These models ARE the frozen contract between backend and frontend. The golden
contract test asserts the shape never drifts silently. The frontend renders
exclusively from ScoreResponse.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReasonCodeModel(BaseModel):
    code: str
    direction: str  # "positive" | "negative" | "neutral"
    evidence: str


class SubScores(BaseModel):
    growth: int
    stability: int
    compliance: int
    liquidity: int
    concentration: int
    leverage: int


class CrossValidationModel(BaseModel):
    consistency_score: int
    flags: list[ReasonCodeModel]


class LimitRecommendationModel(BaseModel):
    amount_inr: int
    tenor_months: int
    basis: str


class ScoreResponse(BaseModel):
    applicant_id: str
    setu_score: int
    band: str
    sub_scores: SubScores
    reason_codes: list[ReasonCodeModel]
    cross_validation: CrossValidationModel
    limit_recommendation: LimitRecommendationModel
    recommendation: str
    data_source: str
    scored_at: str


class ApplicantSummary(BaseModel):
    """Officer-console queue row. persona is present only when not in prod-mode (§7);
    setu_score/band are present only once the applicant has been scored."""

    id: str
    name: str
    sector: str
    history_months: int
    persona: str | None = None
    setu_score: int | None = None
    band: str | None = None
    recommendation: str | None = None


class TrendPoint(BaseModel):
    """One month of the inflow trend. Plotting declared GST vs observed bank credits
    makes the fraud persona's over-declaration visible as a diverging line."""

    month: str
    gst_declared: float
    bank_credit: float
    upi_total: float
    net_inflow: float


class HealthResponse(BaseModel):
    status: str = "ok"
    applicants: int
    data_source: str
