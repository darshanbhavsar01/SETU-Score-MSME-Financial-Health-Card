"""Synthetic MSME data generator (CLAUDE.md §5).

Produces, deterministically from RANDOM_SEED:
  - data/parquet/gst_returns.parquet     monthly GSTR-3B-like filings
  - data/parquet/upi_settlements.parquet daily UPI credits by payer
  - data/parquet/bank_txns.parquet       dated bank credits/debits + running balance
  - data/parquet/epfo_payroll.parquet    monthly payroll & PF contribution
  - data/setu.db (SQLite)                applicants seed table for the officer queue

Run from the repo root:  python -m datagen.generate

Design notes tying back to the guardrails:
  * Pure NumPy, fully seeded — same bytes every run (guardrail #4).
  * Every row is stamped data_source="synthetic" (guardrail #2).
  * The GST↔bank↔UPI relationship is constructed so that NON-fraud personas keep
    declared turnover close to observed inflows and UPI ≤ bank credits, while the
    fraud persona violates *only* the GST-vs-inflows invariant (§5 generator rules).
"""

from __future__ import annotations

import calendar
import sqlite3
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.app.config import (
    BANK_PARQUET,
    DATA_END_MONTH,
    DATA_END_YEAR,
    DATA_SOURCE_LABEL,
    EPFO_PARQUET,
    GST_PARQUET,
    RANDOM_SEED,
    SQLITE_PATH,
    UPI_PARQUET,
    ensure_data_dirs,
)
from datagen.personas import PERSONAS, SECTORS, PersonaConfig

# Naming pieces for realistic-looking business names in the console queue.
_NAME_PREFIXES = [
    "Shakti", "Ganesh", "Sunrise", "Meghna", "Anand", "Vardhman", "Deccan",
    "Konark", "Sahyadri", "Trishul", "Navkar", "Krishna", "Ashirwad", "Zenith",
    "Sagar", "Prakash", "Vishnu", "Ratna", "Suraj", "Om",
]
_NAME_SUFFIXES = [
    "Enterprises", "Industries", "Traders", "Agro", "Exports", "Textiles",
    "Fabricators", "Foods", "Packaging", "Udyog",
]


@dataclass
class GeneratedFrames:
    applicants: pd.DataFrame
    gst: pd.DataFrame
    upi: pd.DataFrame
    bank: pd.DataFrame
    epfo: pd.DataFrame


def _month_starts(n_months: int) -> list[pd.Timestamp]:
    """The n most recent month-start dates, ending at DATA_END (inclusive)."""
    end = pd.Timestamp(year=DATA_END_YEAR, month=DATA_END_MONTH, day=1)
    months = pd.date_range(end=end, periods=n_months, freq="MS")
    return list(months)


def _festive_factor(month: int) -> float:
    """Oct–Dec festive lift, tapering. Peaks in November."""
    return {10: 0.6, 11: 1.0, 12: 0.7}.get(month, 0.0)


def _payer_weights(rng: np.random.Generator, persona: PersonaConfig) -> np.ndarray:
    """Fixed customer mix for one MSME: payer 0 holds top_payer_share, the rest
    split the remainder with mild Dirichlet variation."""
    n = persona.num_payers
    if n <= 1:
        return np.array([1.0])
    rest = rng.dirichlet(np.ones(n - 1) * 2.0) * (1.0 - persona.top_payer_share)
    return np.concatenate([[persona.top_payer_share], rest])


def _business_name(rng: np.random.Generator) -> str:
    return f"{rng.choice(_NAME_PREFIXES)} {rng.choice(_NAME_SUFFIXES)}"


