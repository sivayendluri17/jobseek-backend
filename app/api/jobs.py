"""API routes — what the Next.js frontend calls."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..config import load_companies
from ..db import store
from ..engine.runner import run_sweep
from ..models.job import Job

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/jobs", response_model=list[Job])
def list_jobs(
    freshness: Literal["24h", "48h", "72h"] | None = None,
    remote: bool | None = None,
    company: str | None = None,
    search: str | None = None,
    category: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[Job]:
    return store.query_jobs(
        freshness=freshness, remote=remote, company=company,
        search=search, category=category, limit=limit,
    )


@router.get("/jobs/categories")
def job_categories() -> list[dict]:
    """Tech categories with live counts, for the filter chips."""
    from ..models.categories import CATEGORY_LABELS
    counts = store.counts_by_category()
    order = ["swe", "backend", "frontend", "fullstack", "mobile", "data-ml",
             "cloud-devops", "security", "qa", "systems", "product-ba",
             "leadership", "intern"]
    return [
        {"key": k, "label": CATEGORY_LABELS[k], "count": counts.get(k, 0)}
        for k in order if counts.get(k, 0) > 0
    ]


@router.get("/jobs/suggest")
def suggest(q: str = Query(..., min_length=1, max_length=80),
            limit: int = Query(8, ge=1, le=15)) -> list[dict]:
    """Type-ahead suggestions for the search box."""
    return store.suggest_jobs(q, limit)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/companies")
def companies() -> dict:
    return load_companies()


@router.get("/stats")
def stats() -> dict:
    return {"by_bucket": store.counts_by_bucket()}


@router.post("/engine/run")
async def trigger_sweep() -> dict:
    """Manually trigger a sweep (useful for testing and first load)."""
    return await run_sweep()
