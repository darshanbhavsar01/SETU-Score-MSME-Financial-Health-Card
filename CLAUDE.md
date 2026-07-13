# CLAUDE.md — SETU Score POC (IDBI Innovate 2026, Track 3)

> **Single source of truth for this repository.** Claude Code must read this file fully before
> writing or modifying any code. When a decision is ambiguous, this file wins over
> assumptions. When this file is silent, prefer the simplest local-first option.

---

## 1. What we are building

**SETU Score** — an MSME Financial Health Card that makes credit-invisible (New-to-Credit /
New-to-Bank) enterprises assessable. It aggregates four alternate data sources — **GST returns,
UPI settlement flows, bank statements, EPFO payroll data** — and produces:

1. A composite **SETU Score (0–900)** built from six explainable sub-scores:
   Growth, Cash-flow Stability, Compliance Discipline, Liquidity, Customer Concentration, Leverage.
2. A **risk radar visualization** (six-axis) a credit officer can read in seconds.
3. **Cross-source fraud validation**: GST-declared turnover vs UPI inflows vs bank credits
   consistency checks that flag inflated filings.
4. A **working-capital limit recommendation** derived from verified cash flows.
5. A **LOS-ready JSON API** response (score + sub-scores + reason codes + limit + flags).

**Audience:** hackathon judges (bank credit/risk officers + tech evaluators).
**Deliverable:** a working POC demoable in a 3-minute video + GitHub repo.
**This is a POC, not a production system.** See §10 for what we deliberately do NOT build.

---

## 2. Non-negotiable guardrails

These override everything else in this file and any prompt given later.

1. **No fabricated results.** Never invent, hard-code, or massage metrics, scores, or
   evaluation numbers. Every number shown in the UI, README, or demo must be computed by
   code in this repo from data in this repo. If a metric is weak, report it honestly with
   a "fix path" note — do not hide it.
2. **Synthetic data must be labeled as synthetic** everywhere it appears (UI footer,
   README, API response metadata field `"data_source": "synthetic"`).
3. **No circular validation theater.** If we evaluate the scoring model, the evaluation
   must acknowledge that outcomes are synthetic. Frame it as "the pipeline rank-orders
   correctly on seeded personas", never as "90% accurate credit model."
4. **Deterministic by default.** All data generation and scoring must be seeded
   (`RANDOM_SEED = 42` in one config constant) so demo runs are reproducible.
5. **Budget cap: ₹300 total cloud spend.** The **submission requires a live deployed link**,
   so Cloud Run deployment is **mandatory, not optional** (§13) — but it must be architected
   to cost near-₹0 (min-instances=0, no per-request paid API calls in the default path).
   Anything *beyond* Cloud Run hosting (e.g. the optional Gemini narrative calls, §8) must be
   justified, metered, and capped with a dry-run/estimate check and a hard call counter.
6. **No secrets in the repo.** API keys only via `.env` (git-ignored). Provide `.env.example`.
7. **Keep local dev runnable in one command.** `docker compose up` (or `make demo`) must bring
   up the entire system on a laptop with **no cloud credentials required** — data, scoring,
   and ML all run locally. Cloud is only for hosting the public demo link, not for the app
   to function.

---

## 3. Architecture — local-first data & ML, cloud-hosted demo

**Why local-first**, stated honestly: at POC data volume, BigQuery and Firestore would
also cost ₹0 (both have generous free tiers) — cost is not the reason. The reason is
iteration speed and reproducibility: DuckDB and SQLite are embedded, in-process
databases with **no service account, no API enablement, no auth setup, and no network
round-trip**. That means the scoring loop can be rewritten and re-run dozens of times
during development with zero GCP dependency, and the entire system still runs offline
on a laptop with no cloud credentials at all — which also makes `docker compose up`
trivial and the demo resilient to any cloud hiccup on judging day.

