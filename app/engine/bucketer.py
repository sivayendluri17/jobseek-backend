"""Freshness bucketer — label each job 24h / 48h / 72h / older."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models.job import FreshnessBucket, Job


def bucket_for(posted_at: datetime, now: datetime | None = None) -> FreshnessBucket:
    now = now or datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    age_hours = (now - posted_at).total_seconds() / 3600
    if age_hours <= 24:
        return FreshnessBucket.NEW_24H
    if age_hours <= 48:
        return FreshnessBucket.NEW_48H
    if age_hours <= 72:
        return FreshnessBucket.NEW_72H
    return FreshnessBucket.OLDER


def bucket_all(jobs: list[Job], now: datetime | None = None) -> list[Job]:
    now = now or datetime.now(timezone.utc)
    for job in jobs:
        job.freshness_bucket = bucket_for(job.posted_at, now)
    return jobs
