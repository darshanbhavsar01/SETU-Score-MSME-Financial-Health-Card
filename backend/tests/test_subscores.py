"""Unit tests for the six sub-scores (build-order step 3).

Hand-built FeatureBundles with controlled inputs — no data dependency — so each
0–100 mapping and its reason codes are pinned independently of the generator.
"""

from __future__ import annotations

import numpy as np

from backend.app.features.builder import FeatureBundle
from backend.app.scoring import subscores


def make_bundle(**overrides) -> FeatureBundle:
    """A healthy 24-month firm by default; override individual arrays per test."""
    n = overrides.pop("n_months", 24)
    defaults = dict(
        applicant_id="TEST",
        n_months=n,
        blended_turnover=np.full(n, 800_000.0),
        bank_credit=np.full(n, 800_000.0),
        gst_declared=np.full(n, 800_000.0),
        upi_total=np.full(n, 480_000.0),
        net_inflow=np.full(n, 80_000.0),
        closing_balance=np.full(n, 1_500_000.0),
        monthly_obligations=np.full(n, 400_000.0),
        emi=np.full(n, 100_000.0),
        gst_late_flags=np.zeros(n, dtype=bool),
        gst_filing_gap_days=np.full(n, -2.0),
        epfo_late_flags=np.zeros(n, dtype=bool),
        payer_shares=np.full(25, 1 / 25),
        avg_monthly_inflow=800_000.0,
        avg_emi=100_000.0,
    )
    defaults.update(overrides)
    return FeatureBundle(**defaults)


def codes(result) -> set[str]:
    return {r.code for r in result.reason_codes}


# --- Growth --------------------------------------------------------------------

def test_growth_rising_scores_high():
    rising = 800_000.0 * (1.03 ** np.arange(24))
    r = subscores.growth(make_bundle(blended_turnover=rising))
    assert r.value >= 85
    assert "TURNOVER_GROWTH" in codes(r)


def test_growth_declining_scores_low():
    falling = 950_000.0 * (0.965 ** np.arange(24))
    r = subscores.growth(make_bundle(blended_turnover=falling))
    assert r.value <= 30
    assert "TURNOVER_DECLINE" in codes(r)


def test_growth_flat_is_mid_band():
    r = subscores.growth(make_bundle(blended_turnover=np.full(24, 700_000.0)))
    assert 45 <= r.value <= 65
    assert "TURNOVER_FLAT" in codes(r)


def test_growth_thin_file_flags_short_history():
    rising = 500_000.0 * (1.03 ** np.arange(8))
    r = subscores.growth(make_bundle(n_months=8, blended_turnover=rising))
    assert "SHORT_HISTORY" in codes(r)


# --- Stability -----------------------------------------------------------------

def test_stability_steady_positive_scores_high():
    net = np.full(24, 90_000.0) + np.array([2000, -2000] * 12)  # tiny variation
    r = subscores.stability(make_bundle(net_inflow=net))
    assert r.value >= 85
    assert "STABLE_CASHFLOW" in codes(r)


def test_stability_volatile_with_negative_months_scores_low():
    net = np.array([250_000, -80_000] * 12, dtype=float)
    r = subscores.stability(make_bundle(net_inflow=net))
    assert r.value <= 35
    assert "NEGATIVE_NET_MONTHS" in codes(r)


# --- Compliance ----------------------------------------------------------------

def test_compliance_all_on_time_is_top():
    r = subscores.compliance(make_bundle())
    assert r.value >= 95
    assert "ALL_FILINGS_ON_TIME" in codes(r)


def test_compliance_late_filings_penalised():
    late = np.array([True] * 8 + [False] * 16)
    r = subscores.compliance(make_bundle(gst_late_flags=late))
    assert r.value < 90
    assert "GST_LATE_FILINGS" in codes(r)


# --- Liquidity -----------------------------------------------------------------

def test_liquidity_strong_stable_balance_is_top():
    r = subscores.liquidity(make_bundle())
    assert r.value >= 90
    assert "STRONG_LIQUIDITY" in codes(r)


def test_liquidity_drawdown_penalised():
    drawing_down = np.linspace(2_000_000.0, 500_000.0, 24)
    r = subscores.liquidity(make_bundle(closing_balance=drawing_down))
    assert r.value <= 30
    assert "DECLINING_CASH_BALANCE" in codes(r)


# --- Concentration -------------------------------------------------------------

def test_concentration_diversified_is_high():
    r = subscores.concentration(make_bundle(payer_shares=np.full(25, 1 / 25)))
    assert r.value >= 85
    assert "DIVERSIFIED_PAYERS" in codes(r)


def test_concentration_single_dominant_payer_is_low():
    shares = np.array([0.75] + [0.25 / 7] * 7)
    r = subscores.concentration(make_bundle(payer_shares=shares))
    assert r.value <= 40
    assert "HIGH_CUSTOMER_CONCENTRATION" in codes(r)


# --- Leverage ------------------------------------------------------------------

def test_leverage_no_debt_is_perfect():
    r = subscores.leverage(make_bundle(avg_emi=0.0, emi=np.zeros(24)))
    assert r.value == 100
    assert "NO_EXISTING_DEBT" in codes(r)


def test_leverage_high_foir_is_low():
    r = subscores.leverage(make_bundle(avg_emi=400_000.0, avg_monthly_inflow=1_000_000.0))
    assert r.value <= 60
    assert "HIGH_EMI_BURDEN" in codes(r)


def test_all_subscores_returns_six_in_range():
    result = subscores.all_subscores(make_bundle())
    assert set(result) == {"growth", "stability", "compliance", "liquidity",
                           "concentration", "leverage"}
    for res in result.values():
        assert 0 <= res.value <= 100
        assert 1 <= len(res.reason_codes) <= 3
