"""Feature engineering (CLAUDE.md §3, §6).

Pulls per-applicant aggregates from the AnalyticsRepository (all heavy SQL lives in
the DuckDB layer) and assembles the monthly, aligned NumPy series the six sub-scores
consume. Pure-python from here on — no SQL, no I/O beyond the repository interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backend.app.repository.base import AnalyticsRepository


@dataclass(frozen=True)
class FeatureBundle:
    """All aligned, monthly features for one MSME. Every array is length n_months
    and ordered oldest→newest."""

    applicant_id: str
    n_months: int

    # Turnover / inflow signals
    blended_turnover: np.ndarray   # mean(GST declared, bank credits) — growth signal
    bank_credit: np.ndarray        # observed bank inflow
    gst_declared: np.ndarray       # declared GST turnover
    upi_total: np.ndarray          # monthly UPI settlement volume
    net_inflow: np.ndarray         # bank credit − bank debit (retained cash)

    # Liquidity / obligations
    closing_balance: np.ndarray
    monthly_obligations: np.ndarray  # fixed commitments: EMI + rent + payroll
    emi: np.ndarray

    # Compliance
    gst_late_flags: np.ndarray       # bool per month
    gst_filing_gap_days: np.ndarray  # filing_date − due_date (days; ≤0 = on/before time)
    epfo_late_flags: np.ndarray      # bool per month

    # Concentration
    payer_shares: np.ndarray         # UPI volume share per distinct payer (sums to 1)

    # Convenience scalars
    avg_monthly_inflow: float
    avg_emi: float

    # Month labels ("YYYY-MM"), aligned with the arrays — used by the trend view.
    months: list[str] = field(default_factory=list)


def _to_bool(series: pd.Series) -> np.ndarray:
    # Parquet/DuckDB may hand back bools, 0/1 ints, or numpy bools — normalise.
    return series.astype(bool).to_numpy()


def build_features(applicant_id: str, analytics: AnalyticsRepository) -> FeatureBundle:
    bank = analytics.bank_monthly(applicant_id)          # month, credit, debit, emi, salary, rent, ...
    gst = analytics.gst_returns(applicant_id)            # month, declared_turnover, filed_late, dates
    epfo = analytics.epfo_payroll(applicant_id)          # month, filed_late, ...
    upi_m = analytics.upi_monthly(applicant_id)          # month, upi_total
    payers = analytics.upi_payer_totals(applicant_id)    # payer_id, total, share

    # Normalise the GST month column (stored as first-of-month) to a period key so the
    # three monthly sources align on an inner join regardless of dtype quirks.
    def month_key(df: pd.DataFrame, col: str) -> pd.Series:
        return pd.to_datetime(df[col]).dt.to_period("M")

    bank = bank.assign(mk=month_key(bank, "month"))
    gst = gst.assign(mk=month_key(gst, "month"))
    epfo = epfo.assign(mk=month_key(epfo, "month"))
    upi_m = upi_m.assign(mk=month_key(upi_m, "month"))

    gst_gap = (pd.to_datetime(gst["filing_date"]) - pd.to_datetime(gst["due_date"])).dt.days

    merged = (
        bank[["mk", "credit", "debit", "emi", "salary", "rent", "closing_balance"]]
        .merge(
            gst.assign(gap=gst_gap)[["mk", "declared_turnover", "filed_late", "gap"]],
            on="mk", how="inner", suffixes=("", "_gst"),
        )
        .merge(upi_m[["mk", "upi_total"]], on="mk", how="left")
        .merge(
            epfo[["mk", "filed_late"]].rename(columns={"filed_late": "epfo_late"}),
            on="mk", how="left",
        )
        .sort_values("mk")
        .reset_index(drop=True)
    )
    merged["upi_total"] = merged["upi_total"].fillna(0.0)

    bank_credit = merged["credit"].to_numpy(dtype=float)
    gst_declared = merged["declared_turnover"].to_numpy(dtype=float)
    net_inflow = (merged["credit"] - merged["debit"]).to_numpy(dtype=float)
    obligations = (merged["emi"] + merged["rent"] + merged["salary"]).to_numpy(dtype=float)

    return FeatureBundle(
        applicant_id=applicant_id,
        n_months=len(merged),
        blended_turnover=(gst_declared + bank_credit) / 2.0,
        bank_credit=bank_credit,
        gst_declared=gst_declared,
        upi_total=merged["upi_total"].to_numpy(dtype=float),
        net_inflow=net_inflow,
        closing_balance=merged["closing_balance"].to_numpy(dtype=float),
        monthly_obligations=obligations,
        emi=merged["emi"].to_numpy(dtype=float),
        gst_late_flags=_to_bool(merged["filed_late"]),
        gst_filing_gap_days=merged["gap"].to_numpy(dtype=float),
        epfo_late_flags=_to_bool(merged["epfo_late"].fillna(False)),
        payer_shares=payers["share"].to_numpy(dtype=float),
        avg_monthly_inflow=float(np.mean(bank_credit)),
        avg_emi=float(np.mean(merged["emi"].to_numpy(dtype=float))),
        months=[str(p) for p in merged["mk"]],
    )
