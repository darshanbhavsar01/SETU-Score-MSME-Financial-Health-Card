"""SQLite implementations of the applicant and score repositories.

- Applicants are read from the baked, read-only seed DB (config.SQLITE_PATH).
- Scores/flags are written to a separate, writable runtime DB (config.APP_DB_PATH)
  so the container never mutates the read-only image files (§13).

Connections are opened per operation — simple and safe at POC request volume, and it
sidesteps SQLite's thread-affinity rules under Uvicorn's worker threads.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.app.config import APP_DB_PATH, SQLITE_PATH
from backend.app.repository.base import (
    Applicant,
    ApplicantRepository,
    ScoreRepository,
    ScoreSummary,
)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


class SqliteApplicantRepository(ApplicantRepository):
    def __init__(self, db_path: Path = SQLITE_PATH) -> None:
        self._db_path = db_path

    def _row_to_applicant(self, row: sqlite3.Row) -> Applicant:
        return Applicant(
            id=row["id"],
            name=row["name"],
            sector=row["sector"],
            persona=row["persona"],
            history_months=int(row["history_months"]),
            onboarded_at=row["onboarded_at"],
            data_source=row["data_source"],
        )

    def list_applicants(self) -> list[Applicant]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM applicants ORDER BY id").fetchall()
        return [self._row_to_applicant(r) for r in rows]

    def get_applicant(self, applicant_id: str) -> Applicant | None:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM applicants WHERE id = ?", (applicant_id,)
            ).fetchone()
        return self._row_to_applicant(row) if row else None

    def exists(self, applicant_id: str) -> bool:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM applicants WHERE id = ?", (applicant_id,)
            ).fetchone()
        return row is not None


class SqliteScoreRepository(ScoreRepository):
    def __init__(self, db_path: Path = APP_DB_PATH) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scores (
                    applicant_id      TEXT PRIMARY KEY,
                    setu_score        INTEGER NOT NULL,
                    band              TEXT NOT NULL,
                    recommendation    TEXT NOT NULL,
                    consistency_score INTEGER,
                    limit_amount      INTEGER,
                    scored_at         TEXT NOT NULL,
                    data_source       TEXT NOT NULL,
                    payload           TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS flags (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_id TEXT NOT NULL,
                    code         TEXT NOT NULL,
                    direction    TEXT,
                    evidence     TEXT,
                    FOREIGN KEY (applicant_id) REFERENCES scores (applicant_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_flags_applicant ON flags (applicant_id)"
            )
            conn.commit()

    def save_score(
        self, applicant_id: str, payload: dict, flags: list[dict] | None = None
    ) -> None:
        cross = payload.get("cross_validation") or {}
        limit = payload.get("limit_recommendation") or {}
        scored_at = payload.get("scored_at") or datetime.now(timezone.utc).isoformat()
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO scores (applicant_id, setu_score, band, recommendation,
                                    consistency_score, limit_amount, scored_at,
                                    data_source, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(applicant_id) DO UPDATE SET
                    setu_score=excluded.setu_score,
                    band=excluded.band,
                    recommendation=excluded.recommendation,
                    consistency_score=excluded.consistency_score,
                    limit_amount=excluded.limit_amount,
                    scored_at=excluded.scored_at,
                    data_source=excluded.data_source,
                    payload=excluded.payload
                """,
                (
                    applicant_id,
                    int(payload.get("setu_score", 0)),
                    payload.get("band", ""),
                    payload.get("recommendation", ""),
                    cross.get("consistency_score"),
                    limit.get("amount_inr"),
                    scored_at,
                    payload.get("data_source", "synthetic"),
                    json.dumps(payload),
                ),
            )
            conn.execute("DELETE FROM flags WHERE applicant_id = ?", (applicant_id,))
            flag_rows = flags if flags is not None else (cross.get("flags") or [])
            conn.executemany(
                "INSERT INTO flags (applicant_id, code, direction, evidence) VALUES (?, ?, ?, ?)",
                [
                    (
                        applicant_id,
                        f.get("code", ""),
                        f.get("direction"),
                        f.get("evidence"),
                    )
                    for f in flag_rows
                ],
            )
            conn.commit()

    def get_score(self, applicant_id: str) -> dict | None:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT payload FROM scores WHERE applicant_id = ?", (applicant_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_scored(self) -> list[ScoreSummary]:
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT applicant_id, setu_score, band, recommendation, scored_at "
                "FROM scores ORDER BY applicant_id"
            ).fetchall()
        return [
            ScoreSummary(
                applicant_id=r["applicant_id"],
                setu_score=int(r["setu_score"]),
                band=r["band"],
                recommendation=r["recommendation"],
                scored_at=r["scored_at"],
            )
            for r in rows
        ]

    def get_flags(self, applicant_id: str) -> list[dict]:
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT code, direction, evidence FROM flags WHERE applicant_id = ?",
                (applicant_id,),
            ).fetchall()
        return [dict(r) for r in rows]
