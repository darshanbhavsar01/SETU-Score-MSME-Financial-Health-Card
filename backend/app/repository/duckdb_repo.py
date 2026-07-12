"""DuckDB-over-parquet implementation of the analytics repository.

Registers the four parquet datasets as views on a single in-process connection and
serves per-applicant reads and pushed-down aggregations. All analytical SQL lives
here (§3) so the feature builders stay pure-python and the engine is swappable.

Concurrency: one connection is created per repository instance; each query runs on a
fresh `cursor()` (a lightweight thread-local view of the same catalog), which is safe
under Uvicorn's sync-endpoint threadpool.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from backend.app.config import BANK_PARQUET, EPFO_PARQUET, GST_PARQUET, UPI_PARQUET
from backend.app.repository.base import AnalyticsRepository


class DuckdbAnalyticsRepository(AnalyticsRepository):
    def __init__(self) -> None:
        self._con = duckdb.connect(database=":memory:")
        # as_posix() keeps paths valid inside SQL string literals on Windows.
        self._con.execute(
            f"""
            CREATE VIEW gst  AS SELECT * FROM read_parquet('{GST_PARQUET.as_posix()}');
            CREATE VIEW upi  AS SELECT * FROM read_parquet('{UPI_PARQUET.as_posix()}');
            CREATE VIEW bank AS SELECT * FROM read_parquet('{BANK_PARQUET.as_posix()}');
            CREATE VIEW epfo AS SELECT * FROM read_parquet('{EPFO_PARQUET.as_posix()}');
            """
        )

    def _query(self, sql: str, params: list) -> pd.DataFrame:
        return self._con.cursor().execute(sql, params).df()

    # --- raw per-applicant pulls ---
    def gst_returns(self, applicant_id: str) -> pd.DataFrame:
        return self._query(
            "SELECT * FROM gst WHERE applicant_id = ? ORDER BY month", [applicant_id]
        )

    def upi_settlements(self, applicant_id: str) -> pd.DataFrame:
        return self._query(
            "SELECT * FROM upi WHERE applicant_id = ? ORDER BY txn_date", [applicant_id]
        )

    def bank_txns(self, applicant_id: str) -> pd.DataFrame:
        return self._query(
            "SELECT * FROM bank WHERE applicant_id = ? ORDER BY txn_date", [applicant_id]
        )

    def epfo_payroll(self, applicant_id: str) -> pd.DataFrame:
        return self._query(
            "SELECT * FROM epfo WHERE applicant_id = ? ORDER BY month", [applicant_id]
        )

    # --- pushed-down aggregations ---
    def upi_payer_totals(self, applicant_id: str) -> pd.DataFrame:
        return self._query(
            """
            SELECT payer_id,
                   SUM(amount)                              AS total,
                   SUM(amount) / SUM(SUM(amount)) OVER ()   AS share
            FROM upi
            WHERE applicant_id = ?
            GROUP BY payer_id
            ORDER BY total DESC
            """,
            [applicant_id],
        )

    def upi_monthly(self, applicant_id: str) -> pd.DataFrame:
        return self._query(
            """
            SELECT date_trunc('month', txn_date) AS month,
                   SUM(amount)                    AS upi_total
            FROM upi
            WHERE applicant_id = ?
            GROUP BY 1
            ORDER BY 1
            """,
            [applicant_id],
        )

    def bank_monthly(self, applicant_id: str) -> pd.DataFrame:
        return self._query(
            """
            SELECT date_trunc('month', txn_date) AS month,
                   COALESCE(SUM(amount) FILTER (WHERE direction = 'credit'), 0) AS credit,
                   COALESCE(SUM(amount) FILTER (WHERE direction = 'debit'),  0) AS debit,
                   COALESCE(SUM(amount) FILTER (WHERE txn_type = 'EMI'),      0) AS emi,
                   COALESCE(SUM(amount) FILTER (WHERE txn_type = 'SALARY'),   0) AS salary,
                   COALESCE(SUM(amount) FILTER (WHERE txn_type = 'RENT'),     0) AS rent,
                   COALESCE(SUM(amount) FILTER (WHERE txn_type = 'SUPPLIER'), 0) AS supplier,
                   arg_max(balance, txn_date)                                   AS closing_balance
            FROM bank
            WHERE applicant_id = ?
            GROUP BY 1
            ORDER BY 1
            """,
            [applicant_id],
        )
