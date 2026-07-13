import type { ApplicantSummary } from "../api";
import { bandColor, bandLabel } from "../format";

// Officer console: the applicant queue. The three demo firms (§11) are flagged so a
// presenter can find them instantly.

const DEMO_PERSONAS: Record<string, string> = {
  ntc_thin_file: "New-to-credit",
  healthy_growth: "Healthy growth",
  inflated_gst_fraud: "Suspected fraud",
};

function BandChip({ band }: { band: string }) {
  return (
    <span style={{
      padding: "2px 10px", borderRadius: 999, fontSize: 12, fontWeight: 600,
      color: "#fff", background: bandColor(band),
    }}>
      {bandLabel(band)}
    </span>
  );
}

export function Console({
  applicants,
  onSelect,
}: {
  applicants: ApplicantSummary[];
  onSelect: (a: ApplicantSummary) => void;
}) {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Applicant queue</h2>
        <span className="muted">{applicants.length} MSMEs</span>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {applicants.map((a, i) => {
          const demo = a.persona ? DEMO_PERSONAS[a.persona] : undefined;
          return (
            <button
              key={a.id}
              onClick={() => onSelect(a)}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(180px,1.6fr) 1.2fr auto auto",
                alignItems: "center", gap: 12, width: "100%", textAlign: "left",
                padding: "12px 16px", background: "transparent", border: "none",
                borderTop: i === 0 ? "none" : "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>
                  {a.name}
                  {demo && (
                    <span style={{
                      marginLeft: 8, fontSize: 11, fontWeight: 600, padding: "1px 8px",
                      borderRadius: 999, background: "var(--surface-2)", color: "var(--text-secondary)",
                    }}>
                      ★ {demo}
                    </span>
                  )}
                </div>
                <div className="muted" style={{ fontSize: 12 }}>{a.id}</div>
              </div>
              <div className="muted" style={{ fontSize: 13 }}>{a.sector}</div>
              <div className="muted tabular" style={{ fontSize: 12 }}>{a.history_months} mo</div>
              <div style={{ textAlign: "right", minWidth: 120 }}>
                {a.setu_score != null && a.band ? (
                  <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                    <span className="tabular" style={{ fontWeight: 700 }}>{a.setu_score}</span>
                    <BandChip band={a.band} />
                  </span>
                ) : (
                  <span className="muted" style={{ fontSize: 13 }}>not scored →</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
