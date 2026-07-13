import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ApplicantSummary, ScoreResponse, TrendPoint } from "../api";
import { HealthCard } from "../pages/HealthCard";

// Render HealthCard against the SAME golden payloads the backend contract test pins,
// so the UI is proven to render exclusively from the frozen §7 response. vitest runs
// with cwd = frontend/, so the backend golden dir is one level up.
function loadGolden(persona: string): ScoreResponse {
  const path = resolve(process.cwd(), "..", "backend", "tests", "golden", `score_${persona}.json`);
  const g = JSON.parse(readFileSync(path, "utf-8")) as ScoreResponse;
  return { ...g, scored_at: "2026-07-13T00:00:00Z" };
}

const trend: TrendPoint[] = [
  { month: "2024-07", gst_declared: 810000, bank_credit: 800000, upi_total: 480000, net_inflow: 80000 },
];

function applicant(over: Partial<ApplicantSummary>): ApplicantSummary {
  return {
    id: "MSME-0001", name: "Test Traders", sector: "Textiles", history_months: 24,
    persona: null, setu_score: null, band: null, recommendation: null, ...over,
  };
}

describe("HealthCard", () => {
  it("renders the healthy score, band, recommendation and limit from the payload", () => {
    const score = loadGolden("healthy_growth");
    render(<HealthCard applicant={applicant({ name: "Navkar Agro" })} score={score} trend={trend} onBack={() => {}} />);

    expect(screen.getByText("Navkar Agro")).toBeInTheDocument();
    expect(screen.getByText(String(score.setu_score))).toBeInTheDocument();
    expect(screen.getByText("Excellent")).toBeInTheDocument();
    expect(screen.getByText("Approve with limit")).toBeInTheDocument();
    // Limit rendered in full INR grouping.
    expect(screen.getByText(new RegExp(score.limit_recommendation.amount_inr.toLocaleString("en-IN")))).toBeInTheDocument();
    // Cross-validation passed (no fraud).
    expect(screen.getByText("Cross-validation passed")).toBeInTheDocument();
  });

  it("fires the fraud banner and withholds the limit for the fraud payload", () => {
    const score = loadGolden("inflated_gst_fraud");
    render(<HealthCard applicant={applicant({ id: "MSME-0051", name: "Om Udyog" })} score={score} trend={trend} onBack={() => {}} />);

    expect(screen.getByText(/Cross-validation FAILED/)).toBeInTheDocument();
    expect(screen.getAllByText(/withheld/).length).toBeGreaterThan(0);
    expect(screen.getByText("High Risk")).toBeInTheDocument();
    // The GST-vs-bank fraud flag evidence is surfaced (banner + raw JSON).
    expect(screen.getAllByText(/GST_VS_BANK/).length).toBeGreaterThan(0);
  });

  it("shows the thin-file inclusion caption for short-history applicants", () => {
    const score = loadGolden("ntc_thin_file");
    render(<HealthCard applicant={applicant({ id: "MSME-0041", history_months: 8 })} score={score} trend={trend} onBack={() => {}} />);
    expect(screen.getByText(/still scoreable/)).toBeInTheDocument();
  });
});
