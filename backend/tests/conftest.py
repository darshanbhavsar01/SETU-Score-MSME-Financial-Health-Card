"""Shared pytest fixtures.

The synthetic dataset is a prerequisite for the analytics repository tests. Rather
than require a manual `make data`, we generate it once per session if the parquet
files are missing (deterministic, ~1s).
"""

from __future__ import annotations

import pytest

from backend.app.config import BANK_PARQUET, GST_PARQUET, SQLITE_PATH


@pytest.fixture(scope="session", autouse=True)
def ensure_dataset() -> None:
    if not (GST_PARQUET.exists() and BANK_PARQUET.exists() and SQLITE_PATH.exists()):
        from datagen.generate import main as generate

        generate()
