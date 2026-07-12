"""Working-capital limit recommendation (CLAUDE.md §6).

    limit = clamp(k × avg_verified_monthly_net_inflow × stability_multiplier, caps)

'Verified' inflow is the *minimum* of GST-declared and bank-observed inflow each month
— conservative by construction, so an inflated GST filing can never inflate the limit
(the fraud persona's limit falls back to real bank flow). The formula is surfaced in
the UI tooltip; visible prudence is the point.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.app.config import (
    LIMIT_MAX_INR,
    LIMIT_MIN_INR,
    LIMIT_MULTIPLE,
    LIMIT_ROUNDING_INR,
    LIMIT_TENOR_MONTHS,
)
from backend.app.features.builder import FeatureBundle


@dataclass(frozen=True)
class LimitRecommendation:
    amount_inr: int
    tenor_months: int
    basis: str

    def as_dict(self) -> dict:
        return {
            "amount_inr": self.amount_inr,
            "tenor_months": self.tenor_months,
            "basis": self.basis,
        }


def _round_to(x: float, unit: int) -> int:
    return int(round(x / unit) * unit)


def stability_multiplier(stability_score: int) -> float:
    """Map the 0–100 stability sub-score to a 0.7–1.3 multiplier: unstable cash flow
    shrinks the limit, steady cash flow modestly expands it."""
    return 0.7 + 0.6 * (stability_score / 100.0)


def recommend_limit(f: FeatureBundle, stability_score: int) -> LimitRecommendation:
    # Conservative verified inflow: min(GST-declared, bank-observed) per month.
    verified_inflow = np.minimum(f.gst_declared, f.bank_credit)
    monthly_debit = f.bank_credit - f.net_inflow  # reconstruct total outflow
    verified_net = np.clip(verified_inflow - monthly_debit, 0.0, None)
    avg_verified_net = float(np.mean(verified_net))

    mult = stability_multiplier(stability_score)
    raw = LIMIT_MULTIPLE * avg_verified_net * mult

    # Extra prudence: never exceed 2× average verified *gross* monthly inflow.
    gross_cap = 2.0 * float(np.mean(verified_inflow))
    amount = min(raw, gross_cap, LIMIT_MAX_INR)
    amount = max(amount, 0.0)
    amount = _round_to(amount, LIMIT_ROUNDING_INR)
    if 0 < amount < LIMIT_MIN_INR:
        amount = LIMIT_MIN_INR

    basis = (
        f"{LIMIT_MULTIPLE:.0f} × avg verified monthly net inflow "
        f"(₹{avg_verified_net:,.0f}, min of GST & bank) × stability multiplier "
        f"{mult:.2f}; capped at 2× gross inflow and ₹{LIMIT_MAX_INR:,}"
    )
    return LimitRecommendation(
        amount_inr=int(amount),
        tenor_months=LIMIT_TENOR_MONTHS,
        basis=basis,
    )