```
┌────────────────────────────────────────────────────────────────┐
│  React + Vite frontend (Health Card UI)          localhost:5173│
└──────────────────────────┬─────────────────────────────────────┘
                           │ REST (JSON)
┌──────────────────────────▼─────────────────────────────────────┐
│  FastAPI backend (Python 3.11)                   localhost:8000│
│                                                                 │
│  /score        scoring engine (rules + local ML)                │
│  /validate     cross-source fraud checks                        │
│  /narrative    reason-code text (template-first, Gemini opt.)   │
│  /applicants   list & detail of demo MSMEs                      │
└──────────────────────────┬─────────────────────────────────────┘
                           │  (via repository/ interface — see below)
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   SQLite (app db)    DuckDB (analytics    scikit-learn /
   applicants,        over parquet:        XGBoost model
   scores, flags      txns, GST, UPI,      trained locally,
                      EPFO)                pickled in repo CI
```

**Technology decisions (fixed):**

| Concern | Use | Do NOT use |
|---|---|---|
| Analytics / feature engine | **DuckDB over Parquet files** | BigQuery, BQML |
| App storage | **SQLite** | Cloud SQL, Firestore |
| ML | **scikit-learn + XGBoost, trained locally** | Vertex AI training |
| Narratives / reason text | **Deterministic templates first**; optional Gemini API (AI Studio key, free tier) behind a flag | Vertex AI Gemini endpoint |
| Backend | **FastAPI + Uvicorn** | Cloud Functions |
| Frontend | **React + Vite + Recharts** (radar, trend charts) | Any paid charting lib |
| Packaging | **Docker, single `docker-compose.yml`** for local dev | Kubernetes, Terraform |
| Deployment (mandatory — submission needs a live link) | **One Cloud Run service** (§13) | Load balancers, VPCs, Pub/Sub, multi-service topologies |

