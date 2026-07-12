"""Cross-source fraud validation (CLAUDE.md §6).

Consistency checks across the three inflow views a real MSME leaves behind:
  * GST_VS_BANK  — declared GST turnover vs bank credit totals, per quarter (±25%).
  * GST_VS_UPI   — declared turnover vs UPI settlement volume (a subset of bank flow).
  * ROUND_NUMBER — suspicious round-figure filing pattern.

Output: a 0–100 consistency score + the list of triggered flags. A *hard* flag
(systematic GST over-declaration vs the money that actually moved) caps the composite
at 449 and forces REFER_FRAUD_REVIEW — that's the inflated-GST fraud story.

Operates on the same FeatureBundle the sub-scores use (monthly aligned arrays), so
the pipeline computes features once.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.app.config import (
    GST_BANK_TOLERANCE,
    GST_UPI_MAX_RATIO,
    ROUND_NUMBER_FRACTION,
    ROUND_NUMBER_UNIT,
)
from backend.app.features.builder import FeatureBundle
from backend.app.scoring.types import NEGATIVE, POSITIVE, ReasonCode


@dataclass(frozen=True)
class CrossValidationResult:
    consistency_score: int
    flags: list[ReasonCode]
    hard_flag: bool

    def as_dict(self) -> dict:
        return {
            "consistency_score": self.consistency_score,
            "flags": [f.as_dict() for f in self.flags],
        }


def _inr(x: float) -> str:
    """Compact ₹ formatting: crore / lakh."""
    if x >= 1e7:
        return f"₹{x / 1e7:.2f}Cr"
    if x >= 1e5:
        return f"₹{x / 1e5:.1f}L"
    return f"₹{x:,.0f}"


def _quarter_sums(monthly: np.ndarray) -> list[tuple[float, float]]:
    """Chunk a monthly series into (quarter) groups of 3, returning the raw sums."""
    return [monthly[i : i + 3] for i in range(0, len(monthly), 3)]


def cross_validate(f: FeatureBundle) -> CrossValidationResult:
    gst = f.gst_declared
    bank = f.bank_credit
    upi = f.upi_total

    total_gst = float(gst.sum())
    total_bank = float(bank.sum())
    total_upi = float(upi.sum())

    flags: list[ReasonCode] = []
    penalty = 0.0
    hard_flag = False

    # --- GST_VS_BANK (per quarter, ±25% band) ---
    upper = 1.0 + GST_BANK_TOLERANCE
    breached_quarters = 0
    total_quarters = 0
    for q_gst, q_bank in (
        (g.sum(), b.sum())
        for g, b in zip(_quarter_sums(gst), _quarter_sums(bank))
    ):
        total_quarters += 1
        if q_bank > 0 and (q_gst / q_bank) > upper:
            breached_quarters += 1

    overall_ratio = (total_gst / total_bank) if total_bank > 0 else 1.0
    if overall_ratio > upper and breached_quarters >= max(1, total_quarters // 2):
        hard_flag = True
        excess = overall_ratio - upper
        penalty += min(70.0, excess * 30.0)
        flags.append(ReasonCode(
            "GST_VS_BANK",
            NEGATIVE,
            f"declared GST {_inr(total_gst)} vs bank credits {_inr(total_bank)} "
            f"({overall_ratio:.1f}× ) — over-declared in {breached_quarters}/{total_quarters} quarters",
        ))

    # --- GST_VS_UPI (UPI is a subset of bank flow, so honest ratios sit ~1.5–2×) ---
    if total_upi > 0:
        gst_upi_ratio = total_gst / total_upi
        if gst_upi_ratio > GST_UPI_MAX_RATIO:
            penalty += 15.0
            flags.append(ReasonCode(
                "GST_VS_UPI",
                NEGATIVE,
                f"declared GST is {gst_upi_ratio:.1f}× UPI settlement volume "
                f"(expected ≲ {GST_UPI_MAX_RATIO:.1f}×)",
            ))

    # --- ROUND_NUMBER (exact ₹1L-multiple filings) ---
    round_hits = int(np.sum(np.isclose(gst % ROUND_NUMBER_UNIT, 0.0)))
    round_fraction = round_hits / len(gst)
    if round_fraction >= ROUND_NUMBER_FRACTION:
        penalty += 20.0
        flags.append(ReasonCode(
            "ROUND_NUMBER",
            NEGATIVE,
            f"{round_hits}/{len(gst)} GST filings are exact ₹1L round figures",
        ))

    consistency = int(round(max(0.0, min(100.0, 100.0 - penalty))))
    if not flags:
        flags.append(ReasonCode(
            "SOURCES_CONSISTENT",
            POSITIVE,
            f"GST, bank & UPI inflows reconcile (consistency {consistency}/100)",
        ))

    return CrossValidationResult(
        consistency_score=consistency,
        flags=flags,
        hard_flag=hard_flag,
    )
