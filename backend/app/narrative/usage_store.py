"""Durable call counter for the Gemini narrative cascade (CLAUDE.md §8).

Persisted in the same writable runtime SQLite DB the score repository uses
(config.APP_DB_PATH — /tmp on Cloud Run), so the 50-call lifetime cap survives
process restarts rather than resetting on every redeploy/cold start. This is a
deliberately small, direct-sqlite3 helper rather than a repository/ interface: it is
infra plumbing for a rate limiter, not a domain read/write path.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.app.config import APP_DB_PATH


class GeminiUsageStore:
    def __init__(self, db_path: Path = APP_DB_PATH) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gemini_calls (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_label  TEXT NOT NULL,
                    model      TEXT NOT NULL,
                    outcome    TEXT NOT NULL,
                    called_at  TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def total_calls(self) -> int:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM gemini_calls").fetchone()
        return int(row[0])

    def remaining(self, cap: int) -> int:
        return max(0, cap - self.total_calls())

    def record(self, key_label: str, model: str, outcome: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO gemini_calls (key_label, model, outcome, called_at) VALUES (?, ?, ?, ?)",
                (key_label, model, outcome, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
