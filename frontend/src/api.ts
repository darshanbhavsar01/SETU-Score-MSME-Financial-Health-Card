// API client + types. Types mirror backend/app/schemas.py (the frozen §7 contract).
// Paths are relative: same-origin in production, proxied to :8000 in dev.

export interface ReasonCode {
  code: string;
  direction: "positive" | "negative" | "neutral";
  evidence: string;
}

export interface SubScores {
  growth: number;
  stability: number;
  compliance: number;
  liquidity: number;
  concentration: number;
  leverage: number;
}

export interface CrossValidation {
  consistency_score: number;
  flags: ReasonCode[];
}

export interface LimitRecommendation {
  amount_inr: number;
  tenor_months: number;
  basis: string;
}

export interface ScoreResponse {
  applicant_id: string;
  setu_score: number;
  band: string;
  sub_scores: SubScores;
  reason_codes: ReasonCode[];
  cross_validation: CrossValidation;
  limit_recommendation: LimitRecommendation;
  recommendation: string;
  data_source: string;
  scored_at: string;
}

export interface TrendPoint {
  month: string;
  gst_declared: number;
  bank_credit: number;
  upi_total: number;
  net_inflow: number;
}

export interface ApplicantSummary {
  id: string;
  name: string;
  sector: string;
  history_months: number;
  persona: string | null;
  setu_score: number | null;
  band: string | null;
  recommendation: string | null;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json() as Promise<T>;
}

async function postJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: "POST" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  listApplicants: () => getJSON<ApplicantSummary[]>("/applicants"),
  getApplicant: (id: string) => getJSON<ApplicantSummary>(`/applicants/${id}`),
  score: (id: string) => postJSON<ScoreResponse>(`/score/${id}`),
  getScore: (id: string) => getJSON<ScoreResponse>(`/score/${id}`),
  getTrend: (id: string) => getJSON<TrendPoint[]>(`/applicants/${id}/trend`),
};
