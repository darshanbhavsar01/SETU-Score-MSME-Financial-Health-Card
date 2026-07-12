"""Scoring pipeline — the single orchestrator (CLAUDE.md §6, §7).

Ties the layers together for one applicant: features → sub-scores → cross-validation
→ composite (with policy overlays) → limit → assembled API payload. Route handlers
stay thin; this is a pure computation per request (no write-then-read state, so it is
Cloud Run-safe, §13).
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from backend.app.config import (
    CONCENTRATION_CAP_SCORE,
    CONCENTRATION_CAP_TOP_SHARE,
    DATA_SOURCE_LABEL,
)
from backend.app.features import build_features
from backend.app.repository import Repositories
from backend.app.scoring.composite import composite
from backend.app.scoring.limits import recommend_limit
from backend.app.scoring.subscores import all_subscores
from backend.app.validation.cross_checks import cross_validate


def _history_confidence(n_months: int) -> float:
    """Thin files are scored conservatively: linear in history completeness, floored
    at 0.5 so an 8-month file regresses halfway toward the neutral prior."""
    return float(np.clip(n_months / 24.0, 0.5, 1.0))


def _recommendation(band: str, hard_fraud: bool) -> str:
    if hard_fraud:
        return "REFER_FRAUD_REVIEW"
    return {
        "HIGH_RISK": "DECLINE",
        "WATCH": "MONITOR",
        "GOOD": "APPROVE_WITH_LIMIT",
        "EXCELLENT": "APPROVE_WITH_LIMIT",
    }[band]


def score_applicant(applicant_id: str, repos: Repositories) -> dict:
    """Run the full pipeline and return the API payload dict (§7 shape)."""
    f = build_features(applicant_id, repos.analytics)
    subs = all_subscores(f)
    cv = cross_validate(f)

    top_share = float(np.max(f.payer_shares)) if f.payer_shares.size else 0.0
    score_cap = CONCENTRATION_CAP_SCORE if top_share >= CONCENTRATION_CAP_TOP_SHARE else None

    comp = composite(
        subs,
        fraud_cap=cv.hard_flag,
        history_confidence=_history_confidence(f.n_months),
        score_cap=score_cap,
    )

    recommendation = _recommendation(comp.band, cv.hard_flag)

    limit = recommend_limit(f, subs["stability"].value)
    if cv.hard_flag:
        # Withhold the limit pending fraud review — never extend credit on figures
        # we have flagged as inflated.
        limit = limit.__class__(
            amount_inr=0,
            tenor_months=limit.tenor_months,
            basis="withheld pending fraud review (GST inflation flagged)",
        )

    return {
        "applicant_id": applicant_id,
        "setu_score": comp.setu_score,
        "band": comp.band,
        "sub_scores": comp.sub_scores,
        "reason_codes": [rc.as_dict() for rc in comp.reason_codes],
        "cross_validation": cv.as_dict(),
        "limit_recommendation": limit.as_dict(),
        "recommendation": recommendation,
        "data_source": DATA_SOURCE_LABEL,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }
