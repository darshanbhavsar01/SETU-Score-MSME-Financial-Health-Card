// Formatting + band presentation helpers. Pure functions, unit-friendly.

export type Band = "HIGH_RISK" | "WATCH" | "GOOD" | "EXCELLENT";

/** Compact INR: ₹1.23Cr / ₹4.5L / ₹8,000. */
export function inr(amount: number): string {
  if (amount >= 1e7) return `₹${(amount / 1e7).toFixed(2)}Cr`;
  if (amount >= 1e5) return `₹${(amount / 1e5).toFixed(1)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

/** Full INR with grouping: ₹8,00,000. */
export function inrFull(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

const BAND_META: Record<Band, { label: string; varName: string }> = {
  EXCELLENT: { label: "Excellent", varName: "--band-excellent" },
  GOOD: { label: "Good", varName: "--band-good" },
  WATCH: { label: "Watch", varName: "--band-watch" },
  HIGH_RISK: { label: "High Risk", varName: "--band-high_risk" },
};

export function bandColor(band: string): string {
  const meta = BAND_META[band as Band];
  return meta ? `var(${meta.varName})` : "var(--text-muted)";
}

export function bandLabel(band: string): string {
  return BAND_META[band as Band]?.label ?? band;
}

const RECO_LABEL: Record<string, string> = {
  APPROVE_WITH_LIMIT: "Approve with limit",
  MONITOR: "Monitor",
  DECLINE: "Decline",
  REFER_FRAUD_REVIEW: "Refer — fraud review",
};

export function recommendationLabel(reco: string): string {
  return RECO_LABEL[reco] ?? reco;
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
