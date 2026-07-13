import { useEffect, useState } from "react";

// Mocked Account Aggregator consent + fetch animation (demo beat 2). The connectors
// are interface-compatible mocks (see connectors/ story); this visualises the consent
// → multi-source pull that a real AA/FIU flow would perform, then hands off to scoring.

const SOURCES = [
  { key: "gst", label: "GST returns (GSTN)" },
  { key: "upi", label: "UPI settlements" },
  { key: "bank", label: "Bank statements (AA)" },
  { key: "epfo", label: "EPFO payroll" },
];

const STEP_MS = 420;

export function ConsentModal({ name, onComplete }: { name: string; onComplete: () => void }) {
  const [fetched, setFetched] = useState(0);

  useEffect(() => {
    if (fetched < SOURCES.length) {
      const t = setTimeout(() => setFetched((n) => n + 1), STEP_MS);
      return () => clearTimeout(t);
    }
    const t = setTimeout(onComplete, 550); // brief beat on "all fetched" before the card
    return () => clearTimeout(t);
  }, [fetched, onComplete]);

  return (
    <div
      role="dialog"
      aria-label="Account Aggregator consent"
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
        display: "grid", placeItems: "center", zIndex: 50,
      }}
    >
      <div className="card" style={{ width: "min(420px, 92vw)", padding: 24 }}>
        <div style={{ fontSize: 13, color: "var(--text-muted)", letterSpacing: 0.4 }}>
          CONSENT GRANTED · ACCOUNT AGGREGATOR
        </div>
        <h3 style={{ margin: "6px 0 4px", fontSize: 18 }}>Fetching {name}'s data</h3>
        <div className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
          Pulling alternate data across four sources…
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {SOURCES.map((s, i) => {
            const done = i < fetched;
            const active = i === fetched;
            return (
              <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span
                  aria-hidden
                  style={{
                    width: 22, height: 22, borderRadius: "50%", display: "grid",
                    placeItems: "center", fontSize: 13, color: "#fff",
                    background: done ? "var(--status-good)" : "var(--gridline)",
                    transition: "background 0.2s",
                  }}
                >
                  {done ? "✓" : ""}
                </span>
                <span style={{
                  color: done || active ? "var(--text-primary)" : "var(--text-muted)",
                  fontWeight: active ? 600 : 400,
                }}>
                  {s.label}
                </span>
                {active && <span className="muted" style={{ marginLeft: "auto", fontSize: 12 }}>fetching…</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
