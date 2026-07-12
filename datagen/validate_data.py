"""Data invariant checks for the synthetic MSME population (CLAUDE.md §5).

Runs in `make data` / CI. Asserts the structural and semantic invariants the rest
of the pipeline relies on, and — crucially (§5) — that the fraud persona violates
*exactly* the intended invariant (GST turnover ≫ observed inflows) and no others.

Run from the repo root:  python -m datagen.validate_data
Exits non-zero (with a printed report) if any check fails.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass

import pandas as pd

from backend.app.config import (
    BANK_PARQUET,
    EPFO_PARQUET,
    GST_PARQUET,
    SQLITE_PATH,
    UPI_PARQUET,
)
from datagen.personas import PERSONAS_BY_KEY, total_msme_count

FRAUD_KEY = "inflated_gst_fraud"
CONCENTRATION_KEY = "concentration_risk"

# GST-declared vs bank-credit tolerance. Honest filers stay well inside this band;
# the fraud persona blows past it (that IS the fraud signal cross_checks.py keys on).
GST_BANK_LOW, GST_BANK_HIGH = 0.6, 1.4
FRAUD_MIN_RATIO = 2.5  # fraud declared turnover ≥ 2.5× bank credits


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _load() -> dict:
    app = sqlite3.connect(SQLITE_PATH)
    applicants = pd.read_sql("SELECT * FROM applicants", app)
    app.close()
    return {
        "applicants": applicants,
        "persona": dict(zip(applicants.id, applicants.persona)),
        "gst": pd.read_parquet(GST_PARQUET),
        "upi": pd.read_parquet(UPI_PARQUET),
        "bank": pd.read_parquet(BANK_PARQUET),
        "epfo": pd.read_parquet(EPFO_PARQUET),
    }


def _monthly_credit(bank: pd.DataFrame) -> pd.DataFrame:
    c = bank[bank.direction == "credit"].copy()
    c["m"] = c.txn_date.dt.to_period("M")
    return c.groupby(["applicant_id", "m"], as_index=False).amount.sum().rename(
        columns={"amount": "bank_credit"}
    )


def _monthly_upi(upi: pd.DataFrame) -> pd.DataFrame:
    u = upi.copy()
    u["m"] = u.txn_date.dt.to_period("M")
    return u.groupby(["applicant_id", "m"], as_index=False).amount.sum().rename(
        columns={"amount": "upi"}
    )


def _monthly_gst(gst: pd.DataFrame) -> pd.DataFrame:
    g = gst.copy()
    g["m"] = g.month.dt.to_period("M")
    return g.groupby(["applicant_id", "m"], as_index=False).declared_turnover.sum().rename(
        columns={"declared_turnover": "gst"}
    )


def run_checks() -> list[Check]:
    d = _load()
    persona = d["persona"]
    checks: list[Check] = []

    # 1. Population size and per-persona counts.
    n = len(d["applicants"])
    checks.append(Check("applicant_count", n == total_msme_count(),
                        f"{n} applicants (expected {total_msme_count()})"))
    counts = d["applicants"].persona.value_counts().to_dict()
    bad = {k: counts.get(k, 0) for k, p in PERSONAS_BY_KEY.items() if counts.get(k, 0) != p.count}
    checks.append(Check("per_persona_counts", not bad, "all 10 each" if not bad else f"off: {bad}"))

    # 2. History length per persona (thin-file == 8, others == 24).
    hist = d["gst"].groupby("applicant_id").size()
    hist_bad = [
        aid for aid, cnt in hist.items()
        if cnt != PERSONAS_BY_KEY[persona[aid]].history_months
    ]
    checks.append(Check("history_months", not hist_bad,
                        "GST months match persona" if not hist_bad else f"mismatch: {hist_bad[:5]}"))

    # 3. No NaNs anywhere.
    nan_tables = [name for name in ("gst", "upi", "bank", "epfo") if d[name].isna().any().any()]
    checks.append(Check("no_nans", not nan_tables,
                        "clean" if not nan_tables else f"NaNs in {nan_tables}"))

    # 4. Positive amounts; non-negative balances.
    pos_ok = (
        (d["gst"].declared_turnover > 0).all()
        and (d["upi"].amount > 0).all()
        and (d["bank"].amount > 0).all()
        and (d["epfo"].wage_bill > 0).all()
    )
    checks.append(Check("positive_amounts", bool(pos_ok), "all amounts > 0"))
    min_bal = float(d["bank"].balance.min())
    checks.append(Check("non_negative_balance", min_bal >= 0, f"min closing balance = ₹{min_bal:,.0f}"))

    # 5. Dates monotonic per applicant (non-decreasing) across every series.
    def monotonic(df: pd.DataFrame, col: str) -> bool:
        return bool(df.groupby("applicant_id")[col].apply(lambda s: s.is_monotonic_increasing).all())

    mono_ok = (
        monotonic(d["upi"].sort_values(["applicant_id", "txn_date"]), "txn_date")
        and monotonic(d["bank"].sort_values(["applicant_id", "txn_date"]), "txn_date")
        and monotonic(d["gst"].sort_values(["applicant_id", "month"]), "month")
        and monotonic(d["epfo"].sort_values(["applicant_id", "month"]), "month")
    )
    checks.append(Check("dates_monotonic", mono_ok, "sorted per applicant"))

    # 6. UPI monthly total <= bank credits — must hold for EVERY persona, fraud
    #    included (the fraud is only in *declared GST*, not in the money that moved).
    mu = _monthly_upi(d["upi"])
    mc = _monthly_credit(d["bank"])
    upibank = mu.merge(mc, on=["applicant_id", "m"], how="inner")
    upi_viol = upibank[upibank.upi > upibank.bank_credit + 1.0]  # ₹1 float tolerance
    checks.append(Check("upi_le_bank_all", upi_viol.empty,
                        "UPI ≤ bank credits everywhere" if upi_viol.empty
                        else f"{len(upi_viol)} violations"))

    # 7 & 8. GST-vs-bank ratio: honest personas inside tolerance; fraud far above,
    #        and fraud violates ONLY this invariant.
    mg = _monthly_gst(d["gst"])
    gb = mg.merge(mc, on=["applicant_id", "m"], how="inner")
    gb["ratio"] = gb.gst / gb.bank_credit
    gb["persona"] = gb.applicant_id.map(persona)

    honest = gb[gb.persona != FRAUD_KEY]
    honest_mean = honest.groupby("applicant_id").ratio.mean()
    honest_bad = honest_mean[(honest_mean < GST_BANK_LOW) | (honest_mean > GST_BANK_HIGH)]
    checks.append(Check("honest_gst_in_tolerance", honest_bad.empty,
                        f"all honest filers in [{GST_BANK_LOW},{GST_BANK_HIGH}]" if honest_bad.empty
                        else f"{len(honest_bad)} out of band"))

    fraud = gb[gb.persona == FRAUD_KEY]
    fraud_mean = fraud.groupby("applicant_id").ratio.mean()
    fraud_ok = bool((fraud_mean >= FRAUD_MIN_RATIO).all())
    checks.append(Check("fraud_gst_inflated", fraud_ok,
                        f"fraud GST/bank ratios min={fraud_mean.min():.1f} (≥{FRAUD_MIN_RATIO})"))

    # Fraud persona must be clean on every OTHER invariant.
    fraud_ids = [a for a, p in persona.items() if p == FRAUD_KEY]
    fraud_bank = d["bank"][d["bank"].applicant_id.isin(fraud_ids)]
    fraud_upi_viol = upi_viol[upi_viol.applicant_id.isin(fraud_ids)]
    fraud_only_ok = bool((fraud_bank.balance >= 0).all()) and fraud_upi_viol.empty
    checks.append(Check("fraud_violates_only_gst", fraud_only_ok,
                        "fraud clean on balance & UPI≤bank"))

    # 9. Concentration persona: top-payer share high; everyone else diversified.
    u = d["upi"].copy()
    payer_tot = u.groupby(["applicant_id", "payer_id"]).amount.sum()
    top_share = payer_tot.groupby("applicant_id").apply(lambda s: s.max() / s.sum())
    conc_ids = [a for a, p in persona.items() if p == CONCENTRATION_KEY]
    conc_ok = bool((top_share.loc[conc_ids] >= 0.6).all())
    others = top_share.drop(index=conc_ids)
    others_ok = bool((others < 0.55).all())
    checks.append(Check("concentration_top_payer", conc_ok and others_ok,
                        f"conc min top-share={top_share.loc[conc_ids].min():.2f}, "
                        f"others max={others.max():.2f}"))

    # 10. Round-number tell: fraud declared turnover is a multiple of ₹1 lakh.
    fr_gst = d["gst"][d["gst"].applicant_id.isin(fraud_ids)]
    round_ok = bool((fr_gst.declared_turnover % 100_000 == 0).all())
    checks.append(Check("fraud_round_numbers", round_ok, "fraud filings are ₹1L multiples"))

    return checks


def main() -> int:
    # Windows consoles default to cp1252, which can't encode "₹". Force UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    checks = run_checks()
    width = max(len(c.name) for c in checks)
    print("\n=== SETU synthetic-data validation ===")
    for c in checks:
        mark = "PASS" if c.ok else "FAIL"
        print(f"  [{mark}] {c.name.ljust(width)}  {c.detail}")
    failed = [c for c in checks if not c.ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed.")
    if failed:
        print("VALIDATION FAILED:", ", ".join(c.name for c in failed))
        return 1
    print("All invariants hold.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
