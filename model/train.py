"""Optional ML sanity-check layer (CLAUDE.md §6, build-order step 7).

Trains a small XGBoost classifier to predict the *persona-implied* risk bucket
(WATCH/HIGH_RISK vs GOOD/EXCELLENT) from the same six sub-scores the rules engine
already computes — but recomputed on a temporal *first-18-months* window only, so
nothing from the held-out later months leaks into the features.

This is explicitly NOT a credit-decisioning model (guardrail #3, CLAUDE.md §6):
"used only to sanity-check that features carry signal, shown in the demo as 'model
agreement' not as accuracy." Trained and evaluated entirely on the 60 synthetic
seeded personas. metrics.json is the only artifact the UI/README may read numbers
from — never hand-edit it.

Run from the repo root:  python -m model.train
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from backend.app.config import METRICS_PATH, MODEL_PATH, RANDOM_SEED, ensure_data_dirs
from backend.app.features import build_features, truncate
from backend.app.repository import get_repositories
from backend.app.scoring.subscores import SUBSCORE_FUNCS, all_subscores
from datagen.personas import PERSONAS_BY_KEY

FEATURE_WINDOW_MONTHS = 18   # "first 18 months" per §6
MIN_HISTORY_FOR_SPLIT = 24   # need >= 18 feature months + 6 held-out months
RISK_BANDS = {"WATCH", "HIGH_RISK"}
FEATURE_NAMES = list(SUBSCORE_FUNCS)  # growth, stability, compliance, liquidity, concentration, leverage


def _label_for(persona: str) -> int:
    """1 = persona-implied risk (WATCH/HIGH_RISK expected band), 0 = GOOD/EXCELLENT."""
    return 1 if PERSONAS_BY_KEY[persona].expected_band in RISK_BANDS else 0


def build_dataset() -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    """Returns (X, y, applicant_ids, excluded_ids).

    Only applicants with >= MIN_HISTORY_FOR_SPLIT months qualify — this excludes the
    ntc_thin_file persona (8 months), which has too little history for an 18/6 split.
    That exclusion is itself the honest point: the ML sanity-check needs a longer
    track record than the rules engine does; NTC firms remain fully scoreable by the
    rules engine (§5), just not part of this auxiliary model's training set.
    """
    repos = get_repositories()
    X: list[list[float]] = []
    y: list[int] = []
    ids: list[str] = []
    excluded: list[str] = []

    for a in repos.applicants.list_applicants():
        if a.history_months < MIN_HISTORY_FOR_SPLIT:
            excluded.append(a.id)
            continue
        full = build_features(a.id, repos.analytics)
        window = truncate(full, FEATURE_WINDOW_MONTHS)
        subs = all_subscores(window)
        X.append([subs[name].value for name in FEATURE_NAMES])
        y.append(_label_for(a.persona))
        ids.append(a.id)

    return np.array(X, dtype=float), np.array(y, dtype=int), ids, excluded


def train() -> dict:
    ensure_data_dirs()
    X, y, ids, excluded = build_dataset()

    X_train, X_test, y_train, y_test, ids_train, ids_test = train_test_split(
        X, y, ids, test_size=0.3, random_state=RANDOM_SEED, stratify=y,
    )

    model = XGBClassifier(
        n_estimators=60,
        max_depth=3,
        learning_rate=0.15,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=RANDOM_SEED,
    )
    model.fit(X_train, y_train)

    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)
    test_proba = model.predict_proba(X_test)[:, 1]

    train_acc = float(accuracy_score(y_train, train_pred))
    test_acc = float(accuracy_score(y_test, test_pred))
    test_auc = float(roc_auc_score(y_test, test_proba)) if len(set(y_test)) > 1 else None

    importances = dict(zip(FEATURE_NAMES, [float(v) for v in model.feature_importances_]))

    # The honest callout: does the model catch fraud from sub-scores ALONE (it
    # shouldn't reliably — that's why cross_checks.py exists as a separate engine).
    repos = get_repositories()
    persona_by_id = {a.id: a.persona for a in repos.applicants.list_applicants()}
    fraud_test_idx = [i for i, aid in enumerate(ids_test) if persona_by_id[aid] == "inflated_gst_fraud"]
    fraud_recall = None
    if fraud_test_idx:
        fraud_recall = float(np.mean([test_pred[i] == 1 for i in fraud_test_idx]))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    metrics = {
        "random_seed": RANDOM_SEED,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "synthetic",
        "features": FEATURE_NAMES,
        "feature_window_months": FEATURE_WINDOW_MONTHS,
        "label_definition": (
            "1 = persona-implied risk band is WATCH or HIGH_RISK "
            "(declining_stress, concentration_risk, inflated_gst_fraud); "
            "0 = EXCELLENT or GOOD (healthy_growth, seasonal_stable)."
        ),
        "temporal_split": (
            f"features computed from months 0-{FEATURE_WINDOW_MONTHS - 1} only "
            "(sub-scores recomputed on a truncated FeatureBundle); the label is "
            "persona-implied, not derived from the held-out months — no direct "
            "leakage from the tail of each applicant's history."
        ),
        "n_samples": len(y),
        "n_train": len(y_train),
        "n_test": len(y_test),
        "excluded_applicants": excluded,
        "excluded_reason": "ntc_thin_file persona has only 8 months of history — too short for the 18/6 split.",
        "train_accuracy": round(train_acc, 3),
        "test_accuracy": round(test_acc, 3),
        "test_auc": round(test_auc, 3) if test_auc is not None else None,
        "feature_importance": {k: round(v, 3) for k, v in importances.items()},
        "fraud_persona_recall_in_test": round(fraud_recall, 3) if fraud_recall is not None else None,
        "honest_note": (
            f"Trained and evaluated ENTIRELY on the 60 synthetic seeded personas "
            f"(RANDOM_SEED={RANDOM_SEED}). Demonstrates that the six engineered "
            f"sub-scores carry separable signal for persona-implied risk buckets on "
            f"this seeded population (test_accuracy={round(test_acc, 3)}"
            + (f", test_auc={round(test_auc, 3)}" if test_auc is not None else "")
            + f"). This is a feature sanity-check on 50 samples, NOT a claim of "
            "real-world credit accuracy — the UI/README must present it as 'model "
            "agreement', never as an accuracy percentage. IMPORTANT: this classifier "
            "is not the fraud-detection mechanism. Even where "
            f"fraud_persona_recall_in_test={round(fraud_recall, 3) if fraud_recall is not None else 'N/A'} "
            "is high on this run's split, that coverage is incidental (sub-scores can "
            "pick up secondary symptoms of the fraud persona's stress) and unverified "
            "at scale — it is NOT guaranteed the way validation/cross_checks.py is, "
            "which deterministically flags 100% of the fraud persona via the "
            "GST-declared-vs-observed-inflows check (see test_cross_checks.py). Fraud "
            "review decisions must always route through cross_checks.py, never through "
            "this model."
        ),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    metrics = train()
    print(f"[model.train] seed={metrics['random_seed']}  n={metrics['n_samples']} "
          f"(train={metrics['n_train']}, test={metrics['n_test']})")
    print(f"[model.train] test_accuracy={metrics['test_accuracy']}  test_auc={metrics['test_auc']}")
    print(f"[model.train] fraud_persona_recall_in_test={metrics['fraud_persona_recall_in_test']} "
          "(incidental only — cross_checks.py is the authoritative fraud mechanism)")
    print(f"[model.train] wrote {MODEL_PATH} and {METRICS_PATH}")


if __name__ == "__main__":
    main()
