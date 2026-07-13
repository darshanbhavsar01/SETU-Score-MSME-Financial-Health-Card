"""Small formatting helpers shared by the narrative templates (and anything else
server-side that needs to render a human-readable figure). Mirrors the presentation
logic in frontend/src/format.ts — kept in sync by hand since it's a handful of
one-line pure functions, not worth a codegen step at POC scale.
"""

from __future__ import annotations


def inr(amount: float) -> str:
    """Compact ₹ formatting: ₹1.23Cr / ₹4.5L / ₹8,000."""
    if amount >= 1e7:
        return f"₹{amount / 1e7:.2f}Cr"
    if amount >= 1e5:
        return f"₹{amount / 1e5:.1f}L"
    return f"₹{amount:,.0f}"


_RECOMMENDATION_LABELS = {
    "APPROVE_WITH_LIMIT": "Approve with limit",
    "MONITOR": "Monitor",
    "DECLINE": "Decline",
    "REFER_FRAUD_REVIEW": "Refer — fraud review",
}


def recommendation_label(reco: str) -> str:
    return _RECOMMENDATION_LABELS.get(reco, reco)
