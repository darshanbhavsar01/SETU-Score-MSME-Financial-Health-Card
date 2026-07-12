"""Composite SETU score (CLAUDE.md §6).

Weighted average of the six 0–100 sub-scores, rescaled to a 300–900 credit range,
with a band label. A hard fraud flag (from cross_checks) can cap the composite at
FRAUD_CAP_SCORE — that capping is applied by the caller (the pipeline), keeping this
function a pure weight-and-scale computation.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.config import (
    BANDS,
    FRAUD_CAP_SCORE,
    SCORE_SCALE_MAX,
    SCORE_SCALE_MIN,
    SUBSCORE_WEIGHTS,
)
from backend.app.scoring.types import ReasonCode, SubScoreResult


@dataclass(frozen=True)
class CompositeResult:
    setu_score: int
    band: str
    sub_scores: dict[str, int]
    reason_codes: list[ReasonCode]
    capped: bool = False


def band_for(score: int) -> str:
    for label, upper in BANDS:
        if score < upper:
            return label
    return BANDS[-1][0]


# A thin-file firm's ratios can look pristine, but limited track record warrants
# conservatism. We regress the weighted score toward this neutral prior in proportion
# to how much history is missing (history_confidence < 1). This is the explainable
# "shorter-history caveat" (§5) rather than a magic penalty.
NEUTRAL_PRIOR: float = 55.0


def _weighted_0_100(sub_values: dict[str, int]) -> float:
    return sum(sub_values[name] * w for name, w in SUBSCORE_WEIGHTS.items())


def _scale(value_0_100: float) -> int:
    span = SCORE_SCALE_MAX - SCORE_SCALE_MIN
    return int(round(SCORE_SCALE_MIN + (value_0_100 / 100.0) * span))


def _aggregate_reasons(sub_scores: dict[str, SubScoreResult]) -> list[ReasonCode]:
    """Surface the most decision-relevant reason codes across all sub-scores:
    the strongest negatives first (lowest sub-scores), then supporting positives."""
    ordered = sorted(sub_scores.items(), key=lambda kv: kv[1].value)
    negatives: list[ReasonCode] = []
    positives: list[ReasonCode] = []
    for _, res in ordered:
        for rc in res.reason_codes:
            (negatives if rc.direction == "negative" else positives).append(rc)
    return (negatives + positives)[:6]


def composite(
    sub_scores: dict[str, SubScoreResult],
    fraud_cap: bool = False,
    history_confidence: float = 1.0,
    score_cap: int | None = None,
) -> CompositeResult:
    """Combine sub-scores into a 300–900 composite.

    - history_confidence ∈ (0, 1]: blend toward NEUTRAL_PRIOR for thin files.
    - score_cap: policy ceiling (e.g. extreme customer concentration) applied before
      the fraud cap.
    - fraud_cap: hard fraud flag → cap at FRAUD_CAP_SCORE.
    """
    sub_values = {name: res.value for name, res in sub_scores.items()}
    weighted = _weighted_0_100(sub_values)
    weighted = weighted * history_confidence + NEUTRAL_PRIOR * (1.0 - history_confidence)
    raw = _scale(weighted)

    capped = False
    score = raw
    if score_cap is not None and score > score_cap:
        score = score_cap
        capped = True
    if fraud_cap and score > FRAUD_CAP_SCORE:
        score = FRAUD_CAP_SCORE
        capped = True

    return CompositeResult(
        setu_score=score,
        band=band_for(score),
        sub_scores=sub_values,
        reason_codes=_aggregate_reasons(sub_scores),
        capped=capped,
    )
