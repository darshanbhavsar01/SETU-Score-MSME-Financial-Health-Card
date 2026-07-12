"""Shared test helper: build a FeatureBundle with controlled arrays."""

from __future__ import annotations

import numpy as np

from backend.app.features.builder import FeatureBundle


def make_bundle(**overrides) -> FeatureBundle:
    """A healthy 24-month firm by default; override individual fields per test."""
    n = overrides.pop("n_months", 24)
    defaults = dict(
        applicant_id="TEST",
        n_months=n,
        # Non-round figures: honest filings are noisy, so the default must not
        # accidentally trip the ₹1L round-number fraud detector.
        blended_turnover=np.full(n, 810_000.0),
        bank_credit=np.full(n, 810_000.0),
        gst_declared=np.full(n, 810_000.0),
        upi_total=np.full(n, 486_000.0),
        net_inflow=np.full(n, 80_000.0),
        closing_balance=np.full(n, 1_500_000.0),
        monthly_obligations=np.full(n, 400_000.0),
        emi=np.full(n, 100_000.0),
        gst_late_flags=np.zeros(n, dtype=bool),
        gst_filing_gap_days=np.full(n, -2.0),
        epfo_late_flags=np.zeros(n, dtype=bool),
        payer_shares=np.full(25, 1 / 25),
        avg_monthly_inflow=800_000.0,
        avg_emi=100_000.0,
    )
    defaults.update(overrides)
    return FeatureBundle(**defaults)
