"""The six explainable sub-scores (CLAUDE.md §6).

Each is a pure function of a FeatureBundle returning a SubScoreResult (0–100 value +
top-3 reason codes). No I/O, no globals — trivially unit-testable with hand-built
fixtures. The 0–100 mappings are deliberately simple, monotonic, and clamped so a
credit officer can reason about them.
"""

from __future__ import annotations

import numpy as np

from backend.app.features.builder import FeatureBundle
from backend.app.scoring.types import NEGATIVE, POSITIVE, ReasonCode, SubScoreResult


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _top3(reasons: list[ReasonCode]) -> list[ReasonCode]:
    return reasons[:3]


def _score(value: float, reasons: list[ReasonCode]) -> SubScoreResult:
    return SubScoreResult(value=int(round(_clamp(value))), reason_codes=_top3(reasons))


def growth(f: FeatureBundle) -> SubScoreResult:
    """Blended-turnover trend (§6).

    With ≥24 months we compare the last 12 vs the prior 12 (year-over-year), which is
    immune to intra-year seasonality; with shorter history we fall back to a
    half-window trailing comparison. Window label reflects which was used.
    """
    n = f.n_months
    if n >= 24:
        w, label = 12, "YoY"
    else:
        w, label = min(6, n // 2), f"{min(6, n // 2)}m vs prior"
    trailing = f.blended_turnover[-w:].sum()
    prior = f.blended_turnover[-2 * w : -w].sum()
    g = (trailing / prior - 1.0) if prior > 0 else 0.0

    # g≈+0.4 (healthy YoY) → saturates 100; flat → ~55; strong decline → ~0.
    value = 55.0 + g * 130.0
    pct = g * 100.0
    reasons: list[ReasonCode] = []
    if g >= 0.05:
        reasons.append(ReasonCode("TURNOVER_GROWTH", POSITIVE,
                                  f"blended turnover up {pct:.0f}% ({label})"))
    elif g <= -0.05:
        reasons.append(ReasonCode("TURNOVER_DECLINE", NEGATIVE,
                                  f"blended turnover down {abs(pct):.0f}% ({label})"))
    else:
        reasons.append(ReasonCode("TURNOVER_FLAT", POSITIVE,
                                  f"blended turnover roughly flat ({pct:+.0f}% {label})"))
    if n < 12:
        reasons.append(ReasonCode("SHORT_HISTORY", NEGATIVE,
                                  f"only {n} months of history — trend less certain"))
    return _score(value, reasons)


def stability(f: FeatureBundle) -> SubScoreResult:
    """Coefficient of variation of monthly net inflows; penalise negative months (§6)."""
    net = f.net_inflow
    mean = float(np.mean(net))
    std = float(np.std(net))
    cv = (std / mean) if mean > 0 else 5.0  # chronic non-positive mean → very unstable
    neg_months = int((net < 0).sum())

    value = 100.0 - cv * 110.0 - neg_months * 4.0
    reasons: list[ReasonCode] = []
    if cv <= 0.20 and mean > 0:
        reasons.append(ReasonCode("STABLE_CASHFLOW", POSITIVE,
                                  f"net inflow CV {cv:.2f} — low volatility"))
    elif cv >= 0.40 or mean <= 0:
        reasons.append(ReasonCode("VOLATILE_CASHFLOW", NEGATIVE,
                                  f"net inflow CV {cv:.2f} — high volatility"))
    if neg_months > 0:
        reasons.append(ReasonCode("NEGATIVE_NET_MONTHS", NEGATIVE,
                                  f"{neg_months} month(s) with net cash outflow"))
    if not reasons:
        reasons.append(ReasonCode("MODERATE_CASHFLOW", POSITIVE,
                                  f"net inflow CV {cv:.2f}"))
    return _score(value, reasons)


def compliance(f: FeatureBundle) -> SubScoreResult:
    """GST + EPFO on-time filing discipline (§6)."""
    n = f.n_months
    gst_late = int(f.gst_late_flags.sum())
    epfo_late = int(f.epfo_late_flags.sum())
    gst_on_time = 1.0 - gst_late / n
    epfo_on_time = 1.0 - epfo_late / n

    # GST weighted a bit above EPFO (turnover filing is the primary discipline signal).
    value = 100.0 * (0.6 * gst_on_time + 0.4 * epfo_on_time)
    reasons: list[ReasonCode] = []
    if gst_late == 0 and epfo_late == 0:
        reasons.append(ReasonCode("ALL_FILINGS_ON_TIME", POSITIVE,
                                  f"all {n} GST & EPFO filings on time"))
    if gst_late > 0:
        reasons.append(ReasonCode("GST_LATE_FILINGS", NEGATIVE,
                                  f"{gst_late} of {n} GSTR-3B filed late"))
    if epfo_late > 0:
        reasons.append(ReasonCode("EPFO_LATE_FILINGS", NEGATIVE,
                                  f"{epfo_late} of {n} EPFO contributions filed late"))
    return _score(value, reasons)


def liquidity(f: FeatureBundle) -> SubScoreResult:
    """Recent cash level AND its trajectory vs fixed monthly obligations (§6).

    Obligations = EMI + rent + payroll (the non-discretionary monthly commitments).
    Two components:
      * level  — trailing-6m avg closing balance ÷ obligations ('months covered').
      * trend  — a penalty when the balance is being drawn down (recent avg well below
                 the earlier avg). A falling cash balance is a classic distress signal,
                 so a firm bleeding its buffer scores low on liquidity even while the
                 absolute level still looks comfortable.
    """
    n = f.n_months
    w = min(6, n)
    recent_close = float(np.mean(f.closing_balance[-w:]))
    recent_oblig = float(np.mean(f.monthly_obligations[-w:]))
    ratio = (recent_close / recent_oblig) if recent_oblig > 0 else 0.0

    # ratio≥3 → level ~100; 1.5 → ~52; 0.75 → ~29; near 0 → ~5.
    level = (ratio / 3.0) * 95.0 + 5.0

    early_close = float(np.mean(f.closing_balance[:w])) if n >= 2 * w else float(f.closing_balance[0])
    drawdown = (1.0 - recent_close / early_close) if early_close > 0 else 0.0
    drawdown = max(0.0, drawdown)  # only shrinking balances are penalised
    penalty = min(drawdown, 1.0) * 85.0

    value = level - penalty
    reasons: list[ReasonCode] = []
    if drawdown >= 0.25:
        reasons.append(ReasonCode("DECLINING_CASH_BALANCE", NEGATIVE,
                                  f"closing balance down {drawdown * 100:.0f}% — drawing down buffer"))
    if ratio >= 2.5 and drawdown < 0.25:
        reasons.append(ReasonCode("STRONG_LIQUIDITY", POSITIVE,
                                  f"cash covers {ratio:.1f}× monthly fixed obligations"))
    elif ratio < 1.0:
        reasons.append(ReasonCode("TIGHT_LIQUIDITY", NEGATIVE,
                                  f"cash covers only {ratio:.1f}× monthly fixed obligations"))
    elif not reasons:
        reasons.append(ReasonCode("ADEQUATE_LIQUIDITY", POSITIVE,
                                  f"cash covers {ratio:.1f}× monthly fixed obligations"))
    return _score(value, reasons)


def concentration(f: FeatureBundle) -> SubScoreResult:
    """Herfindahl index over UPI payer distribution — lower HHI is better (§6)."""
    shares = f.payer_shares
    hhi = float(np.sum(shares**2)) if shares.size else 1.0
    top_share = float(np.max(shares)) if shares.size else 1.0

    # Diversified (HHI≈0.05) → ~93; single dominant payer (HHI≈0.55) → ~20.
    value = 100.0 - hhi * 145.0
    reasons: list[ReasonCode] = []
    if top_share >= 0.5:
        reasons.append(ReasonCode("HIGH_CUSTOMER_CONCENTRATION", NEGATIVE,
                                  f"top payer = {top_share * 100:.0f}% of UPI inflows (HHI {hhi:.2f})"))
    elif hhi <= 0.12:
        reasons.append(ReasonCode("DIVERSIFIED_PAYERS", POSITIVE,
                                  f"well-diversified payer base (HHI {hhi:.2f})"))
    else:
        reasons.append(ReasonCode("MODERATE_CONCENTRATION", NEGATIVE,
                                  f"top payer = {top_share * 100:.0f}% of UPI inflows (HHI {hhi:.2f})"))
    return _score(value, reasons)


def leverage(f: FeatureBundle) -> SubScoreResult:
    """Existing EMI outflow / average monthly inflow — FOIR-like (§6)."""
    foir = (f.avg_emi / f.avg_monthly_inflow) if f.avg_monthly_inflow > 0 else 0.0

    # No debt (foir=0) → 100; foir 0.30 → ~52; foir 0.5 → ~20.
    value = 100.0 - foir * 160.0
    reasons: list[ReasonCode] = []
    if foir == 0:
        reasons.append(ReasonCode("NO_EXISTING_DEBT", POSITIVE,
                                  "no existing EMI obligations"))
    elif foir >= 0.35:
        reasons.append(ReasonCode("HIGH_EMI_BURDEN", NEGATIVE,
                                  f"EMI = {foir * 100:.0f}% of monthly inflow (FOIR)"))
    else:
        reasons.append(ReasonCode("MANAGEABLE_LEVERAGE", POSITIVE,
                                  f"EMI = {foir * 100:.0f}% of monthly inflow (FOIR)"))
    return _score(value, reasons)


# Ordered registry used by the composite scorer and the API contract.
SUBSCORE_FUNCS = {
    "growth": growth,
    "stability": stability,
    "compliance": compliance,
    "liquidity": liquidity,
    "concentration": concentration,
    "leverage": leverage,
}


def all_subscores(f: FeatureBundle) -> dict[str, SubScoreResult]:
    return {name: fn(f) for name, fn in SUBSCORE_FUNCS.items()}
