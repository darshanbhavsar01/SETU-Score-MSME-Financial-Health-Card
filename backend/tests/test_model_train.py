"""Smoke test for the optional ML sanity-check layer (build-order step 7).

Trains into a temp path (never touches the real model/model.pkl or metrics.json)
and asserts the dataset construction and metrics shape are sane. This is a feature
sanity-check per CLAUDE.md §6 — we assert structure and bounds, not a specific
accuracy number (that would be exactly the "circular validation" the guardrails
forbid claiming as real-world accuracy).
"""

from __future__ import annotations

import json

from backend.app.repository import get_repositories
from model.train import _label_for, build_dataset, train


def test_build_dataset_excludes_thin_file_and_labels_by_persona():
    X, y, ids, excluded = build_dataset()

    assert X.shape == (50, 6)  # 60 - 10 ntc_thin_file, 6 sub-score features
    assert y.shape == (50,)
    assert len(excluded) == 10
    assert sum(y) > 0 and sum(y) < len(y)  # both classes present

    persona_by_id = {a.id: a.persona for a in get_repositories().applicants.list_applicants()}
    for aid, label in zip(ids, y):
        assert label == _label_for(persona_by_id[aid])
    for aid in excluded:
        assert persona_by_id[aid] == "ntc_thin_file"


def test_train_writes_well_formed_metrics(tmp_path, monkeypatch):
    model_path = tmp_path / "model.pkl"
    metrics_path = tmp_path / "metrics.json"
    monkeypatch.setattr("model.train.MODEL_PATH", model_path)
    monkeypatch.setattr("model.train.METRICS_PATH", metrics_path)

    metrics = train()

    assert model_path.exists()
    assert metrics_path.exists()
    on_disk = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert on_disk == metrics

    assert metrics["n_samples"] == 50
    assert metrics["n_train"] + metrics["n_test"] == 50
    assert 0.0 <= metrics["train_accuracy"] <= 1.0
    assert 0.0 <= metrics["test_accuracy"] <= 1.0
    assert set(metrics["features"]) == {
        "growth", "stability", "compliance", "liquidity", "concentration", "leverage",
    }
    assert len(metrics["excluded_applicants"]) == 10
    assert "cross_checks.py" in metrics["honest_note"]
    assert metrics["data_source"] == "synthetic"
