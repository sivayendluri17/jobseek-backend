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


class EmploymentType(str, enum.Enum):
    """How the role is engaged — the consultancy's primary lens."""

    FULLTIME = "fulltime"   # W2 permanent / direct-hire
    C2C = "c2c"             # Corp-to-Corp contract
    W2_CONTRACT = "w2"      # W2 contract (contract but not corp-to-corp)
    CONTRACT = "contract"   # contract, C2C-vs-W2 unspecified in the posting


class Job(BaseModel):
    """A normalized job listing, ready to store and serve."""

    id: str                       # stable hash — same role never stored twice
    source: str                   # "greenhouse", "lever", "jsearch", ...
    company: str
    title: str
    location: str | None = None
    remote: bool = False
    url: str
    posted_at: datetime
    freshness_bucket: FreshnessBucket = FreshnessBucket.OLDER
    department: str | None = None
    employment_type: EmploymentType = EmploymentType.FULLTIME
