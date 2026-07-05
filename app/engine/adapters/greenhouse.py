"""Greenhouse adapter.

Public endpoint (no key, no login):
  https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
Returns {"jobs": [{"id", "title", "updated_at", "absolute_url", "location": {"name"}}]}
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..base import Adapter, RawJob

REMOTE_HINTS = ("remote", "anywhere", "distributed")


def _parse_dt(value: str) -> datetime:
    # Greenhouse timestamps look like "2024-05-01T12:00:00-04:00"
    dt = datetime.fromisoformat(value)
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class GreenhouseAdapter(Adapter):
    source = "greenhouse"

    def url_for(self, slug: str) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"

    def parse(self, slug: str, payload) -> list[RawJob]:
        jobs: list[RawJob] = []
        for j in payload.get("jobs", []):
            loc = (j.get("location") or {}).get("name")
            title = j.get("title", "")
            remote_flag = bool(loc and any(h in loc.lower() for h in REMOTE_HINTS))
            jobs.append(
                RawJob(
                    source=self.source,
                    company=slug,
                    external_id=str(j.get("id")),
                    title=title,
                    url=j.get("absolute_url", ""),
                    posted_at=_parse_dt(j["updated_at"]),
                    location=loc,
                    department=None,
                )
            )
        return jobs
