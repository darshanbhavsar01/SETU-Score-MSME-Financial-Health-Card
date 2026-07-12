"""Repository layer public surface + wiring factory.

Import interfaces and the concrete bundle from here; callers depend on the
interfaces (base module) rather than the SQLite/DuckDB classes directly, so the
managed-cloud swap (§3) stays a one-file change.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.repository.base import (
    AnalyticsRepository,
    Applicant,
    ApplicantRepository,
    ScoreRepository,
    ScoreSummary,
)
from backend.app.repository.duckdb_repo import DuckdbAnalyticsRepository
from backend.app.repository.sqlite_repo import (
    SqliteApplicantRepository,
    SqliteScoreRepository,
)

__all__ = [
    "Applicant",
    "ScoreSummary",
    "ApplicantRepository",
    "ScoreRepository",
    "AnalyticsRepository",
    "Repositories",
    "get_repositories",
]


@dataclass(frozen=True)
class Repositories:
    """Bundle of the three repositories wired for the current backend."""

    applicants: ApplicantRepository
    scores: ScoreRepository
    analytics: AnalyticsRepository


def get_repositories() -> Repositories:
    """Construct the default (SQLite + DuckDB) repository bundle and ensure the
    runtime score tables exist. This is the single place that picks concrete
    implementations — swap here to move to managed cloud services."""
    scores = SqliteScoreRepository()
    scores.initialize()
    return Repositories(
        applicants=SqliteApplicantRepository(),
        scores=scores,
        analytics=DuckdbAnalyticsRepository(),
    )
