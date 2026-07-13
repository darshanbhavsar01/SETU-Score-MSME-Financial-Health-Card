"""API + golden-contract tests (build-order step 5).

The golden files in golden/ are the frozen §7 contract. Because all data is seeded,
the API response is byte-stable except `scored_at`, which we normalise before
comparing — so any silent schema OR value drift fails the test.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")  # starlette TestClient httpx deprecation noise

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import create_app  # noqa: E402
from backend.app.repository import Repositories  # noqa: E402
from backend.app.repository.duckdb_repo import DuckdbAnalyticsRepository  # noqa: E402
from backend.app.repository.sqlite_repo import (  # noqa: E402
    SqliteApplicantRepository,
    SqliteScoreRepository,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_CASES = {
    "healthy_growth": "MSME-0001",
    "ntc_thin_file": "MSME-0041",
    "inflated_gst_fraud": "MSME-0051",
}


@pytest.fixture
def client(tmp_path) -> TestClient:
    # Isolate score writes to a temp DB so tests never touch data/app.db.
    scores = SqliteScoreRepository(db_path=tmp_path / "app.db")
    scores.initialize()
    repos = Repositories(
        applicants=SqliteApplicantRepository(),
        scores=scores,
        analytics=DuckdbAnalyticsRepository(),
    )
    return TestClient(create_app(repos=repos))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["applicants"] == 60
    assert body["data_source"] == "synthetic"


def test_list_applicants_shape(client):
    r = client.get("/applicants")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 60
    first = rows[0]
    assert {"id", "name", "sector", "history_months"} <= set(first)
    # Not yet scored → score/band are null.
    assert first["setu_score"] is None


def test_unknown_applicant_404(client):
    assert client.post("/score/MSME-9999").status_code == 404
    assert client.get("/applicants/MSME-9999").status_code == 404
    assert client.post("/validate/MSME-9999").status_code == 404


@pytest.mark.parametrize("persona,applicant_id", GOLDEN_CASES.items())
def test_score_matches_golden(client, persona, applicant_id):
    resp = client.post(f"/score/{applicant_id}")
    assert resp.status_code == 200
    payload = resp.json()
    payload["scored_at"] = "SEEDED"  # normalise the one non-deterministic field

    golden = json.loads((GOLDEN_DIR / f"score_{persona}.json").read_text(encoding="utf-8"))
    assert payload == golden, f"{persona} response drifted from golden contract"


def test_score_persisted_and_listed(client):
    client.post("/score/MSME-0001")
    # Now appears in the queue with its score, and GET /score returns the cached payload.
    row = next(a for a in client.get("/applicants").json() if a["id"] == "MSME-0001")
    assert row["setu_score"] == 809
    assert row["band"] == "EXCELLENT"
    cached = client.get("/score/MSME-0001")
    assert cached.status_code == 200
    assert cached.json()["setu_score"] == 809


def test_get_score_before_scoring_404(client):
    assert client.get("/score/MSME-0002").status_code == 404


def test_trend_endpoint(client):
    # 24 aligned monthly points; the fraud firm's declared GST rides far above bank.
    points = client.get("/applicants/MSME-0051/trend").json()
    assert len(points) == 24
    assert set(points[0]) == {"month", "gst_declared", "bank_credit", "upi_total", "net_inflow"}
    assert points[0]["gst_declared"] > 2 * points[0]["bank_credit"]
    # NTC thin file has only 8 months.
    assert len(client.get("/applicants/MSME-0041/trend").json()) == 8


def test_narrative_endpoint_defaults_to_template(client):
    # ENABLE_LLM_NARRATIVE defaults false, so this never touches the network — the
    # narrative source must be "template" and the text must mention the score.
    resp = client.post("/narrative/MSME-0001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["applicant_id"] == "MSME-0001"
    assert body["source"] == "template"
    assert "809" in body["narrative"]


def test_narrative_scores_on_demand_if_not_already_scored(client):
    # No prior POST /score/MSME-0002 — /narrative must score it itself and persist.
    resp = client.post("/narrative/MSME-0002")
    assert resp.status_code == 200
    assert client.get("/score/MSME-0002").status_code == 200


def test_narrative_unknown_applicant_404(client):
    assert client.post("/narrative/MSME-9999").status_code == 404


def test_validate_endpoint(client):
    fraud = client.post("/validate/MSME-0051").json()
    assert fraud["consistency_score"] == 0
    assert {f["code"] for f in fraud["flags"]} >= {"GST_VS_BANK", "ROUND_NUMBER"}

    healthy = client.post("/validate/MSME-0001").json()
    assert healthy["consistency_score"] == 100
