"""Tests for the repository layer (build-order step 2).

Proves the SQLite + DuckDB implementations are real: they read the seeded population,
push aggregations into DuckDB correctly, and round-trip score payloads/flags.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.repository.base import Applicant
from backend.app.repository.duckdb_repo import DuckdbAnalyticsRepository
from backend.app.repository.sqlite_repo import (
    SqliteApplicantRepository,
    SqliteScoreRepository,
)
from datagen.personas import total_msme_count


@pytest.fixture(scope="module")
def applicants() -> SqliteApplicantRepository:
    return SqliteApplicantRepository()


@pytest.fixture(scope="module")
def analytics() -> DuckdbAnalyticsRepository:
    return DuckdbAnalyticsRepository()


@pytest.fixture
def scores(tmp_path) -> SqliteScoreRepository:
    repo = SqliteScoreRepository(db_path=tmp_path / "app.db")
    repo.initialize()
    return repo


def _first_of_persona(applicants: SqliteApplicantRepository, persona: str) -> Applicant:
    return next(a for a in applicants.list_applicants() if a.persona == persona)


# --- ApplicantRepository -------------------------------------------------------

def test_list_applicants_returns_full_population(applicants):
    all_apps = applicants.list_applicants()
    assert len(all_apps) == total_msme_count() == 60
    assert all(isinstance(a, Applicant) for a in all_apps)
    assert all(a.data_source == "synthetic" for a in all_apps)
    # sorted by id and unique
    ids = [a.id for a in all_apps]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_get_applicant_and_exists(applicants):
    one = applicants.list_applicants()[0]
    fetched = applicants.get_applicant(one.id)
    assert fetched == one
    assert applicants.exists(one.id) is True


def test_missing_applicant(applicants):
    assert applicants.get_applicant("MSME-9999") is None
    assert applicants.exists("MSME-9999") is False


# --- AnalyticsRepository -------------------------------------------------------

def test_raw_pulls_match_history_length(applicants, analytics):
    thin = _first_of_persona(applicants, "ntc_thin_file")
    healthy = _first_of_persona(applicants, "healthy_growth")

    assert len(analytics.gst_returns(thin.id)) == thin.history_months == 8
    assert len(analytics.gst_returns(healthy.id)) == healthy.history_months == 24
    assert len(analytics.epfo_payroll(healthy.id)) == 24
    assert not analytics.upi_settlements(healthy.id).empty
    assert not analytics.bank_txns(healthy.id).empty


def test_bank_monthly_aggregation(applicants, analytics):
    healthy = _first_of_persona(applicants, "healthy_growth")
    bm = analytics.bank_monthly(healthy.id)
    assert len(bm) == healthy.history_months
    expected_cols = {"month", "credit", "debit", "emi", "salary", "rent",
                     "supplier", "closing_balance"}
    assert expected_cols.issubset(bm.columns)
    assert (bm.credit > 0).all()
    assert (bm.closing_balance >= 0).all()
    # DuckDB month truncation yields strictly increasing month starts.
    assert bm.month.is_monotonic_increasing


def test_ntc_persona_has_no_emi(applicants, analytics):
    thin = _first_of_persona(applicants, "ntc_thin_file")
    bm = analytics.bank_monthly(thin.id)
    assert (bm.emi == 0).all()  # "no loans ever" persona


def test_upi_payer_totals_shares_and_concentration(applicants, analytics):
    conc = _first_of_persona(applicants, "concentration_risk")
    healthy = _first_of_persona(applicants, "healthy_growth")

    conc_totals = analytics.upi_payer_totals(conc.id)
    assert conc_totals.share.sum() == pytest.approx(1.0)
    # ordered descending -> first row is the dominant payer
    assert conc_totals.iloc[0].share >= 0.6

    healthy_totals = analytics.upi_payer_totals(healthy.id)
    assert healthy_totals.iloc[0].share < 0.55  # diversified


def test_upi_monthly_totals_positive(applicants, analytics):
    healthy = _first_of_persona(applicants, "healthy_growth")
    um = analytics.upi_monthly(healthy.id)
    assert len(um) == healthy.history_months
    assert (um.upi_total > 0).all()


# --- ScoreRepository -----------------------------------------------------------

def _sample_payload() -> dict:
    return {
        "applicant_id": "MSME-0001",
        "setu_score": 712,
        "band": "GOOD",
        "sub_scores": {"growth": 74, "stability": 68},
        "reason_codes": [{"code": "GST_ON_TIME", "direction": "positive", "evidence": "12/12"}],
        "cross_validation": {
            "consistency_score": 94,
            "flags": [{"code": "GST_VS_BANK", "direction": "negative", "evidence": "within band"}],
        },
        "limit_recommendation": {"amount_inr": 800000, "tenor_months": 12, "basis": "min(GST, bank)"},
        "recommendation": "APPROVE_WITH_LIMIT",
        "data_source": "synthetic",
        "scored_at": "2026-07-13T00:00:00+00:00",
    }


def test_score_roundtrip(scores):
    payload = _sample_payload()
    scores.save_score("MSME-0001", payload)

    assert scores.get_score("MSME-0001") == payload
    assert scores.get_score("MSME-0002") is None

    summaries = scores.list_scored()
    assert len(summaries) == 1
    assert summaries[0].setu_score == 712
    assert summaries[0].band == "GOOD"

    flags = scores.get_flags("MSME-0001")
    assert len(flags) == 1
    assert flags[0]["code"] == "GST_VS_BANK"


def test_save_score_is_idempotent_upsert(scores):
    payload = _sample_payload()
    scores.save_score("MSME-0001", payload)
    updated = dict(payload, setu_score=430, band="HIGH_RISK",
                   cross_validation={"consistency_score": 40, "flags": []})
    scores.save_score("MSME-0001", updated)

    assert len(scores.list_scored()) == 1  # replaced, not duplicated
    assert scores.get_score("MSME-0001")["setu_score"] == 430
    assert scores.get_flags("MSME-0001") == []  # old flags cleared


def test_save_score_accepts_explicit_flags(scores):
    payload = _sample_payload()
    explicit = [{"code": "ROUND_NUMBER", "direction": "negative", "evidence": "3 round filings"}]
    scores.save_score("MSME-0055", payload, flags=explicit)
    got = scores.get_flags("MSME-0055")
    assert [f["code"] for f in got] == ["ROUND_NUMBER"]
