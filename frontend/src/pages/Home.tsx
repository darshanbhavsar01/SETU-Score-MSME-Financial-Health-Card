import { ScoreDial } from "../components/ScoreDial";

// Landing page: problem, solution + business value, technical/AI-ML explanation,
// demo CTA. Sections are full-bleed with an inner max-width so it reads as a
// marketing page rather than the constrained officer-console app shell.

function Section({
  id,
  children,
  tone,
}: {
  id?: string;
  children: React.ReactNode;
  tone?: "surface" | "plain";
}) {
  return (
    <section
      id={id}
      style={{
        background: tone === "surface" ? "var(--surface-2)" : "transparent",
        borderTop: tone === "surface" ? "1px solid var(--border)" : undefined,
        borderBottom: tone === "surface" ? "1px solid var(--border)" : undefined,
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "56px 20px" }}>{children}</div>
    </section>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 12, fontWeight: 700, letterSpacing: 0.8, textTransform: "uppercase",
        color: "var(--series-1)", marginBottom: 10,
      }}
    >
      {children}
    </div>
  );
}

function Grid({ min, children }: { min: number; children: React.ReactNode }) {
  return (
    <div style={{
      display: "grid", gap: 16, marginTop: 24,
      gridTemplateColumns: `repeat(auto-fit, minmax(${min}px, 1fr))`,
    }}>
      {children}
    </div>
  );
}

function Card({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ padding: 20 }}>
      <div style={{ fontSize: 22, marginBottom: 10 }} aria-hidden>{icon}</div>
      <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 15 }}>{title}</div>
      <div className="muted" style={{ fontSize: 13.5, lineHeight: 1.6 }}>{children}</div>
    </div>
  );
}

const PROBLEMS = [
  {
    icon: "🚫",
    title: "Credit-invisible by design",
    body: "New-to-Credit and New-to-Bank MSMEs have no bureau history, so traditional scoring can't assess them at all — not \"high risk\", just invisible.",
  },
  {
    icon: "🧩",
    title: "Four disconnected data sources",
    body: "GST returns, UPI settlements, bank statements, and EPFO payroll each tell part of the story, but sit in separate systems an underwriter has to manually reconcile.",
  },
  {
    icon: "🐌",
    title: "Slow, manual underwriting",
    body: "Cross-checking turnover across filings and statements by hand takes days per applicant — a hard ceiling on how many credit-invisible firms a bank can even evaluate.",
  },
  {
    icon: "🕵️",
    title: "Inflated filings are hard to catch",
    body: "A GST filing inflated against real bank/UPI inflows can slip past a manual review — there's no systematic, always-on cross-source check.",
  },
];

const BUSINESS_POINTS = [
  {
    title: "Expands the addressable book",
    body: "Reaches the New-to-Credit / New-to-Bank segment traditional bureau scores simply cannot rate — inclusion, not just risk-scoring.",
  },
  {
    title: "Underwriting in seconds, not days",
    body: "What used to be manual cross-referencing across four filings collapses into one API call that returns a scored, explained decision.",
  },
  {
    title: "Fraud-aware by construction",
    body: "Every score runs through an automatic GST-vs-bank-vs-UPI consistency check before a limit is ever recommended — inflated filings are flagged, not missed.",
  },
  {
    title: "Conservative capital exposure",
    body: "The working-capital limit is derived from the minimum of GST-declared and bank-observed inflows — prudent by construction, not by policy exception.",
  },
  {
    title: "Auditable, not a black box",
    body: "Every sub-score ships with structured, human-readable reason codes — the kind of explainability compliance and credit-risk teams can actually sign off on.",
  },
  {
    title: "Drop-in, LOS-ready",
    body: "One JSON response — score, sub-scores, reason codes, flags, limit — designed to plug into an existing Loan Origination System with no reshaping.",
  },
];

const TECH_POINTS = [
  {
    icon: "⚖️",
    title: "Explainable rules engine",
    body: "Six auditable sub-scores — Growth, Cash-flow Stability, Compliance, Liquidity, Customer Concentration, Leverage — each a pure function with weighted reason codes, not a black box.",
  },
  {
    icon: "🔎",
    title: "Cross-source fraud validation",
    body: "Deterministic statistical checks reconcile declared GST turnover against observed bank credits and UPI settlement volume, plus a round-number filing detector.",
  },
  {
    icon: "🤖",
    title: "ML sanity-check layer",
    body: "An XGBoost classifier validates that the six engineered features carry real separable signal for risk — a feature sanity-check that supports the rules engine, never a black-box decision-maker.",
  },
  {
    icon: "✨",
    title: "Generative narrative, on demand",
    body: "An optional Gemini-powered layer turns the computed reason codes into a fluent officer summary, with a cascading multi-model fallback and a deterministic template as the always-available default.",
  },
  {
    icon: "🗄️",
    title: "Data engine",
    body: "DuckDB analytics over Parquet powers feature computation; a FastAPI backend and React frontend serve the same explainable JSON contract to both the UI and any LOS integration.",
  },
];

