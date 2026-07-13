"""FastAPI application (CLAUDE.md §7, §13).

One service exposes the JSON API and (when built) serves the React frontend from the
same origin — no CORS needed in production, one Cloud Run URL for both tiers. CORS is
enabled permissively only to ease local split-port dev (Vite :5173 → API :8000).

Routes:
  GET  /health              liveness + population size
  GET  /applicants          officer queue (+ score/band if already computed)
  GET  /applicants/{id}     single applicant summary
  POST /score/{id}          run the full pipeline, persist, return ScoreResponse
  GET  /score/{id}          return a previously computed score (404 if none)
  POST /validate/{id}       cross-source consistency check only
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import DATA_SOURCE_LABEL, REPO_ROOT, settings
from backend.app.features import build_features
from backend.app.repository import Repositories, get_repositories
from backend.app.schemas import (
    ApplicantSummary,
    CrossValidationModel,
    HealthResponse,
    ScoreResponse,
    TrendPoint,
)
from backend.app.scoring.pipeline import score_applicant
from backend.app.validation.cross_checks import cross_validate

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


def get_repos() -> Repositories:
    # Overridden in tests; in the app it's bound to the singleton in create_app().
    raise RuntimeError("repositories not configured")


def create_app(repos: Repositories | None = None) -> FastAPI:
    app = FastAPI(title="SETU Score API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _repos = repos or get_repositories()
    app.dependency_overrides[get_repos] = lambda: _repos

    @app.get("/health", response_model=HealthResponse)
    def health(r: Repositories = Depends(get_repos)) -> HealthResponse:
        return HealthResponse(
            status="ok",
            applicants=len(r.applicants.list_applicants()),
            data_source=DATA_SOURCE_LABEL,
        )

    @app.get("/applicants", response_model=list[ApplicantSummary])
    def list_applicants(r: Repositories = Depends(get_repos)) -> list[ApplicantSummary]:
        cached = {s.applicant_id: s for s in r.scores.list_scored()}
        out: list[ApplicantSummary] = []
        for a in r.applicants.list_applicants():
            s = cached.get(a.id)
            out.append(
                ApplicantSummary(
                    id=a.id,
                    name=a.name,
                    sector=a.sector,
                    history_months=a.history_months,
                    persona=a.persona if settings.expose_persona else None,
                    setu_score=s.setu_score if s else None,
                    band=s.band if s else None,
                    recommendation=s.recommendation if s else None,
                )
            )
        return out

    @app.get("/applicants/{applicant_id}", response_model=ApplicantSummary)
    def get_applicant(applicant_id: str, r: Repositories = Depends(get_repos)) -> ApplicantSummary:
        a = r.applicants.get_applicant(applicant_id)
        if a is None:
            raise HTTPException(status_code=404, detail=f"Unknown applicant {applicant_id}")
        s = r.scores.get_score(applicant_id)
        return ApplicantSummary(
            id=a.id,
            name=a.name,
            sector=a.sector,
            history_months=a.history_months,
            persona=a.persona if settings.expose_persona else None,
            setu_score=s["setu_score"] if s else None,
            band=s["band"] if s else None,
            recommendation=s["recommendation"] if s else None,
        )

    @app.post("/score/{applicant_id}", response_model=ScoreResponse)
    def score(applicant_id: str, r: Repositories = Depends(get_repos)) -> ScoreResponse:
        if not r.applicants.exists(applicant_id):
            raise HTTPException(status_code=404, detail=f"Unknown applicant {applicant_id}")
        payload = score_applicant(applicant_id, r)
        r.scores.save_score(applicant_id, payload, flags=payload["cross_validation"]["flags"])
        return ScoreResponse(**payload)

    @app.get("/score/{applicant_id}", response_model=ScoreResponse)
    def get_score(applicant_id: str, r: Repositories = Depends(get_repos)) -> ScoreResponse:
        payload = r.scores.get_score(applicant_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"{applicant_id} not scored yet")
        return ScoreResponse(**payload)

    @app.get("/applicants/{applicant_id}/trend", response_model=list[TrendPoint])
    def trend(applicant_id: str, r: Repositories = Depends(get_repos)) -> list[TrendPoint]:
        if not r.applicants.exists(applicant_id):
            raise HTTPException(status_code=404, detail=f"Unknown applicant {applicant_id}")
        f = build_features(applicant_id, r.analytics)
        return [
            TrendPoint(
                month=f.months[i],
                gst_declared=float(f.gst_declared[i]),
                bank_credit=float(f.bank_credit[i]),
                upi_total=float(f.upi_total[i]),
                net_inflow=float(f.net_inflow[i]),
            )
            for i in range(f.n_months)
        ]

    @app.post("/validate/{applicant_id}", response_model=CrossValidationModel)
    def validate(applicant_id: str, r: Repositories = Depends(get_repos)) -> CrossValidationModel:
        if not r.applicants.exists(applicant_id):
            raise HTTPException(status_code=404, detail=f"Unknown applicant {applicant_id}")
        f = build_features(applicant_id, r.analytics)
        return CrossValidationModel(**cross_validate(f).as_dict())

    # Serve the built frontend from the same origin, if present (§13). Mounted last so
    # the API routes above take precedence; harmless no-op until step 6 builds it.
    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    return app


app = create_app()
