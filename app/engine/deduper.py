"""Deduplicator — the same role can appear twice (two sources, reposts).

Keep one copy per stable id, preferring the most recently posted."""
from __future__ import annotations

from ..models.job import Job


def dedupe(jobs: list[Job]) -> list[Job]:
    best: dict[str, Job] = {}
    for job in jobs:
        existing = best.get(job.id)
        if existing is None or job.posted_at > existing.posted_at:
            best[job.id] = job
    return list(best.values())
