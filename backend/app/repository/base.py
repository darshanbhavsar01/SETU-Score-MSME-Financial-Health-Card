"""Repository interfaces — the deliberate data-access swap-point (CLAUDE.md §3).

Every read/write to SQLite or DuckDB goes through one of these interfaces; no raw
SQL lives in route handlers, scoring, or feature code. Today the implementations
are SQLite (app storage) and DuckDB-over-parquet (analytics). Swapping to
BigQuery/Firestore later means re-implementing these classes only — a bounded change,
not a rewrite. That migration path is the whole reason this layer exists at POC scale.

Domain models here are plain dataclasses so the storage layer stays independent of the
pydantic API contract (schemas.py, step 5).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Applicant:
    """One MSME in the officer queue. `persona` is ground-truth-for-demo only and is
    hidden in prod-mode responses (§7)."""

    id: str
    name: str
    sector: str
    persona: str
    history_months: int
    onboarded_at: str
    data_source: str


@dataclass(frozen=True)
class ScoreSummary:
    """Lightweight row for the console queue — 'score if computed' without
    deserializing the full payload."""

    applicant_id: str
    setu_score: int
    band: str
    recommendation: str
    scored_at: str


class ApplicantRepository(ABC):
    """Read access to the (baked, read-only) applicants seed."""

    @abstractmethod
    def list_applicants(self) -> list[Applicant]:
        ...

    @abstractmethod
    def get_applicant(self, applicant_id: str) -> Applicant | None:
        ...

    @abstractmethod
    def exists(self, applicant_id: str) -> bool:
        ...


class ScoreRepository(ABC):
    """Persistence for computed scores and their fraud/reason flags.

    Writes go to the *runtime* DB (config.APP_DB_PATH), separate from the read-only
    seed. Scoring is a pure per-request computation (§13); persistence is a
    convenience/cache, never a correctness dependency.
    """

    @abstractmethod
    def initialize(self) -> None:
        """Create the scores/flags tables if they do not exist. Idempotent."""

    @abstractmethod
    def save_score(
        self, applicant_id: str, payload: dict, flags: list[dict] | None = None
    ) -> None:
        """Persist the full API payload (as JSON) plus indexed summary columns and
        any triggered flags. Replaces any prior score for the applicant."""

    @abstractmethod
    def get_score(self, applicant_id: str) -> dict | None:
        """Return the stored API payload dict, or None if never scored."""

    @abstractmethod
    def list_scored(self) -> list[ScoreSummary]:
        ...

    @abstractmethod
    def get_flags(self, applicant_id: str) -> list[dict]:
        ...


class AnalyticsRepository(ABC):
    """Read-only analytical access over the parquet data lake (DuckDB today).

    Raw per-applicant getters return tidy DataFrames; the aggregate helpers push the
    GROUP BY down into the engine. All SQL lives behind this interface so the feature
    builders (step 3) stay pure-python and the engine is swappable.
    """

    # --- raw per-applicant pulls (already monthly for GST/EPFO) ---
    @abstractmethod
    def gst_returns(self, applicant_id: str) -> pd.DataFrame:
        ...

    @abstractmethod
    def upi_settlements(self, applicant_id: str) -> pd.DataFrame:
        ...

    @abstractmethod
    def bank_txns(self, applicant_id: str) -> pd.DataFrame:
        ...

    @abstractmethod
    def epfo_payroll(self, applicant_id: str) -> pd.DataFrame:
        ...

    # --- pushed-down aggregations used by the sub-scores ---
    @abstractmethod
    def upi_payer_totals(self, applicant_id: str) -> pd.DataFrame:
        """payer_id, total, share — for the customer-concentration (HHI) sub-score."""

    @abstractmethod
    def upi_monthly(self, applicant_id: str) -> pd.DataFrame:
        """month, upi_total — for cross-validation and growth blending."""

    @abstractmethod
    def bank_monthly(self, applicant_id: str) -> pd.DataFrame:
        """month, credit, debit, emi, salary, rent, supplier, closing_balance —
        the backbone of the liquidity/stability/leverage sub-scores."""
