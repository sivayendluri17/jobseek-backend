"""Runner — orchestrates one full sweep.

  load company list -> fetch all (concurrently) -> normalize -> dedupe
  -> bucket by freshness -> store in the database.

Run directly for a one-off sweep:  python -m app.engine.runner
"""
from __future__ import annotations

import asyncio

import httpx

from ..config import load_companies
from ..db import store
from ..models.job import Job
from .adapters.greenhouse import GreenhouseAdapter
from .adapters.lever import LeverAdapter
from .adapters.jsearch import JSearchAdapter
from .base import RawJob
from .bucketer import bucket_all
from .deduper import dedupe
from .normalizer import normalize_all

ADAPTERS = {
    "greenhouse": GreenhouseAdapter(),
    "lever": LeverAdapter(),
    "jsearch": JSearchAdapter(),
}


async def _fetch_all(companies: dict[str, list[str]]) -> list[RawJob]:
    raws: list[RawJob] = []
    async with httpx.AsyncClient(headers={"User-Agent": "JobSeek/0.1"}) as client:
        tasks = []
        for source, slugs in companies.items():
            adapter = ADAPTERS.get(source)
            if not adapter:
                print(f"no adapter for source '{source}', skipping")
                continue
            for slug in slugs:
                tasks.append(adapter.fetch(client, slug))
        for result in await asyncio.gather(*tasks):
            raws.extend(result)
    return raws


async def run_sweep() -> dict:
    """Run one sweep and return a small summary."""
    store.init_db()
    companies = load_companies()

    raws = await _fetch_all(companies)
    jobs: list[Job] = normalize_all(raws)
    jobs = dedupe(jobs)
    jobs = bucket_all(jobs)
    written = store.upsert_jobs(jobs)

    summary = {
        "fetched": len(raws),
        "after_dedupe": len(jobs),
        "written": written,
        "by_bucket": store.counts_by_bucket(),
    }
    print("sweep complete:", summary)
    return summary


if __name__ == "__main__":
    asyncio.run(run_sweep())
