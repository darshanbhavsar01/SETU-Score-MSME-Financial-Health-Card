import type { CrossValidation } from "../api";

// Cross-validation banner. When consistency has collapsed (hard fraud flag), it fires
// red with an icon + label (status color never alone). Otherwise it's a calm
// "sources reconcile" confirmation. This is demo beat 3.

export function FlagBanner({ cross }: { cross: CrossValidation }) {
  const negatives = cross.flags.filter((f) => f.direction === "negative");
  const isFraud = negatives.length > 0 && cross.consistency_score < 50;

  const color = isFraud ? "var(--status-critical)" : "var(--status-good)";
  const bg = isFraud ? "rgba(208,59,59,0.10)" : "rgba(12,163,12,0.10)";

  return (
    <div
      role={isFraud ? "alert" : undefined}
      style={{
        border: `1px solid ${color}`,
        background: bg,
        borderRadius: "var(--radius)",
        padding: "14px 16px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span aria-hidden style={{ fontSize: 18 }}>{isFraud ? "⚠️" : "✓"}</span>
        <strong style={{ color }}>
          {isFraud ? "Cross-validation FAILED — refer to fraud review" : "Cross-validation passed"}
        </strong>
        <span className="tabular muted" style={{ marginLeft: "auto", fontSize: 13 }}>
          consistency {cross.consistency_score}/100
        </span>
      </div>
      {cross.flags.length > 0 && (
        <ul style={{ margin: "10px 0 0", paddingLeft: 26, fontSize: 13, color: "var(--text-secondary)" }}>
          {cross.flags.map((f, i) => (
            <li key={i} style={{ marginBottom: 2 }}>
              <span className="tabular" style={{
                color: f.direction === "negative" ? "var(--status-critical)" : "var(--text-muted)",
                fontWeight: 600,
              }}>
                {f.code}
              </span>{" "}
              — {f.evidence}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