def _generate_one(
    applicant_id: str,
    persona: PersonaConfig,
    rng: np.random.Generator,
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict]]:
    """Generate all rows for a single MSME. Returns (applicant, gst, upi, bank, epfo)."""
    months = _month_starts(persona.history_months)
    n = len(months)

    # --- Actual monthly turnover (the underlying business truth) ---
    turnover = np.empty(n)
    turnover[0] = persona.base_monthly_turnover
    for m in range(1, n):
        g = persona.monthly_growth_mean + rng.normal(0.0, persona.monthly_growth_std)
        turnover[m] = turnover[m - 1] * (1.0 + g)
    # Seasonal lift + multiplicative noise, applied after the trend.
    for m, ts in enumerate(months):
        turnover[m] *= 1.0 + persona.seasonal_amplitude * _festive_factor(ts.month)
        turnover[m] *= 1.0 + rng.normal(0.0, persona.turnover_noise)
    # Optional revenue floor (a declining firm stabilising rather than collapsing).
    if persona.turnover_floor_fraction > 0:
        turnover = np.maximum(turnover, persona.turnover_floor_fraction * persona.base_monthly_turnover)
    turnover = np.clip(turnover, 10_000.0, None)

    payer_w = _payer_weights(rng, persona)

    # Opening bank balance = buffer × month-1 fixed obligations.
    rent = round(persona.rent_ratio * persona.base_monthly_turnover, 2)
    salary0 = persona.base_employees * persona.salary_per_employee
    emi0 = persona.emi_to_inflow * persona.base_monthly_turnover
    balance = persona.liquidity_buffer_months * (salary0 + rent + emi0)

    gst_rows: list[dict] = []
    upi_rows: list[dict] = []
    bank_rows: list[dict] = []
    epfo_rows: list[dict] = []

    for m, ts in enumerate(months):
        inflow = float(turnover[m])
        days_in_month = calendar.monthrange(ts.year, ts.month)[1]
        period = ts.strftime("%b-%Y")

        # ---------------- GST (GSTR-3B-like) ----------------
        declare_ratio = rng.normal(persona.gst_declare_ratio_mean, persona.gst_declare_ratio_std)
        declared = inflow * max(0.3, declare_ratio) * persona.gst_inflation_factor
        if persona.gst_round_numbers:
            declared = round(declared / 100_000.0) * 100_000.0  # round to ₹1 lakh
        declared = max(declared, 10_000.0)
        tax_paid = round(declared * persona.gst_effective_tax_rate, 2)

        due = (ts + pd.offsets.MonthEnd(1)) + pd.Timedelta(days=20)  # ~20th of next month
        late_prob = min(0.95, persona.gst_late_prob + persona.gst_late_prob_drift * m)
        filed_late = rng.random() < late_prob
        if filed_late:
            filing = due + pd.Timedelta(days=int(rng.integers(1, 16)))
        else:
            filing = due - pd.Timedelta(days=int(rng.integers(0, 6)))
        gst_rows.append(
            {
                "applicant_id": applicant_id,
                "month": ts,
                "period": period,
                "declared_turnover": round(declared, 2),
                "tax_paid": tax_paid,
                "due_date": due.normalize(),
                "filing_date": filing.normalize(),
                "filed_late": bool(filed_late),
                "data_source": DATA_SOURCE_LABEL,
            }
        )

        # ---------------- UPI settlements ----------------
        upi_total = inflow * persona.upi_share_of_turnover
        for p, w in enumerate(payer_w):
            payer_amt = upi_total * float(w)
            if payer_amt < 100.0:
                continue
            n_tx = int(rng.integers(1, 4))
            splits = rng.dirichlet(np.ones(n_tx))
            for s in splits:
                amt = round(float(payer_amt * s), 2)
                if amt <= 0:
                    continue
                day = int(rng.integers(1, days_in_month + 1))
                upi_rows.append(
                    {
                        "applicant_id": applicant_id,
                        "txn_date": ts + pd.Timedelta(days=day - 1),
                        "payer_id": f"PYR-{p:02d}",
                        "amount": amt,
                        "data_source": DATA_SOURCE_LABEL,
                    }
                )

        # ---------------- Bank statement ----------------
        emi = (persona.emi_to_inflow + persona.emi_to_inflow_drift * m) * persona.base_monthly_turnover
        emp_count = max(1, round(persona.base_employees * (1.0 + persona.employee_growth) ** m))
        salary = emp_count * persona.salary_per_employee
        suppliers = persona.supplier_ratio * inflow

        # Build dated entries, then apply chronologically to a running balance.
        entries: list[tuple[int, str, str, float]] = []
        for wk, day in enumerate((7, 14, 21, 28)):
            entries.append((day, "CREDIT", "credit", round(inflow / 4.0, 2)))
        if emi > 0:
            entries.append((5, "EMI", "debit", round(emi, 2)))
        entries.append((3, "RENT", "debit", rent))
        entries.append((28, "SALARY", "debit", round(salary, 2)))
        entries.append((12, "SUPPLIER", "debit", round(suppliers * 0.5, 2)))
        entries.append((22, "SUPPLIER", "debit", round(suppliers * 0.5, 2)))
        for day, ttype, direction, amt in sorted(entries, key=lambda e: e[0]):
            balance += amt if direction == "credit" else -amt
            bank_rows.append(
                {
                    "applicant_id": applicant_id,
                    "txn_date": ts + pd.Timedelta(days=min(day, days_in_month) - 1),
                    "txn_type": ttype,
                    "direction": direction,
                    "amount": amt,
                    "balance": round(balance, 2),
                    "data_source": DATA_SOURCE_LABEL,
                }
            )

        # ---------------- EPFO payroll ----------------
        epfo_due = (ts + pd.offsets.MonthEnd(1)) + pd.Timedelta(days=15)
        epfo_late = rng.random() < persona.epfo_late_prob
        epfo_filing = epfo_due + pd.Timedelta(days=int(rng.integers(1, 12))) if epfo_late else epfo_due - pd.Timedelta(days=int(rng.integers(0, 4)))
        epfo_rows.append(
            {
                "applicant_id": applicant_id,
                "month": ts,
                "period": period,
                "employee_count": int(emp_count),
                "wage_bill": round(salary, 2),
                "contribution_paid": round(salary * persona.epfo_rate, 2),
                "due_date": epfo_due.normalize(),
                "filing_date": epfo_filing.normalize(),
                "filed_late": bool(epfo_late),
                "data_source": DATA_SOURCE_LABEL,
            }
        )

    applicant = {
        "id": applicant_id,
        "name": _business_name(rng),
        "sector": SECTORS[int(applicant_id.split("-")[1]) % len(SECTORS)],
        "persona": persona.key,  # hidden in prod-mode; used for demo/eval only
        "history_months": persona.history_months,
        "onboarded_at": months[0].normalize(),
        "data_source": DATA_SOURCE_LABEL,
    }
    return applicant, gst_rows, upi_rows, bank_rows, epfo_rows