**Data-access abstraction (build this even though it's a POC):** all reads/writes to
SQLite/DuckDB go through a thin `backend/app/repository/` interface (e.g.
`ApplicantRepository`, `ScoreRepository` with methods like `get_applicant()`,
`save_score()`) — never raw SQL scattered through route handlers or scoring code.
This costs almost nothing extra to build now and is what makes a future swap to
BigQuery/Firestore a bounded, contained change (re-implement the repository classes)
instead of a rewrite touching every module. Document this explicitly in the README
under "Swapping to managed cloud data services" so judges see the migration path is
a deliberate design choice, not an afterthought.

The AA/ULI/OCEN integration is **mocked**: a `connectors/` layer with the same interface a
real AA FIU flow would use, returning our synthetic payloads after a simulated consent step.
The README and pitch state clearly: *"Connectors are interface-compatible mocks; swapping in
real AA/GSTN endpoints changes only the connector layer."* That IS the integration-readiness
story — do not pretend it is live.

---

## 4. Repository layout

```
setu-score/
├── CLAUDE.md                  # this file
├── README.md                  # setup, demo script, honest limitations section
├── Makefile                   # make data / train / test / demo / deploy
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory + routes; serves built frontend static files
│   │   ├── config.py          # RANDOM_SEED, paths, flags, budget counters
│   │   ├── repository/        # DB-access interface (SQLite/DuckDB today; swap-point for BQ/Firestore later)
│   │   ├── connectors/        # mock AA/GST/UPI/EPFO fetchers (interface-first)
│   │   ├── features/          # DuckDB SQL + python feature builders
│   │   ├── scoring/
│   │   │   ├── subscores.py   # six sub-score calculators (pure functions)
│   │   │   ├── composite.py   # weighting → 0–900 + grade band
│   │   │   ├── model.py       # optional ML risk ranker (trained locally)
│   │   │   └── limits.py      # working-capital limit recommendation
│   │   ├── validation/
│   │   │   └── cross_checks.py# GST×UPI×bank consistency engine
│   │   ├── narrative/
│   │   │   ├── templates.py   # deterministic reason-code text (default)
│   │   │   └── gemini.py      # optional LLM polish, hard call-capped
│   │   └── schemas.py         # pydantic models = API contract
│   └── tests/                 # pytest; every module above has tests
├── datagen/
│   ├── personas.py            # persona definitions (§5)
│   ├── generate.py            # writes parquet + sqlite seed
│   └── validate_data.py       # sanity checks (no negative balances, etc.)
├── frontend/
│   └── src/
│       ├── pages/Console.tsx  # officer console: applicant queue
│       ├── pages/HealthCard.tsx # score dial, radar, trends, flags, limit
│       └── components/        # ScoreDial, RiskRadar, TrendChart, FlagBanner
├── model/
│   ├── train.py               # temporal split, saves model.pkl + metrics.json
│   └── metrics.json           # produced by train.py, NEVER hand-edited
├── Dockerfile                 # multi-stage: build frontend -> copy into FastAPI image
└── deploy/
    └── cloudrun.md            # gcloud deploy commands, instance limits, cost note (§13)
```

---

## 5. Synthetic data — personas and generators

Generate **60 MSMEs, 24 months of history each**, across 6 personas (10 each). Each MSME
gets: monthly GST returns (GSTR-3B-like: turnover, tax paid, filing date), daily UPI
settlement credits, bank statement transactions (credits/debits/EMIs/salary-out), and
monthly EPFO payroll (employee count, contribution paid, on-time flag).

| Persona | Story the data must tell | Expected outcome |
|---|---|---|
| `healthy_growth` | Steady 2–4% m/m turnover growth, on-time GST & EPFO, diversified UPI payers, comfortable liquidity | Score 700–850, limit approved |
| `seasonal_stable` | Strong festive-quarter peaks, flat annual trend, disciplined filings | Score 600–750, limit with seasonality note |
| `declining_stress` | Turnover −3–6% m/m for 8+ months, rising EMI/inflow ratio, delayed filings creeping in | Score 350–500, "monitor / decline" |
| `concentration_risk` | Healthy totals but 70%+ inflows from a single payer | Mid score, concentration flag drives it down |
| `ntc_thin_file` | Only 8 months of history, no loans ever, otherwise healthy | **Scoreable** (the inclusion story) — decent score, shorter-history caveat |
| `inflated_gst_fraud` | GST turnover ~3–5× actual UPI+bank inflows, round-number filings | Cross-validation **FRAUD FLAG**, score capped, "refer to fraud review" |

Generator rules:
- Pure Python + NumPy, seeded. Parameters (growth rates, noise, payer counts) live in
  `personas.py` as dataclasses — no magic numbers inside loops.
- Amounts in INR with realistic magnitudes (₹5L–₹5Cr annual turnover band).
- `validate_data.py` must run in CI/`make data` and assert invariants
  (e.g., UPI inflows ≤ bank credits for non-fraud personas; dates monotonic;
  fraud personas violate exactly the intended invariant and no others).

---

## 6. Scoring methodology (explainable core)

**Sub-scores (each 0–100, pure functions in `subscores.py`, unit-tested):**

1. **Growth** — trailing 6m vs prior 6m turnover trend (from GST + bank credits blended).
2. **Cash-flow Stability** — coefficient of variation of monthly net inflows; penalize
   negative-net months.
3. **Compliance Discipline** — GST filing punctuality %, EPFO on-time %, filing gaps.
4. **Liquidity** — average monthly closing-balance proxy vs monthly obligations (EMIs + rent-like debits).
5. **Customer Concentration** — Herfindahl index over UPI payer distribution (lower HHI = better).
6. **Leverage** — existing EMI outflows / average monthly inflows (FOIR-like).

**Composite:** weighted sum → scale to 300–900 (report as 0–900 scale with bands:
<450 High Risk, 450–600 Watch, 600–750 Good, >750 Excellent). Weights in `config.py`
with a one-line rationale comment each. Every sub-score returns
`(value, top_3_reason_codes)` where a reason code is a structured dict
(`code`, `direction`, `evidence` — e.g., `{"code": "GST_LATE_FILINGS", "direction": "negative", "evidence": "4 of last 12 GSTR-3B filed late"}`).

**Optional ML layer (`model.py`):** a small XGBoost ranker trained on the synthetic
population to predict the persona-implied risk ordering — used only to sanity-check that
features carry signal, shown in the demo as "model agreement" not as accuracy. Train with a
**temporal split** (first 18 months features → last 6 months outcome proxy). `train.py`
writes `metrics.json`; the UI/README may only display numbers read from that file.

**Limit recommendation (`limits.py`):** `limit = clamp(k × average_verified_monthly_net_inflow × stability_multiplier, persona-agnostic caps)` — verified inflow means the *minimum* of GST-implied and bank-observed inflow (conservative by construction). Show the formula in the UI tooltip; judges love visible prudence.

**Cross-validation engine (`cross_checks.py`):**
- `GST_VS_BANK`: declared GST turnover vs bank credit totals per quarter (tolerance band ±25%).
- `GST_VS_UPI`: declared turnover vs UPI settlement volume where UPI-dominant.
- `ROUND_NUMBER`: suspicious round-figure filing pattern detector.
- Output: `consistency_score (0–100)` + list of triggered flags with evidence.
  Any hard flag caps composite at 449 and sets `recommendation: "REFER_FRAUD_REVIEW"`.

---

## 7. API contract (freeze early, test against it)

`GET /applicants` → list (id, name, sector, persona hidden in prod-mode flag, score if computed)
`POST /score/{applicant_id}` → runs full pipeline, returns:

```json
{
  "applicant_id": "MSME-0042",
  "setu_score": 712,
  "band": "GOOD",
  "sub_scores": {"growth": 74, "stability": 68, "compliance": 91,
                 "liquidity": 63, "concentration": 55, "leverage": 70},
  "reason_codes": [ {"code": "...", "direction": "...", "evidence": "..."} ],
  "cross_validation": {"consistency_score": 94, "flags": []},
  "limit_recommendation": {"amount_inr": 800000, "tenor_months": 12, "basis": "..."},
  "recommendation": "APPROVE_WITH_LIMIT",
  "data_source": "synthetic",
  "scored_at": "..."
}
```

Frontend renders exclusively from this payload. A saved example response lives in
`backend/tests/golden/` and a contract test asserts the schema never drifts silently.

---

## 8. Gemini usage (optional, budget-capped)

- Default narrative text comes from `templates.py` (deterministic). The demo must be fully
  presentable with templates alone.
- If `GEMINI_API_KEY` is set AND `ENABLE_LLM_NARRATIVE=true`, `gemini.py` may polish the
  officer-facing summary paragraph (1 call per applicant, `gemini-2.0-flash`-class model
  via AI Studio).
- Hard limits in code: max **50 calls per process lifetime** (counter persisted in SQLite),
  max 1,000 output tokens/call, and a startup log line printing estimated worst-case cost.
  At free-tier AI Studio rates this is ₹0; even on paid rates it stays under ₹50 — well
  inside the ₹300 cap. If the counter is exhausted, silently fall back to templates.
- Never send raw transaction tables to the LLM — only the computed sub-scores, flags, and
  reason codes (aggregates, no synthetic PII).

---

## 9. Testing & quality bar

- `pytest` for: every sub-score function (hand-computed fixtures), cross-check engine
  (each fraud persona triggers exactly its intended flag; healthy personas trigger none),
  limit formula, API contract (golden response), data validators.
- `make test` runs datagen validation + pytest; must pass before any demo/deploy step.
- One **end-to-end smoke test**: generate data → score all 60 → assert persona score bands
  from §5 hold (this is our honest "does the system rank-order correctly" proof).
- Frontend: keep it simple — typecheck + a render test for HealthCard with the golden payload.
- Code style: ruff + black defaults; no clever abstractions; small pure functions.
- **Post-deploy smoke test:** after `make deploy` (§13), curl the live Cloud Run URL's
  `/applicants` and one `/score/{id}` and confirm they match the local golden response
  shape — the POC isn't done until the public link is verified working, not just the code.

---

## 10. Explicitly OUT of scope (do not build)

- Real AA/GSTN/EPFO/OCEN API integration, OAuth, or consent infrastructure (mock only).
- Authentication/authorization, multi-tenancy, audit logging beyond simple request logs.
- Streaming (Pub/Sub/Kafka), schedulers, retraining pipelines, model registries.
- BigQuery/BQML, Vertex AI, Terraform, Kubernetes, load balancers, VPCs, CI/CD beyond a
  basic GitHub Action running `make test`. (**Cloud Run itself is in scope and required** —
  see §13 — this line excludes everything *around* it, not the deployment itself.)
- Mobile app, vernacular report PDFs (roadmap slide items, not POC).
- Any attempt to claim real-world accuracy numbers.

---

## 11. Demo script the build must serve (3-minute video)

1. Officer console: queue of applicants, three highlighted — `ntc_thin_file`,
   `healthy_growth`, `inflated_gst_fraud`.
2. Score the NTC firm live: consent-mock animation → card renders in seconds →
   "no bureau history, still scoreable" caption. Radar + reason codes on screen.
3. Score the fraud firm: cross-validation banner fires — GST ₹2.1Cr vs verified inflows
   ₹0.6Cr → score capped, REFER_FRAUD_REVIEW.
4. Show limit recommendation + the conservative "min(GST, bank)" basis tooltip.
5. End on the raw JSON API response in a terminal → "LOS-integration ready."

Every feature that does not serve one of these five beats is a candidate for cutting.

---

## 13. Deployment on Cloud Run (mandatory — the submission needs a live link)

This is required, not optional — same pattern as VAAYU and VARUNA: one container, one
public URL, near-₹0 running cost.

**Design constraints that make local storage safe in a scaled/stateless environment:**

1. **Bake the synthetic dataset into the image as read-only files** (parquet + a
   pre-seeded SQLite file), generated at build time via `make data` in the Dockerfile's
   build stage. The running container never needs to write applicant/GST/UPI/bank data —
   it only reads.
2. **Scoring is a pure computation per request** (`POST /score/{id}` computes fresh from
   the read-only data every time) — no dependency on write-then-read state, so it is safe
   even if Cloud Run spins up multiple instances.
3. **Cap the service at `max-instances=1` for the demo** anyway, purely to keep behaviour
   simple and predictable for judges (no risk of any instance divergence at all), and set
   `min-instances=0` so it scales to zero and costs nothing between visits.
4. **The optional Gemini call-counter (§8)** persists to the same read-only-mounted SQLite
   file for local dev; on Cloud Run, default `ENABLE_LLM_NARRATIVE=false` so the deployed
   demo runs entirely on templates and needs no API key at all. This keeps the public link
   at guaranteed ₹0 marginal cost; you can flip the flag on temporarily for a specific
   judge walkthrough if you want the LLM narrative shown live.
5. **Single container serves both tiers:** `Dockerfile` is multi-stage — stage 1 builds the
   React frontend (`npm run build`), stage 2 copies the static build output into the FastAPI
   image, and FastAPI serves it directly (`StaticFiles` mount) alongside the `/score`,
   `/validate`, `/applicants` API routes. One image, one Cloud Run service, one URL for
   both the UI and the API — no CORS setup, no separate frontend hosting needed.

**Deploy commands (documented in `deploy/cloudrun.md`, also runnable via `make deploy`):**

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/setu-score
gcloud run deploy setu-score \
  --image gcr.io/PROJECT_ID/setu-score \
  --region asia-south1 \
  --min-instances=0 --max-instances=1 \
  --memory=512Mi --cpu=1 \
  --allow-unauthenticated
```

**Expected cost:** Cloud Run's always-free tier covers 2 million requests and 360,000
GB-seconds/month; a hackathon demo (judges clicking through a handful of times) stays
inside that free tier — realistically **₹0**, comfortably under the ₹300 cap even
accounting for build/storage overhead. Check the GCP billing dashboard after the first
deploy and note the actual figure in the README for honesty.

---

## 14. Build order (work in this sequence, commit per step)

1. `datagen/` + validators (`make data` green).
2. `repository/` interface + SQLite/DuckDB implementations (thin, but real from day one).
3. `features/` + `subscores.py` + `composite.py` with tests.
4. `cross_checks.py` + `limits.py` with tests.
5. FastAPI routes + golden contract test (`make test` green).
6. Frontend Console + HealthCard against the golden payload, then live API.
7. `model/train.py` + metrics.json (optional layer — skip if time-boxed out).
8. Narrative templates; Gemini flag last.
9. Docker compose for local dev, README (including an honest **Limitations** section).
10. **`Dockerfile` (multi-stage) + Cloud Run deploy (§13) — required, not optional.**
    Verify the live URL works end-to-end before calling the POC done. Check GCP billing
    after first deploy and record the actual cost in the README.


## Git Commit Guidelines
- Do not include AI attribution or co-author lines in commit messages.