export function Home({ onLaunch }: { onLaunch: () => void }) {
  return (
    <div>
      {/* Hero */}
      <Section>
        <div style={{
          display: "grid", gap: 40, alignItems: "center",
          gridTemplateColumns: "minmax(280px, 1.2fr) minmax(220px, 0.8fr)",
        }}>
          <div>
            <div style={{
              display: "inline-block", fontSize: 12, fontWeight: 700, padding: "4px 12px",
              borderRadius: 999, background: "var(--surface-2)", color: "var(--text-secondary)",
              marginBottom: 18, border: "1px solid var(--border)",
            }}>
              IDBI Innovate 2026 · Track 3 · Synthetic data POC
            </div>
            <h1 style={{ fontSize: 42, lineHeight: 1.12, margin: "0 0 16px", letterSpacing: -0.5 }}>
              Making credit-invisible MSMEs <span style={{ color: "var(--series-1)" }}>assessable</span>.
            </h1>
            <p className="muted" style={{ fontSize: 17, lineHeight: 1.6, maxWidth: 540, margin: "0 0 28px" }}>
              SETU Score aggregates GST returns, UPI settlements, bank statements, and
              EPFO payroll into one explainable 0–900 financial health score — with a
              six-axis risk radar, automatic fraud cross-validation, and a conservative
              working-capital limit recommendation, all served through a single
              LOS-ready JSON API.
            </p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button
                onClick={onLaunch}
                style={{
                  padding: "12px 22px", borderRadius: 10, border: "none",
                  background: "var(--series-1)", color: "#fff", fontWeight: 700, fontSize: 15,
                }}
              >
                Open the Officer Console →
              </button>
              <a
                href="#technical"
                className="card"
                style={{
                  padding: "12px 22px", fontWeight: 600, fontSize: 15,
                  color: "var(--text-primary)", textDecoration: "none",
                }}
              >
                See how it works
              </a>
            </div>
          </div>
          <div className="card" style={{ padding: 28, justifySelf: "center" }}>
            <ScoreDial score={809} band="EXCELLENT" />
            <div className="muted" style={{ textAlign: "center", fontSize: 12, marginTop: 4 }}>
              Example score — computed live from synthetic data
            </div>
          </div>
        </div>
      </Section>

      {/* Problem */}
      <Section tone="surface" id="problem">
        <Eyebrow>The problem</Eyebrow>
        <h2 style={{ fontSize: 28, margin: "0 0 8px" }}>Millions of MSMEs are invisible to credit</h2>
        <p className="muted" style={{ fontSize: 15, maxWidth: 680, lineHeight: 1.6 }}>
          A large share of India's MSMEs are New-to-Credit or New-to-Bank — not because
          they're risky, but because there's no bureau history to score them against.
          The financial signal exists; it's just fragmented, manual, and slow to check.
        </p>
        <Grid min={230}>
          {PROBLEMS.map((p) => (
            <Card key={p.title} icon={p.icon} title={p.title}>{p.body}</Card>
          ))}
        </Grid>
      </Section>

      {/* Solution + business terms */}
      <Section id="solution">
        <Eyebrow>The solution</Eyebrow>
        <h2 style={{ fontSize: 28, margin: "0 0 8px" }}>One explainable score, four alternate data sources</h2>
        <p className="muted" style={{ fontSize: 15, maxWidth: 680, lineHeight: 1.6, marginBottom: 8 }}>
          SETU Score blends GST filings, UPI settlement flows, bank statements, and EPFO
          payroll into a single 0–900 composite, built from six transparent sub-scores —
          each with its own top reason codes — plus a fraud-aware limit recommendation
          a credit officer can approve with confidence.
        </p>

        <div style={{ marginTop: 32 }}>
          <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>Why lenders choose it</div>
          <Grid min={250}>
            {BUSINESS_POINTS.map((b) => (
              <div key={b.title} className="card" style={{ padding: 18 }}>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 6 }}>{b.title}</div>
                <div className="muted" style={{ fontSize: 13.5, lineHeight: 1.6 }}>{b.body}</div>
              </div>
            ))}
          </Grid>
        </div>
      </Section>

      {/* Technical / AI+ML */}
      <Section tone="surface" id="technical">
        <Eyebrow>Under the hood</Eyebrow>
        <h2 style={{ fontSize: 28, margin: "0 0 8px" }}>Explainable-by-design, AI-augmented</h2>
        <p className="muted" style={{ fontSize: 15, maxWidth: 680, lineHeight: 1.6 }}>
          Credit decisions need to be defensible, not just accurate. So the score itself
          comes from a transparent rules engine — AI and ML are layered on top to
          validate that engine and to explain its output in plain English, never to
          replace the audit trail.
        </p>
        <Grid min={240}>
          {TECH_POINTS.map((t) => (
            <Card key={t.title} icon={t.icon} title={t.title}>{t.body}</Card>
          ))}
        </Grid>
      </Section>

      {/* CTA */}
      <Section id="demo">
        <div className="card" style={{
          padding: "40px 32px", textAlign: "center", background: "var(--surface-1)",
        }}>
          <h2 style={{ fontSize: 24, margin: "0 0 10px" }}>See it score a firm live</h2>
          <p className="muted" style={{ maxWidth: 520, margin: "0 auto 22px", fontSize: 14.5, lineHeight: 1.6 }}>
            The officer console highlights three seeded firms — a healthy business, a
            New-to-Credit applicant scored for the first time, and a case where
            cross-validation catches an inflated GST filing.
          </p>
          <button
            onClick={onLaunch}
            style={{
              padding: "12px 24px", borderRadius: 10, border: "none",
              background: "var(--series-1)", color: "#fff", fontWeight: 700, fontSize: 15,
            }}
          >
            Open the Officer Console →
          </button>
        </div>
      </Section>
    </div>
  );
}
