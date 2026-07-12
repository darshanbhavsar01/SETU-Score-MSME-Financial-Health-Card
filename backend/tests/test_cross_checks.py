"""Tests for the cross-source fraud engine (build-order step 4).

Combines hand-built bundles (mapping mechanics) with the real seeded population
(§9: each fraud persona triggers exactly its intended flag; healthy personas none).
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.features import build_features
from backend.app.repository import get_repositories
from backend.app.validation.cross_checks import cross_validate
from backend.tests._helpers import make_bundle

HONEST_PERSONAS = {
    "healthy_growth", "seasonal_stable", "ntc_thin_file",
    "concentration_risk", "declining_stress",
}


@pytest.fixture(scope="module")
def repos():
    return get_repositories()


def flag_codes(result) -> set[str]:
    return {f.code for f in result.flags}


# --- Hand-built mechanics ------------------------------------------------------

def test_consistent_sources_no_flag_full_score():
    r = cross_validate(make_bundle())
    assert r.hard_flag is False
    assert r.consistency_score == 100
    assert flag_codes(r) == {"SOURCES_CONSISTENT"}


def test_inflated_gst_triggers_hard_flag():
    # Declared GST 4× bank credits, round ₹1L figures → all three checks fire.
    inflated = make_bundle(
        gst_declared=np.full(24, 3_200_000.0),  # bank_credit default 800k
        bank_credit=np.full(24, 800_000.0),
        upi_total=np.full(24, 400_000.0),
    )
    r = cross_validate(inflated)
    assert r.hard_flag is True
    assert r.consistency_score <= 5
    assert {"GST_VS_BANK", "GST_VS_UPI", "ROUND_NUMBER"} <= flag_codes(r)


def test_mild_overdeclaration_within_tolerance_is_clean():
    # +20% is inside the ±25% band → no hard flag.
    mild = make_bundle(gst_declared=np.full(24, 960_000.0), bank_credit=np.full(24, 800_000.0))
    r = cross_validate(mild)
    assert r.hard_flag is False
    assert "GST_VS_BANK" not in flag_codes(r)


# --- Real seeded population ----------------------------------------------------

def test_only_fraud_persona_hard_flags(repos):
    for a in repos.applicants.list_applicants():
        f = build_features(a.id, repos.analytics)
        r = cross_validate(f)
        if a.persona == "inflated_gst_fraud":
            assert r.hard_flag is True, a.id
            assert r.consistency_score <= 10
            assert {"GST_VS_BANK", "ROUND_NUMBER"} <= flag_codes(r)
        else:
            assert r.hard_flag is False, a.id


def test_honest_personas_are_fully_consistent(repos):
    for a in repos.applicants.list_applicants():
        if a.persona not in HONEST_PERSONAS:
            continue
        f = build_features(a.id, repos.analytics)
        r = cross_validate(f)
        assert r.consistency_score == 100, a.id
        assert flag_codes(r) == {"SOURCES_CONSISTENT"}, a.id
