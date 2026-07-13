import type { ApplicantSummary, ScoreResponse, TrendPoint } from "../api";
import { FlagBanner } from "../components/FlagBanner";
import { ReasonCodes } from "../components/ReasonCodes";
import { RiskRadar } from "../components/RiskRadar";
import { ScoreDial } from "../components/ScoreDial";
import { TrendChart } from "../components/TrendChart";
import { inrFull, recommendationLabel, titleCase } from "../format";

const SUB_LABELS: Record<string, string> = {
  growth: "Growth",
  stability: "Stability",
  compliance: "Compliance",
  liquidity: "Liquidity",
  concentration: "Diversification",
  leverage: "Leverage",
};

function Panel({ title, children, style }: { title?: string; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <section className="card" style={{ padding: 18, ...style }}>
      {title && <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-secondary)" }}>{title}</h3>}
      {children}
    </section>
  );
}

export function HealthCard({
  applicant,
  score,
  trend,
  onBack,
}: {
  applicant: ApplicantSummary;
  score: ScoreResponse;
  trend: TrendPoint[];
  onBack: () => void;
}) {
  const thinFile = applicant.history_months < 12;
  const isFraud = score.recommendation === "REFER_FRAUD_REVIEW";

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <button onClick={onBack} className="card" style={{ padding: "6px 12px", background: "var(--surface-1)", border: "1px solid var(--border)" }}>
          ← Queue
        </button>
        <h2 style={{ margin: 0, fontSize: 22 }}>{applicant.name}</h2>
        <span className="muted">{applicant.sector} · {applicant.id}</span>
        {thinFile && (
          <span style={{
            padding: "2px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600,
            background: "rgba(42,120,214,0.12)", color: "var(--series-1)",
          }}>
            New-to-credit · thin file — no bureau history, still scoreable
          </span>
        )}
      </div>

      {/* Score + recommendation + limit */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(240px, 1fr) 1.4fr", gap: 16 }}>
        <Panel>
          <ScoreDial score={score.setu_score} band={score.band} />
        </Panel>
        <Panel>
          <div style={{ display: "grid", gap: 14 }}>
            <div>
              <div className="muted" style={{ fontSize: 13 }}>Recommendation</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: isFraud ? "var(--status-critical)" : "var(--text-primary)" }}>
                {recommendationLabel(score.recommendation)}
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: 13 }}>Working-capital limit</div>
              <div className="tabular" style={{ fontSize: 24, fontWeight: 700 }}>
                {score.limit_recommendation.amount_inr > 0
                  ? inrFull(score.limit_recommendation.amount_inr)
                  : "— withheld"}
                {score.limit_recommendation.amount_inr > 0 && (
                  <span className="muted" style={{ fontSize: 14, fontWeight: 400 }}>
                    {" "}· {score.limit_recommendation.tenor_months} mo
                  </span>
                )}
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4, maxWidth: 460 }} title={score.limit_recommendation.basis}>
                {score.limit_recommendation.basis}
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <FlagBanner cross={score.cross_validation} />

      {/* Radar + reason codes */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Panel title="Risk radar — six sub-scores">
          <RiskRadar subScores={score.sub_scores} />
          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", marginTop: 6 }}>
            {Object.entries(score.sub_scores).map(([k, v]) => (
              <span key={k} className="tabular muted" style={{ fontSize: 12 }}>
                {SUB_LABELS[k] ?? titleCase(k)} <strong style={{ color: "var(--text-primary)" }}>{v}</strong>
              </span>
            ))}
          </div>
        </Panel>
        <Panel title="Why — top reason codes">
          <ReasonCodes codes={score.reason_codes} />
        </Panel>
      </div>

      <Panel title="Declared GST vs observed bank credits">
        <TrendChart data={trend} />
      </Panel>

      {/* Raw API response — LOS-integration ready (demo beat 5) */}
      <Panel>
        <details>
          <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: 14 }}>
            LOS-ready JSON API response
          </summary>
          <pre className="tabular" style={{
            marginTop: 12, padding: 14, background: "var(--surface-2)", borderRadius: 10,
            overflowX: "auto", fontSize: 12, lineHeight: 1.5,
          }}>
            {JSON.stringify(score, null, 2)}
          </pre>
        </details>
      </Panel>

      <div className="muted" style={{ fontSize: 12, textAlign: "center", paddingBottom: 8 }}>
        Data source: <strong>{score.data_source}</strong> · scored {new Date(score.scored_at).toLocaleString()}
      </div>
    </div>
  );
}
