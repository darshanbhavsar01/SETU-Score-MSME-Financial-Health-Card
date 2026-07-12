"""Tests for the working-capital limit recommendation (build-order step 4)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.config import LIMIT_MAX_INR, LIMIT_TENOR_MONTHS
from backend.app.scoring.limits import recommend_limit, stability_multiplier
from backend.tests._helpers import make_bundle


def test_basic_limit_is_positive_and_bounded():
    r = recommend_limit(make_bundle(), stability_score=60)
    assert 0 < r.amount_inr <= LIMIT_MAX_INR
    assert r.tenor_months == LIMIT_TENOR_MONTHS
    assert "min of GST & bank" in r.basis


def test_inflated_gst_does_not_inflate_limit():
    """The conservative min(GST, bank) basis: a 4× inflated GST filing must yield the
    same limit as honest filing, because bank flow is the binding minimum."""
    honest = recommend_limit(
        make_bundle(gst_declared=np.full(24, 800_000.0), bank_credit=np.full(24, 800_000.0)),
        stability_score=60,
    )
    inflated = recommend_limit(
        make_bundle(gst_declared=np.full(24, 3_200_000.0), bank_credit=np.full(24, 800_000.0)),
        stability_score=60,
    )
    assert inflated.amount_inr == honest.amount_inr


def test_lower_gst_than_bank_binds_the_limit():
    """If GST is the smaller of the two, it (not bank) sets verified inflow."""
    low_gst = recommend_limit(
        make_bundle(gst_declared=np.full(24, 500_000.0), bank_credit=np.full(24, 800_000.0),
                    net_inflow=np.full(24, 80_000.0)),
        stability_score=60,
    )
    high_gst = recommend_limit(
        make_bundle(gst_declared=np.full(24, 800_000.0), bank_credit=np.full(24, 800_000.0),
                    net_inflow=np.full(24, 80_000.0)),
        stability_score=60,
    )
    assert low_gst.amount_inr < high_gst.amount_inr


def test_stability_multiplier_monotonic():
    assert stability_multiplier(0) < stability_multiplier(50) < stability_multiplier(100)
    assert stability_multiplier(0) == pytest.approx(0.7)
    assert stability_multiplier(100) == pytest.approx(1.3)


def test_stability_scales_the_limit():
    steady = recommend_limit(make_bundle(), stability_score=100)
    shaky = recommend_limit(make_bundle(), stability_score=10)
    assert steady.amount_inr > shaky.amount_inr


def test_negative_net_inflow_floors_at_zero_or_min():
    # A firm with no retained cash should not get a large limit.
    broke = make_bundle(net_inflow=np.full(24, -50_000.0))
    r = recommend_limit(broke, stability_score=30)
    assert r.amount_inr == 0