def build_frames() -> GeneratedFrames:
    """Generate the full 60-MSME population as pandas DataFrames."""
    applicants: list[dict] = []
    gst: list[dict] = []
    upi: list[dict] = []
    bank: list[dict] = []
    epfo: list[dict] = []

    seq = 0
    for persona in PERSONAS:
        for _ in range(persona.count):
            seq += 1
            applicant_id = f"MSME-{seq:04d}"
            # Deterministic per-MSME stream, offset from the global seed.
            rng = np.random.default_rng(RANDOM_SEED + seq)
            a, g, u, b, e = _generate_one(applicant_id, persona, rng)
            applicants.append(a)
            gst.extend(g)
            upi.extend(u)
            bank.extend(b)
            epfo.extend(e)

    return GeneratedFrames(
        applicants=pd.DataFrame(applicants),
        gst=pd.DataFrame(gst),
        upi=pd.DataFrame(upi).sort_values(["applicant_id", "txn_date"]).reset_index(drop=True),
        bank=pd.DataFrame(bank).sort_values(["applicant_id", "txn_date"]).reset_index(drop=True),
        epfo=pd.DataFrame(epfo),
    )


def _write_sqlite(applicants: pd.DataFrame) -> None:
    """Seed the SQLite applicants table (the officer-console queue source)."""
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.execute("DROP TABLE IF EXISTS applicants")
        conn.execute(
            """
            CREATE TABLE applicants (
                id             TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                sector         TEXT NOT NULL,
                persona        TEXT NOT NULL,
                history_months INTEGER NOT NULL,
                onboarded_at   TEXT NOT NULL,
                data_source    TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO applicants VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r.id,
                    r.name,
                    r.sector,
                    r.persona,
                    int(r.history_months),
                    pd.Timestamp(r.onboarded_at).strftime("%Y-%m-%d"),
                    r.data_source,
                )
                for r in applicants.itertuples(index=False)
            ],
        )
        conn.commit()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # ₹-safe on Windows cp1252 consoles
    except (AttributeError, ValueError):
        pass
    ensure_data_dirs()
    frames = build_frames()

    frames.gst.to_parquet(GST_PARQUET, index=False)
    frames.upi.to_parquet(UPI_PARQUET, index=False)
    frames.bank.to_parquet(BANK_PARQUET, index=False)
    frames.epfo.to_parquet(EPFO_PARQUET, index=False)
    _write_sqlite(frames.applicants)

    print(f"[datagen] seed={RANDOM_SEED}  data_source={DATA_SOURCE_LABEL}")
    print(f"[datagen] applicants : {len(frames.applicants):>6}  -> {SQLITE_PATH}")
    print(f"[datagen] gst rows   : {len(frames.gst):>6}  -> {GST_PARQUET.name}")
    print(f"[datagen] upi rows   : {len(frames.upi):>6}  -> {UPI_PARQUET.name}")
    print(f"[datagen] bank rows  : {len(frames.bank):>6}  -> {BANK_PARQUET.name}")
    print(f"[datagen] epfo rows  : {len(frames.epfo):>6}  -> {EPFO_PARQUET.name}")
    print("[datagen] done.")


if __name__ == "__main__":
    main()
