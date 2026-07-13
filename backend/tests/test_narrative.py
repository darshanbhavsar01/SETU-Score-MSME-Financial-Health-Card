"""Tests for the narrative layer (build-order step 8).

templates.py is tested directly against the golden payloads (pure function, no
mocking needed). gemini.py's cascade logic is tested against a FAKE genai client —
never a real network call — so the suite stays fast, deterministic, and never
burns the real (budget-capped, SQLite-persisted) call counter.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from backend.app.narrative.templates import build_narrative
from backend.app.narrative.usage_store import GeminiUsageStore

GOLDEN_DIR = Path(__file__).parent / "golden"


def load(persona: str) -> dict:
    return json.loads((GOLDEN_DIR / f"score_{persona}.json").read_text(encoding="utf-8"))


# --- templates.py ----------------------------------------------------------------

def test_healthy_narrative_mentions_score_band_and_approval():
    payload = load("healthy_growth")
    text = build_narrative(payload)
    assert "809" in text
    assert "Excellent" in text
    assert "Approve with limit" in text
    assert "reconcile" in text


def test_fraud_narrative_surfaces_flags_and_withheld_limit():
    payload = load("inflated_gst_fraud")
    text = build_narrative(payload)
    assert "449" in text
    assert "High Risk" in text
    assert "flag" in text.lower()
    assert "No limit is recommended" in text
    assert "fraud review" in text.lower()


def test_narrative_never_touches_raw_transaction_fields():
    # Contract check: build_narrative must only read the aggregate keys the /score
    # payload exposes — assert it works from a payload with ONLY those keys (no
    # feature/transaction data present at all).
    payload = load("healthy_growth")
    minimal = {k: payload[k] for k in (
        "applicant_id", "setu_score", "band", "recommendation",
        "cross_validation", "limit_recommendation", "reason_codes",
    )}
    text = build_narrative(minimal)
    assert "809" in text


# --- gemini.py cascade (mocked — no real network calls) --------------------------

class FakeResponse:
    def __init__(self, text: str):
        self.text = text


class FakeModels:
    """Simulates client.models.generate_content with a scripted outcome sequence."""

    def __init__(self, outcomes: list):
        self._outcomes = list(outcomes)
        self.calls: list[str] = []

    def generate_content(self, *, model: str, contents, config):
        self.calls.append(model)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


class FakeClient:
    def __init__(self, outcomes: list):
        self.models = FakeModels(outcomes)

    @classmethod
    def factory(cls, outcomes: list):
        return lambda api_key: cls(outcomes)


@pytest.fixture(autouse=True)
def isolated_usage_db(tmp_path, monkeypatch):
    # Every test gets its own fresh, isolated call-counter DB.
    db_path = tmp_path / "gemini_usage.db"
    monkeypatch.setattr("backend.app.narrative.gemini.GeminiUsageStore",
                        lambda: GeminiUsageStore(db_path=db_path))
    return db_path


def _enable(monkeypatch, primary="key-primary", fallback="", **extra):
    """settings is a frozen dataclass, so swap the whole module-level instance."""
    from backend.app.narrative import gemini as g
    new_settings = dataclasses.replace(
        g.settings,
        enable_llm_narrative=True,
        gemini_api_key=primary,
        gemini_api_key_fallback=fallback,
        **extra,
    )
    monkeypatch.setattr(g, "settings", new_settings)
    return new_settings


def test_disabled_returns_template_without_calling_gemini(monkeypatch):
    from backend.app.narrative import gemini as g
    monkeypatch.setattr(g, "settings", dataclasses.replace(g.settings, enable_llm_narrative=False))
    text, source = g.polish_narrative(load("healthy_growth"), "BASE TEXT")
    assert (text, source) == ("BASE TEXT", "template")


def test_no_keys_returns_template(monkeypatch):
    from backend.app.narrative import gemini as g
    monkeypatch.setattr(g, "settings", dataclasses.replace(
        g.settings, enable_llm_narrative=True, gemini_api_key="", gemini_api_key_fallback="",
    ))
    text, source = g.polish_narrative(load("healthy_growth"), "BASE TEXT")
    assert (text, source) == ("BASE TEXT", "template")


def test_first_model_success_short_circuits_cascade(monkeypatch):
    from backend.app.narrative import gemini as g
    from google.genai import errors as genai_errors
    _enable(monkeypatch)
    fake = FakeClient(["Polished text"])
    monkeypatch.setattr(g.genai, "Client", lambda api_key: fake)
    text, source = g.polish_narrative(load("healthy_growth"), "BASE TEXT")
    assert (text, source) == ("Polished text", "gemini")
    assert fake.models.calls == [g.GEMINI_MODEL_CASCADE[0]]


def test_cascades_through_models_on_quota_exhaustion(monkeypatch):
    from backend.app.narrative import gemini as g
    from google.genai import errors as genai_errors

    class FakeQuotaError(genai_errors.ClientError):
        def __init__(self):
            pass  # skip the real constructor's response-parsing requirements

    _enable(monkeypatch)
    outcomes = [FakeQuotaError(), FakeQuotaError(), "Third model worked"]
    fake = FakeClient(outcomes)
    monkeypatch.setattr(g.genai, "Client", lambda api_key: fake)
    text, source = g.polish_narrative(load("healthy_growth"), "BASE TEXT")
    assert (text, source) == ("Third model worked", "gemini")
    assert fake.models.calls == g.GEMINI_MODEL_CASCADE[:3]


def test_falls_back_to_second_key_after_primary_key_exhausted(monkeypatch):
    from backend.app.narrative import gemini as g
    from google.genai import errors as genai_errors

    class FakeQuotaError(genai_errors.ClientError):
        def __init__(self):
            pass

    _enable(monkeypatch, primary="key-primary", fallback="key-fallback")
    n_models = len(g.GEMINI_MODEL_CASCADE)
    # Every model fails on the primary key; the first model succeeds on the fallback key.
    clients: dict[str, FakeClient] = {}

    def client_factory(api_key: str):
        outcomes = [FakeQuotaError()] * n_models if api_key == "key-primary" else ["Fallback key worked"]
        c = FakeClient(outcomes)
        clients[api_key] = c
        return c

    monkeypatch.setattr(g.genai, "Client", client_factory)
    text, source = g.polish_narrative(load("healthy_growth"), "BASE TEXT")
    assert (text, source) == ("Fallback key worked", "gemini")
    assert len(clients["key-primary"].models.calls) == n_models
    assert clients["key-fallback"].models.calls == [g.GEMINI_MODEL_CASCADE[0]]


def test_all_models_and_keys_exhausted_falls_back_to_template(monkeypatch):
    from backend.app.narrative import gemini as g
    from google.genai import errors as genai_errors

    class FakeQuotaError(genai_errors.ClientError):
        def __init__(self):
            pass

    _enable(monkeypatch, primary="key-primary", fallback="key-fallback")
    n_models = len(g.GEMINI_MODEL_CASCADE)
    monkeypatch.setattr(
        g.genai, "Client",
        lambda api_key: FakeClient([FakeQuotaError()] * n_models),
    )
    text, source = g.polish_narrative(load("healthy_growth"), "BASE TEXT")
    assert (text, source) == ("BASE TEXT", "template")


def test_lifetime_call_cap_stops_the_cascade(monkeypatch, tmp_path):
    from backend.app.narrative import gemini as g
    from google.genai import errors as genai_errors

    class FakeQuotaError(genai_errors.ClientError):
        def __init__(self):
            pass

    db_path = tmp_path / "capped.db"
    store = GeminiUsageStore(db_path=db_path)
    monkeypatch.setattr(g, "GeminiUsageStore", lambda: store)
    _enable(monkeypatch, gemini_max_calls=2)
    fake = FakeClient([FakeQuotaError(), FakeQuotaError(), "would succeed but cap hit"])
    monkeypatch.setattr(g.genai, "Client", lambda api_key: fake)

    text, source = g.polish_narrative(load("healthy_growth"), "BASE TEXT")
    assert (text, source) == ("BASE TEXT", "template")
    assert len(fake.models.calls) == 2  # stopped at the cap, never tried the 3rd
    assert store.total_calls() == 2


def test_usage_store_persists_across_instances(tmp_path):
    db_path = tmp_path / "usage.db"
    a = GeminiUsageStore(db_path=db_path)
    a.record("primary", "model-x", "success")
    b = GeminiUsageStore(db_path=db_path)  # simulates a fresh process restart
    assert b.total_calls() == 1
    assert b.remaining(50) == 49
