import type { ReasonCode } from "../api";

// The structured, explainable drivers behind the score. Direction is shown with an
// arrow + color; the code and evidence carry the meaning.

export function ReasonCodes({ codes }: { codes: ReasonCode[] }) {
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
      {codes.map((c, i) => {
        const negative = c.direction === "negative";
        const color = negative ? "var(--status-critical)" : "var(--status-good)";
        return (
          <li key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <span aria-hidden style={{ color, fontWeight: 700, marginTop: 1 }}>
              {negative ? "▼" : "▲"}
            </span>
            <div>
              <div className="tabular" style={{ fontWeight: 600, fontSize: 13, color }}>
                {c.code}
              </div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{c.evidence}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
