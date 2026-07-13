"""Central configuration for SETU Score.

This is the *single* place that defines the random seed, filesystem paths, and
process-wide flags/counters. Guardrail #4 (CLAUDE.md §2): all data generation and
scoring must be seeded from ONE constant so demo runs are reproducible.

Import this from anywhere (datagen, backend, model) rather than re-deriving paths
or reseeding locally.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# --- The one seed to rule them all (guardrail #4) ------------------------------
RANDOM_SEED: int = 42

# --- Filesystem layout ---------------------------------------------------------
# This file lives at <repo>/backend/app/config.py → parents[2] is the repo root.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

DATA_DIR: Path = REPO_ROOT / "data"
PARQUET_DIR: Path = DATA_DIR / "parquet"

# Read-only seed DB (applicants queue), baked into the image at build time (§13).
SQLITE_PATH: Path = DATA_DIR / "setu.db"

# Writable runtime DB for scores/flags and the Gemini call-counter (§8). Kept
# SEPARATE from the read-only seed so the container never writes to the baked
# image files. On Cloud Run (read-only FS) point SETU_APP_DB at /tmp, e.g.
#   SETU_APP_DB=/tmp/setu-app.db
APP_DB_PATH: Path = Path(os.getenv("SETU_APP_DB", str(DATA_DIR / "app.db")))

# Individual parquet datasets (DuckDB reads these directly; see §3).
GST_PARQUET: Path = PARQUET_DIR / "gst_returns.parquet"
UPI_PARQUET: Path = PARQUET_DIR / "upi_settlements.parquet"
BANK_PARQUET: Path = PARQUET_DIR / "bank_txns.parquet"
EPFO_PARQUET: Path = PARQUET_DIR / "epfo_payroll.parquet"

MODEL_DIR: Path = REPO_ROOT / "model"
MODEL_PATH: Path = MODEL_DIR / "model.pkl"
METRICS_PATH: Path = MODEL_DIR / "metrics.json"

# --- Data-generation constants (shared by datagen + validators) ----------------
# The most recent fully-complete month the synthetic history ends on. Fixed so
# runs are deterministic regardless of wall-clock date.
DATA_END_YEAR: int = 2026
DATA_END_MONTH: int = 6  # history ends 2026-06 (inclusive)
DEFAULT_HISTORY_MONTHS: int = 24

# Every synthetic record is stamped with this so it can never be mistaken for real
# data (guardrail #2). Surfaced in the API response and UI footer.
DATA_SOURCE_LABEL: str = "synthetic"

# --- Scoring methodology constants (CLAUDE.md §6) ------------------------------
# Sub-score weights. Each has a one-line rationale (guardrail: explainable core).
# Must sum to 1.0 — asserted at import time below.
SUBSCORE_WEIGHTS: dict[str, float] = {
    "growth": 0.15,        # forward-looking repayment capacity from turnover trend
    "stability": 0.20,     # predictable cash flow is the strongest repayment signal
    "compliance": 0.15,    # filing discipline proxies governance & willingness to pay
    "liquidity": 0.20,     # cash buffer to absorb shocks / service obligations
    "concentration": 0.15, # customer diversification = revenue durability
    "leverage": 0.15,      # existing debt burden (FOIR-like) constrains new credit
}
assert abs(sum(SUBSCORE_WEIGHTS.values()) - 1.0) < 1e-9, "SUBSCORE_WEIGHTS must sum to 1.0"

# Composite is a 0–100 weighted average rescaled onto a 300–900 credit-score range.
SCORE_SCALE_MIN: int = 300
SCORE_SCALE_MAX: int = 900

# Band thresholds on the 300–900 scale (§6).
BANDS: list[tuple[str, int]] = [
    ("HIGH_RISK", 450),   # score < 450
    ("WATCH", 600),       # 450 ≤ score < 600
    ("GOOD", 750),        # 600 ≤ score < 750
    ("EXCELLENT", 10_000),  # score ≥ 750
]

# A hard fraud flag caps the composite here and forces REFER_FRAUD_REVIEW (§6).
FRAUD_CAP_SCORE: int = 449

# Policy overlay: single-customer dependence is a material risk regardless of other
# strengths, so an extreme UPI payer concentration caps the composite in the WATCH
# band (§5: "concentration flag drives it down").
CONCENTRATION_CAP_TOP_SHARE: float = 0.65
CONCENTRATION_CAP_SCORE: int = 599

# --- Cross-validation tolerances (§6) -----------------------------------------
GST_BANK_TOLERANCE: float = 0.25     # declared vs bank credits, ±25% band per quarter
GST_UPI_MAX_RATIO: float = 3.5       # declared / UPI volume above this is suspicious
ROUND_NUMBER_UNIT: int = 100_000     # ₹1 lakh — round-figure filing detector unit
ROUND_NUMBER_FRACTION: float = 0.5   # flag if ≥50% of filings are exact ₹1L multiples

# --- Working-capital limit (§6) -----------------------------------------------
LIMIT_MULTIPLE: float = 6.0          # k: months of verified net inflow extended
LIMIT_MIN_INR: int = 50_000
LIMIT_MAX_INR: int = 5_000_000       # persona-agnostic hard cap
LIMIT_TENOR_MONTHS: int = 12
LIMIT_ROUNDING_INR: int = 10_000     # round recommendation to a clean figure


@dataclass(frozen=True)
class Settings:
    """Runtime flags, mostly read from the environment. Safe defaults = the POC
    path that needs no cloud credentials and no API keys."""

    # Optional Gemini narrative polish (§8). Off by default.
    enable_llm_narrative: bool = os.getenv("ENABLE_LLM_NARRATIVE", "false").lower() == "true"
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    # Second AI Studio account/key, tried only once the primary is exhausted across
    # every model in GEMINI_MODEL_CASCADE.
    gemini_api_key_fallback: str = os.getenv("GEMINI_API_KEY_FALLBACK", "")
    # Hard, SQLite-persisted cap on raw Gemini API calls across the app's lifetime —
    # survives process restarts so it is a durable budget guardrail, not a
    # per-process allowance that resets on redeploy (§2 budget cap, §8).
    gemini_max_calls: int = 50
    gemini_max_output_tokens: int = 1000

    # Expose the ground-truth persona in API responses. True for the demo/console;
    # set SETU_PROD_MODE=true to hide it (prod-mode flag, §7).
    expose_persona: bool = os.getenv("SETU_PROD_MODE", "false").lower() != "true"


settings = Settings()

# Ordered cascade of Gemini model IDs to try, newest/most-capable first. Each entry
# that doesn't exist on the caller's account (or is retired) simply errors and the
# cascade moves on — no need to keep this list perfectly in sync with what Google
# currently ships. Override entirely via GEMINI_MODELS="model-a,model-b" if needed.
_default_cascade = [
    "gemini-flash-latest",       # AI Studio alias -> current best flash model
    "gemini-3-flash",
    "gemini-3-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-flash-lite-latest",  # AI Studio alias -> current best flash-lite model
]
GEMINI_MODEL_CASCADE: list[str] = [
    m.strip() for m in os.getenv("GEMINI_MODELS", "").split(",") if m.strip()
] or _default_cascade


def ensure_data_dirs() -> None:
    """Create the data directories if missing. Called by the generator."""
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
