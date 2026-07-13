import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { ApplicantSummary, ScoreResponse, TrendPoint } from "./api";
import { ConsentModal } from "./components/ConsentModal";
import { Console } from "./pages/Console";
import { HealthCard } from "./pages/HealthCard";

type Phase = "queue" | "consent" | "card";

export function App() {
  const [applicants, setApplicants] = useState<ApplicantSummary[]>([]);
  const [selected, setSelected] = useState<ApplicantSummary | null>(null);
  const [phase, setPhase] = useState<Phase>("queue");
  const [score, setScore] = useState<ScoreResponse | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadQueue = useCallback(() => {
    api.listApplicants().then(setApplicants).catch((e) => setError(String(e)));
  }, []);

  useEffect(loadQueue, [loadQueue]);

  const onSelect = (a: ApplicantSummary) => {
    setSelected(a);
    setScore(null);
    setError(null);
    setPhase("consent");
  };

  const runScoring = useCallback(() => {
    if (!selected) return;
    Promise.all([api.score(selected.id), api.getTrend(selected.id)])
      .then(([s, t]) => {
        setScore(s);
        setTrend(t);
        setPhase("card");
      })
      .catch((e) => {
        setError(String(e));
        setPhase("queue");
      });
  }, [selected]);

  const onBack = () => {
    setSelected(null);
    setScore(null);
    setPhase("queue");
    loadQueue(); // refresh badges now that this applicant is scored
  };

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "20px 20px 48px" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <div style={{
          width: 34, height: 34, borderRadius: 9, background: "var(--series-1)", color: "#fff",
          display: "grid", placeItems: "center", fontWeight: 800,
        }}>
          S
        </div>
        <div style={{ marginRight: "auto" }}>
          <div style={{ fontWeight: 700, fontSize: 18, lineHeight: 1.1 }}>SETU Score</div>
          <div className="muted" style={{ fontSize: 12 }}>MSME Financial Health Card</div>
        </div>
        <span style={{
          fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 999,
          background: "var(--surface-2)", color: "var(--text-secondary)",
        }}>
          SYNTHETIC DATA · POC
        </span>
      </header>

      {error && (
        <div role="alert" className="card" style={{ padding: 14, marginBottom: 16, borderColor: "var(--status-critical)", color: "var(--status-critical)" }}>
          {error}
        </div>
      )}

      {phase === "card" && selected && score ? (
        <HealthCard applicant={selected} score={score} trend={trend} onBack={onBack} />
      ) : (
        <Console applicants={applicants} onSelect={onSelect} />
      )}

      {phase === "consent" && selected && (
        <ConsentModal name={selected.name} onComplete={runScoring} />
      )}
    </div>
  );
}
