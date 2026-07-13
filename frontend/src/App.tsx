import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { ApplicantSummary, ScoreResponse, TrendPoint } from "./api";
import { ConsentModal } from "./components/ConsentModal";
import { Footer } from "./components/Footer";
import { Console } from "./pages/Console";
import { HealthCard } from "./pages/HealthCard";
import { Home } from "./pages/Home";

type Phase = "home" | "queue" | "consent" | "card";

export function App() {
  const [applicants, setApplicants] = useState<ApplicantSummary[]>([]);
  const [selected, setSelected] = useState<ApplicantSummary | null>(null);
  const [phase, setPhase] = useState<Phase>("home");
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

  const goHome = () => {
    setSelected(null);
    setScore(null);
    setPhase("home");
  };

  const enterConsole = () => {
    setError(null);
    setPhase("queue");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <header style={{
        display: "flex", alignItems: "center", gap: 12, padding: "16px 20px",
        borderBottom: phase === "home" ? "1px solid var(--border)" : undefined,
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", width: "100%", display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={goHome}
            style={{
              display: "flex", alignItems: "center", gap: 10, background: "transparent",
              border: "none", padding: 0, marginRight: "auto",
            }}
            aria-label="SETU Score home"
          >
            <span style={{
              width: 34, height: 34, borderRadius: 9, background: "var(--series-1)", color: "#fff",
              display: "grid", placeItems: "center", fontWeight: 800,
            }}>
              S
            </span>
            <span style={{ textAlign: "left" }}>
              <div style={{ fontWeight: 700, fontSize: 18, lineHeight: 1.1, color: "var(--text-primary)" }}>SETU Score</div>
              <div className="muted" style={{ fontSize: 12 }}>MSME Financial Health Card</div>
            </span>
          </button>
          {phase !== "home" && (
            <button
              onClick={goHome}
              className="muted"
              style={{ background: "transparent", border: "none", fontSize: 13, fontWeight: 600 }}
            >
              ← Home
            </button>
          )}
          <span style={{
            fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 999,
            background: "var(--surface-2)", color: "var(--text-secondary)",
          }}>
            SYNTHETIC DATA · POC
          </span>
        </div>
      </header>

      <main style={{ flex: 1 }}>
        {phase === "home" ? (
          <Home onLaunch={enterConsole} />
        ) : (
          <div style={{ maxWidth: 1000, margin: "0 auto", padding: "20px 20px 48px" }}>
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
        )}
      </main>

      <Footer />
    </div>
  );
}
