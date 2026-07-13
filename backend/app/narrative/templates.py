"""Deterministic reason-code narrative (CLAUDE.md §8).

The default, always-available path: a plain-English officer summary built purely
from the already-computed score payload (aggregates only — no raw transactions).
This is what the demo runs on with zero API keys; gemini.py may optionally polish
this exact text but the pipeline must be fully presentable on templates alone.
"""

from __future__ import annotations

from backend.app.format_shared import inr, recommendation_label

_POSITIVE_LEAD = "Overall the profile is strong."
_MIXED_LEAD = "The profile shows a mix of strengths and concerns."
_WEAK_LEAD = "The profile shows material weaknesses."


def _lead_for_band(band: str) -> str:
    return {
        "EXCELLENT": _POSITIVE_LEAD,
        "GOOD": _POSITIVE_LEAD,
        "WATCH": _MIXED_LEAD,
        "HIGH_RISK": _WEAK_LEAD,
    }.get(band, _MIXED_LEAD)


def build_narrative(payload: dict) -> str:
    """payload is the /score API response dict (or equivalent). Pure function of
    its aggregate fields — never touches raw GST/UPI/bank/EPFO rows."""
    applicant_id = payload["applicant_id"]
    score = payload["setu_score"]
    band = payload["band"].replace("_", " ").title()
    reco = recommendation_label(payload["recommendation"])
    cross = payload["cross_validation"]
    limit = payload["limit_recommendation"]
    reasons = payload.get("reason_codes", [])

    negatives = [r["evidence"] for r in reasons if r.get("direction") == "negative"][:2]
    positives = [r["evidence"] for r in reasons if r.get("direction") == "positive"][:2]

    parts: list[str] = [
        f"{applicant_id} scores {score} on the SETU scale ({band} band). "
        f"{_lead_for_band(payload['band'])}"
    ]

    if positives:
        parts.append("Key strengths: " + "; ".join(positives) + ".")
    if negatives:
        parts.append("Key concerns: " + "; ".join(negatives) + ".")

    if cross["flags"] and any(f.get("direction") == "negative" for f in cross["flags"]):
        parts.append(
            f"Cross-source validation raised {len(cross['flags'])} flag(s) "
            f"(consistency {cross['consistency_score']}/100) — GST filings do not "
            f"reconcile with observed bank and UPI inflows."
        )
    else:
        parts.append(
            f"GST, bank, and UPI inflows reconcile (consistency {cross['consistency_score']}/100)."
        )

    if limit["amount_inr"] > 0:
        parts.append(
            f"Recommended working-capital limit: {inr(limit['amount_inr'])} over "
            f"{limit['tenor_months']} months, based on {limit['basis']}."
        )
    else:
        parts.append("No limit is recommended at this time.")

    parts.append(f"Recommendation: {reco}.")
    return " ".join(parts)
