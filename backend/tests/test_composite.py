"""Unit tests for the composite scorer (build-order step 3)."""

from __future__ import annotations

from backend.app.scoring.composite import NEUTRAL_PRIOR, band_for, composite
from backend.app.scoring.types import NEGATIVE, POSITIVE, ReasonCode, SubScoreResult


def subs(value: int) -> dict[str, SubScoreResult]:
    names = ["growth", "stability", "compliance", "liquidity", "concentration", "leverage"]
    return {n: SubScoreResult(value=value, reason_codes=[]) for n in names}


def test_scaling_endpoints():
    assert composite(subs(100)).setu_score == 900
    assert composite(subs(0)).setu_score == 300
    assert composite(subs(50)).setu_score == 600


def test_band_thresholds():
    assert band_for(449) == "HIGH_RISK"
    assert band_for(450) == "WATCH"
    assert band_for(599) == "WATCH"
    assert band_for(600) == "GOOD"
    assert band_for(749) == "GOOD"
    assert band_for(750) == "EXCELLENT"


def test_history_confidence_regresses_toward_prior():
    full = composite(subs(90), history_confidence=1.0).setu_score
    thin = composite(subs(90), history_confidence=0.5).setu_score
    # Blending halfway to the neutral prior must pull a strong score down.
    assert thin < full
    # At confidence 0, the weighted value equals exactly the neutral prior.
    only_prior = composite(subs(90), history_confidence=0.0).setu_score
    assert only_prior == int(round(300 + NEUTRAL_PRIOR / 100 * 600))


def test_score_cap_applies():
    r = composite(subs(90), score_cap=599)
    assert r.setu_score == 599
    assert r.capped is True
    assert r.band == "WATCH"


def test_fraud_cap_forces_high_risk():
    r = composite(subs(90), fraud_cap=True)
    assert r.setu_score == 449
    assert r.band == "HIGH_RISK"
    assert r.capped is True


def test_uncapped_leaves_score_untouched():
    r = composite(subs(80))
    assert r.capped is False
    assert r.setu_score > 600


def test_reason_aggregation_orders_negatives_first():
    mixed = {
        "growth": SubScoreResult(20, [ReasonCode("TURNOVER_DECLINE", NEGATIVE, "down")]),
        "stability": SubScoreResult(15, [ReasonCode("VOLATILE_CASHFLOW", NEGATIVE, "cv")]),
        "compliance": SubScoreResult(95, [ReasonCode("ALL_FILINGS_ON_TIME", POSITIVE, "ok")]),
        "liquidity": SubScoreResult(90, [ReasonCode("STRONG_LIQUIDITY", POSITIVE, "cash")]),
        "concentration": SubScoreResult(88, [ReasonCode("DIVERSIFIED_PAYERS", POSITIVE, "div")]),
        "leverage": SubScoreResult(80, [ReasonCode("MANAGEABLE_LEVERAGE", POSITIVE, "foir")]),
    }
    r = composite(mixed)
    # Lowest sub-scores contribute their (negative) reasons first.
    assert r.reason_codes[0].direction == NEGATIVE
    assert r.reason_codes[0].code in {"VOLATILE_CASHFLOW", "TURNOVER_DECLINE"}
    assert len(r.reason_codes) <= 6
