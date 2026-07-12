"""Persona definitions for the synthetic MSME population (CLAUDE.md §5).

Six personas, ten MSMEs each = 60 firms, 24 months of history (8 for the thin-file
NTC persona). Every knob a generator loop reads lives here as a dataclass field so
there are NO magic numbers buried in `generate.py`.

Each persona encodes "the story the data must tell" and the score band we expect the
pipeline to land in. The expected bands are used ONLY by the end-to-end smoke test
(§9) to prove the pipeline rank-orders seeded personas correctly — they are never
fed back into scoring (that would be circular-validation theatre, guardrail #3).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.config import DEFAULT_HISTORY_MONTHS


@dataclass(frozen=True)
class PersonaConfig:
    """All parameters that shape one persona's synthetic financial history.

    Amounts are in INR. Rates are per-month unless stated otherwise.
    """

    key: str
    label: str
    story: str
    count: int = 10
    history_months: int = DEFAULT_HISTORY_MONTHS

    # --- Turnover (actual underlying business volume) ---
    base_monthly_turnover: float = 800_000.0  # month-1 actual turnover, INR
    monthly_growth_mean: float = 0.02          # mean m/m growth
    monthly_growth_std: float = 0.01           # growth volatility
    turnover_noise: float = 0.06               # multiplicative monthly noise (std)
    seasonal_amplitude: float = 0.0            # festive-quarter (Oct–Dec) peak, fraction
    turnover_floor_fraction: float = 0.0       # revenue floor as fraction of base (0 = none)

    # --- GST (GSTR-3B-like monthly filing) ---
    gst_late_prob: float = 0.03                # base P(late filing) per month
    gst_late_prob_drift: float = 0.0           # added to late prob per month elapsed
    gst_declare_ratio_mean: float = 1.0        # declared / actual turnover (honest ≈ 1)
    gst_declare_ratio_std: float = 0.05
    gst_inflation_factor: float = 1.0          # extra multiplier on declared (fraud > 1)
    gst_round_numbers: bool = False            # round declared turnover to ₹1L (fraud tell)
    gst_effective_tax_rate: float = 0.05       # tax_paid / declared_turnover

    # --- UPI settlement flows ---
    num_payers: int = 22                       # distinct UPI payers
    top_payer_share: float = 0.12              # share of UPI volume from the largest payer
    upi_share_of_turnover: float = 0.60        # fraction of turnover settled via UPI (<1)

    # --- Bank statement ---
    emi_to_inflow: float = 0.15                # EMI outflow / monthly inflow (FOIR-like)
    emi_to_inflow_drift: float = 0.0           # rising leverage per month (stress)
    supplier_ratio: float = 0.48               # supplier/purchase debits / inflow (variable COGS)
    rent_ratio: float = 0.03                   # fixed rent-like debit / base turnover
    liquidity_buffer_months: float = 3.0       # opening balance = this × monthly obligations

    # --- EPFO payroll ---
    base_employees: int = 12
    employee_growth: float = 0.0               # net m/m headcount change (fraction)
    salary_per_employee: float = 16_000.0      # monthly gross wage per head
    epfo_rate: float = 0.12                    # employer PF contribution rate
    epfo_late_prob: float = 0.03

    # --- Expected outcome (reference only; used by the smoke test) ---
    expected_band: str = "GOOD"
    expected_score_min: int = 600
    expected_score_max: int = 750
    expects_fraud_flag: bool = False


# ---------------------------------------------------------------------------
# The six personas. Comments tie each block back to §5's "story the data tells".
# ---------------------------------------------------------------------------

PERSONAS: list[PersonaConfig] = [
    PersonaConfig(
        key="healthy_growth",
        label="Healthy Growth",
        story="Steady 2–4% m/m growth, on-time GST & EPFO, diversified payers, "
        "comfortable liquidity.",
        base_monthly_turnover=850_000.0,
        monthly_growth_mean=0.03,
        monthly_growth_std=0.008,
        turnover_noise=0.05,
        gst_late_prob=0.02,
        num_payers=28,
        top_payer_share=0.10,
        upi_share_of_turnover=0.62,
        emi_to_inflow=0.14,
        supplier_ratio=0.45,
        liquidity_buffer_months=3.5,
        base_employees=14,
        employee_growth=0.01,
        epfo_late_prob=0.02,
        expected_band="EXCELLENT",
        expected_score_min=700,
        expected_score_max=850,
    ),
    PersonaConfig(
        key="seasonal_stable",
        label="Seasonal Stable",
        story="Strong festive-quarter peaks, flat annual trend, disciplined filings.",
        base_monthly_turnover=650_000.0,
        monthly_growth_mean=0.0,
        monthly_growth_std=0.006,
        turnover_noise=0.05,
        seasonal_amplitude=0.55,
        gst_late_prob=0.03,
        num_payers=20,
        top_payer_share=0.14,
        upi_share_of_turnover=0.55,
        emi_to_inflow=0.20,
        supplier_ratio=0.44,
        liquidity_buffer_months=3.0,
        base_employees=10,
        epfo_late_prob=0.03,
        expected_band="GOOD",
        expected_score_min=600,
        expected_score_max=750,
    ),
    PersonaConfig(
        key="declining_stress",
        label="Declining / Stress",
        story="Turnover −3–6% m/m for 8+ months, rising EMI/inflow ratio, delayed "
        "filings creeping in.",
        base_monthly_turnover=950_000.0,
        monthly_growth_mean=-0.035,
        monthly_growth_std=0.010,
        turnover_noise=0.07,
        # Revenue slides then stabilises at ~62% of peak — a stressed-but-operating
        # firm, not a total collapse. The floor bounds the tail losses so the balance
        # stays solvent while still visibly drawing down.
        turnover_floor_fraction=0.62,
        gst_late_prob=0.12,
        gst_late_prob_drift=0.015,   # lateness worsens markedly over the window
        num_payers=16,
        top_payer_share=0.16,
        upi_share_of_turnover=0.52,
        # EMI is a fixed rupee amount; the EMI/inflow *ratio* rises on its own as
        # turnover falls (that is what the leverage sub-score picks up). No drift
        # in the absolute EMI — that would model an ever-growing loan, which is wrong.
        emi_to_inflow=0.22,
        # Moderate buffer + thin margin: the balance hovers low and trends *down* as
        # revenue falls — the trend-aware liquidity sub-score reads that drawdown as the
        # distress signal, and the floor keeps it from going negative.
        supplier_ratio=0.50,
        liquidity_buffer_months=4.5,
        base_employees=12,
        employee_growth=-0.012,
        epfo_late_prob=0.24,
        # Lands in WATCH: weak growth + zero stability + drawn-down liquidity pull it
        # well below the GOOD personas, though diversified payers keep it out of
        # HIGH_RISK. We validate the WATCH band / rank-ordering, not a magic number.
        expected_band="WATCH",
        expected_score_min=450,
        expected_score_max=600,
    ),
    PersonaConfig(
        key="concentration_risk",
        label="Concentration Risk",
        story="Healthy totals but 70%+ of inflows from a single payer.",
        base_monthly_turnover=750_000.0,
        monthly_growth_mean=0.02,
        monthly_growth_std=0.008,
        turnover_noise=0.05,
        gst_late_prob=0.04,
        num_payers=8,
        top_payer_share=0.74,        # single dominant payer → high HHI
        upi_share_of_turnover=0.60,
        emi_to_inflow=0.18,
        supplier_ratio=0.45,
        liquidity_buffer_months=3.0,
        base_employees=11,
        epfo_late_prob=0.03,
        expected_band="WATCH",
        expected_score_min=450,
        expected_score_max=600,
    ),
    PersonaConfig(
        key="ntc_thin_file",
        label="New-to-Credit (Thin File)",
        story="Only 8 months of history, no loans ever, otherwise healthy — the "
        "inclusion story: still scoreable.",
        history_months=8,
        base_monthly_turnover=520_000.0,
        monthly_growth_mean=0.03,
        monthly_growth_std=0.008,
        turnover_noise=0.05,
        gst_late_prob=0.03,
        num_payers=22,
        top_payer_share=0.12,
        upi_share_of_turnover=0.62,
        emi_to_inflow=0.0,           # no loans ever
        supplier_ratio=0.60,
        liquidity_buffer_months=3.0,
        base_employees=8,
        employee_growth=0.01,
        epfo_late_prob=0.03,
        expected_band="GOOD",
        expected_score_min=600,
        expected_score_max=750,
    ),
    PersonaConfig(
        key="inflated_gst_fraud",
        label="Inflated GST (Fraud)",
        story="GST turnover ~3–5× actual UPI+bank inflows, round-number filings.",
        base_monthly_turnover=600_000.0,
        monthly_growth_mean=0.02,
        monthly_growth_std=0.01,
        turnover_noise=0.06,
        gst_late_prob=0.08,
        gst_declare_ratio_mean=1.0,
        gst_inflation_factor=4.0,    # declared ≈ 4× actual inflows
        gst_round_numbers=True,      # round-figure filings
        num_payers=14,
        top_payer_share=0.20,
        upi_share_of_turnover=0.50,
        emi_to_inflow=0.24,
        supplier_ratio=0.44,
        liquidity_buffer_months=2.5,
        base_employees=9,
        epfo_late_prob=0.10,
        expected_band="HIGH_RISK",
        expected_score_min=0,
        expected_score_max=449,      # capped by the fraud flag (§6)
        expects_fraud_flag=True,
    ),
]

PERSONAS_BY_KEY: dict[str, PersonaConfig] = {p.key: p for p in PERSONAS}

# Sector labels drawn round-robin so the officer console queue looks realistic.
SECTORS: list[str] = [
    "Textiles & Apparel",
    "Auto Components",
    "Food Processing",
    "Electronics Trading",
    "Pharmaceuticals",
    "Packaging",
    "Chemicals",
    "Handicrafts Export",
    "Agri Inputs",
    "Light Engineering",
]


def total_msme_count() -> int:
    return sum(p.count for p in PERSONAS)
