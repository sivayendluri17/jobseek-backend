"""Data models for JobSeek jobs."""
from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel


class FreshnessBucket(str, enum.Enum):
    """How recently a job was posted."""

    NEW_24H = "24h"
    NEW_48H = "48h"
    NEW_72H = "72h"
    OLDER = "older"


class Job(BaseModel):
    """A normalized job listing, ready to store and serve."""

    id: str
    source: str
    company: str
    title: str
    location: str | None = None
    remote: bool = False
    url: str
    posted_at: datetime
    freshness_bucket: FreshnessBucket = FreshnessBucket.OLDER
    department: str | None = None