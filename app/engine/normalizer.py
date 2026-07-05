"""Normalizer — turn RawJobs from any source into one common Job shape."""
from __future__ import annotations

import hashlib

from ..models.job import Job
from .base import RawJob

REMOTE_HINTS = ("remote", "anywhere", "distributed", "work from home")


def _stable_id(raw: RawJob) -> str:
    """A hash that identifies the same role across sweeps and sources."""
    key = f"{raw.company}|{raw.title}|{raw.location or ''}".lower()
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _is_remote(raw: RawJob) -> bool:
    haystack = f"{raw.location or ''} {raw.title}".lower()
    return any(hint in haystack for hint in REMOTE_HINTS)


def normalize(raw: RawJob) -> Job:
    return Job(
        id=_stable_id(raw),
        source=raw.source,
        company=raw.company,
        title=raw.title.strip(),
        location=raw.location,
        remote=_is_remote(raw),
        url=raw.url,
        posted_at=raw.posted_at,
        department=raw.department,
    )


def normalize_all(raws: list[RawJob]) -> list[Job]:
    return [normalize(r) for r in raws]
