# SETU Score — multi-stage build (CLAUDE.md §13).
#
# Stage 1 builds the React frontend. Stage 2 installs the slim runtime deps, bakes
# the deterministic synthetic dataset into the image at BUILD time (read-only at
# runtime — the container never writes applicant/GST/UPI/bank data), copies in the
# built frontend, and serves both the API and the static UI from one process on one
# port. One image, one Cloud Run service, one URL for both tiers — no CORS, no
# separate frontend hosting.

# ---------- Stage 1: frontend ----------
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: backend + baked data + static frontend ----------
FROM python:3.11-slim AS final
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# `make` so the data-baking step below can literally run `make data`, matching the
# same target a developer runs locally (§13 constraint #1).
RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY Makefile .
COPY backend/__init__.py backend/__init__.py
COPY backend/app backend/app
COPY datagen datagen

# Bake the deterministic (RANDOM_SEED=42) synthetic dataset into the image now, at
# build time. The running container only ever READS data/ — safe under multiple
# Cloud Run instances even though max-instances is capped at 1 for the demo (§13).
RUN make data

# Same-origin static UI (§13) — built in stage 1, copied in as read-only files.
COPY --from=frontend-build /app/frontend/dist frontend/dist

# Cloud Run injects $PORT (defaults to 8080 here for `docker run` / compose too).
ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=3)" || exit 1

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
