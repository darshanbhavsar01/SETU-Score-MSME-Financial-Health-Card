"""End-to-end persona-band smoke test (build-order step 5, §9).

Scores all 60 seeded MSMEs through the full pipeline and asserts the §5 outcomes
hold: each persona lands in its expected band, the bands rank-order by risk with
clean separation, and only the fraud persona is flagged/capped.

This is our honest "the pipeline rank-orders correctly on seeded personas" proof —
NOT a claim of real-world accuracy (guardrail #3).
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from backend.app.repository import get_repositories
from backend.app.scoring.pipeline import score_applicant
from datagen.personas import PERSONAS_BY_KEY


@pytest.fixture(scope="module")
def scored() -> dict[str, list[dict]]:
    repos = get_repositories()
    by_persona: dict[str, list[dict]] = defaultdict(list)
    for a in repos.applicants.list_applicants():
        by_persona[a.persona].append(score_applicant(a.id, repos))
    return by_persona


def test_every_persona_present(scored):
    assert set(scored) == set(PERSONAS_BY_KEY)
    assert all(len(v) == 10 for v in scored.values())


@pytest.mark.parametrize("persona", PERSONAS_BY_KEY)
def test_persona_lands_in_expected_band(scored, persona):
    cfg = PERSONAS_BY_KEY[persona]
    for payload in scored[persona]:
        assert payload["band"] == cfg.expected_band, (persona, payload["applicant_id"])
        assert cfg.expected_score_min <= payload["setu_score"] <= cfg.expected_score_max


def test_fraud_persona_flagged_and_capped(scored):
    for payload in scored["inflated_gst_fraud"]:
        assert payload["recommendation"] == "REFER_FRAUD_REVIEW"
        assert payload["setu_score"] <= 449
        assert payload["cross_validation"]["consistency_score"] == 0
        codes = {f["code"] for f in payload["cross_validation"]["flags"]}
        assert "GST_VS_BANK" in codes
        assert payload["limit_recommendation"]["amount_inr"] == 0


def test_only_fraud_persona_is_capped(scored):
    for persona, payloads in scored.items():
        if persona == "inflated_gst_fraud":
            continue
        for p in payloads:
            assert p["recommendation"] != "REFER_FRAUD_REVIEW", (persona, p["applicant_id"])
            assert p["cross_validation"]["consistency_score"] == 100


def _scores(scored, persona) -> list[int]:
    return [p["setu_score"] for p in scored[persona]]


def test_bands_rank_order_with_clean_separation(scored):
    excellent = _scores(scored, "healthy_growth")
    good = _scores(scored, "seasonal_stable") + _scores(scored, "ntc_thin_file")
    watch = _scores(scored, "concentration_risk") + _scores(scored, "declining_stress")
    fraud = _scores(scored, "inflated_gst_fraud")

    # Strictly separated bands: EXCELLENT > GOOD > WATCH > fraud (capped).
    assert min(excellent) > max(good)
    assert min(good) > max(watch)
    assert min(watch) > max(fraud)
