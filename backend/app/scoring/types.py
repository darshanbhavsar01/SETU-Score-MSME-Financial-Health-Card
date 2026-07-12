"""Shared value types for the scoring layer."""

from __future__ import annotations

from dataclasses import dataclass

# Reason-code direction vocabulary.
POSITIVE = "positive"
NEGATIVE = "negative"
NEUTRAL = "neutral"


@dataclass(frozen=True)
class ReasonCode:
    """A structured, explainable driver behind a score (§6).

    e.g. ReasonCode("GST_LATE_FILINGS", "negative", "4 of last 12 GSTR-3B filed late").
    """

    code: str
    direction: str
    evidence: str

    def as_dict(self) -> dict:
        return {"code": self.code, "direction": self.direction, "evidence": self.evidence}


@dataclass(frozen=True)
class SubScoreResult:
    """One sub-score: a 0–100 value plus its top-3 reason codes."""

    value: int
    reason_codes: list[ReasonCode]

    def as_dict(self) -> dict:
        return {"value": self.value, "reason_codes": [r.as_dict() for r in self.reason_codes]}
