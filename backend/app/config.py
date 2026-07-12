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


@dataclass(frozen=True)
class Settings:
    """Runtime flags, mostly read from the environment. Safe defaults = the POC
    path that needs no cloud credentials and no API keys."""

    # Optional Gemini narrative polish (§8). Off by default.
    enable_llm_narrative: bool = os.getenv("ENABLE_LLM_NARRATIVE", "false").lower() == "true"
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    # Hard cap on Gemini calls per process lifetime (§8).
    gemini_max_calls: int = 50
    gemini_max_output_tokens: int = 1000


settings = Settings()


def ensure_data_dirs() -> None:
    """Create the data directories if missing. Called by the generator."""
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
