# Deploying SETU Score to Cloud Run

Mandatory per the brief (CLAUDE.md §13) — the submission needs a live public link.
Architected for near-₹0 cost: `min-instances=0` (scales to zero between visits),
`max-instances=1` (keeps behaviour simple/predictable, no instance divergence risk),
no per-request paid API calls in the default path (`ENABLE_LLM_NARRATIVE=false`).

## Prerequisites

- `gcloud` CLI authenticated (`gcloud auth login`) against the target project.
- These APIs enabled on the project: `run.googleapis.com`, `cloudbuild.googleapis.com`,
  `artifactregistry.googleapis.com` (or `containerregistry.googleapis.com`).
- `GCP_PROJECT_ID` / `GCP_REGION` set in `.env` (used by `make deploy`; the raw
  `gcloud` commands below take them as shell variables instead).

## Deploy commands

```bash
export PROJECT_ID=<your-project-id>
export REGION=asia-south1

# 1. Build the multi-stage image via Cloud Build (no local Docker needed).
gcloud builds submit --tag gcr.io/$PROJECT_ID/setu-score

# 2. Deploy to Cloud Run.
gcloud run deploy setu-score \
  --image gcr.io/$PROJECT_ID/setu-score \
  --region $REGION \
  --min-instances=0 --max-instances=1 \
  --memory=512Mi --cpu=1 \
  --set-env-vars SETU_APP_DB=/tmp/setu-app.db,ENABLE_LLM_NARRATIVE=false \
  --allow-unauthenticated
```

`SETU_APP_DB=/tmp/setu-app.db` points the writable score/flag cache and the Gemini
call-counter at Cloud Run's ephemeral `/tmp`, since the baked `data/` files inside
the image are read-only application data, not a place the running container should
write to (§13 constraint #1). Scoring itself is a pure per-request computation, so
this cache is a convenience, never a correctness dependency — losing it on a cold
start just means the next `/score/{id}` call recomputes instead of reading cache.

To temporarily show the live Gemini narrative polish during a judge walkthrough,
redeploy (or `gcloud run services update`) with:

```bash
--set-env-vars ENABLE_LLM_NARRATIVE=true,GEMINI_API_KEY=<key>,GEMINI_API_KEY_FALLBACK=<key2>
```

then flip it back to `false` afterward to keep the public link at guaranteed ₹0
marginal cost.

## Post-deploy smoke test (§9 — not done until this passes)

```bash
export URL=$(gcloud run services describe setu-score --region $REGION --format='value(status.url)')
curl -s "$URL/health"
curl -s "$URL/applicants" | head -c 300
curl -s -X POST "$URL/score/MSME-0001" | head -c 300
```

Confirm the shapes match the local golden response
(`backend/tests/golden/score_healthy_growth.json`) before calling the deploy done.

## Cost

Cloud Run's always-free tier covers 2M requests and 360,000 GB-seconds/month. A
hackathon demo (judges clicking through a handful of times) stays inside that free
tier. Check **GCP Console → Billing → Reports** after the first deploy for the
actual figure.

## Deployed

- **URL:** https://setu-score-229692962627.asia-south1.run.app
- **Project / region:** `main-aura-398409` / `asia-south1`
- **Revision:** `setu-score-00001-k5k`
- **Config:** `min-instances=0`, `max-instances=1`, `memory=512Mi`, `cpu=1`,
  `ENABLE_LLM_NARRATIVE=false` (public link runs on templates, needs no key)
- **Post-deploy smoke test:** `GET /health` → 60 applicants; `POST /score/MSME-0001`
  decoded and diffed byte-for-byte (excluding `scored_at`) against
  `backend/tests/golden/score_healthy_growth.json` — **exact match**. `GET /` serves
  the built React SPA (200, correct title). 404s verified for unknown/unscored
  applicant IDs.
- **Cost:** deployed with only smoke-test traffic against `min-instances=0`, well
  inside Cloud Run's always-free tier (2M requests, 360,000 GB-seconds/month) —
  expected ₹0. Cloud Billing reports lag real-time usage by several hours; confirm
  the settled figure in **GCP Console → Billing → Reports** filtered to this
  project/service before quoting an exact number in the pitch deck.
