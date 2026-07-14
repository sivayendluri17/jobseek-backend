"""JSearch adapter (via RapidAPI).

JSearch aggregates Google-for-Jobs results across many boards (including
staffing-firm postings that appear on Dice/Indeed), returning an
employment_type hint plus the description text we parse for C2C vs W2.

Requires env var RAPIDAPI_KEY. Configure the searches in companies.yaml under
the 'jsearch' source as a list of query strings, e.g.:

  jsearch:
    - "java developer c2c"
    - "business analyst contract"
    - "python developer w2"

Each query is one API call. JSearch's free tier is limited, so keep the query
list focused and let the cron cadence (not query count) drive freshness.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from ..base import Adapter, RawJob

RAPIDAPI_HOST = "jsearch.p.rapidapi.com"
REMOTE_HINTS = ("remote", "anywhere", "work from home", "wfh")


def _parse_dt(value) -> datetime:
    """JSearch gives job_posted_at_timestamp (unix) or ISO strings."""
    if value is None:
        return datetime.now(timezone.utc)
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


class JSearchAdapter(Adapter):
    source = "jsearch"

    def url_for(self, query: str) -> str:
        # date_posted=week keeps results fresh; num_pages=1 conserves quota.
        from urllib.parse import quote
        return (
            f"https://{RAPIDAPI_HOST}/search?query={quote(query)}"
            f"&page=1&num_pages=1&date_posted=week&country=us"
        )

    async def fetch(self, client: httpx.AsyncClient, query: str) -> list[RawJob]:
        key = os.environ.get("RAPIDAPI_KEY", "")
        if not key:
            print("[jsearch] RAPIDAPI_KEY not set, skipping")
            return []
        try:
            resp = await client.get(
                self.url_for(query),
                headers={
                    "x-rapidapi-key": key,
                    "x-rapidapi-host": RAPIDAPI_HOST,
                },
                timeout=25,
            )
            resp.raise_for_status()
            return self.parse(query, resp.json())
        except Exception as exc:  # noqa: BLE001
            print(f"[jsearch] {query!r}: skipped ({type(exc).__name__})")
            return []

    def parse(self, query: str, payload) -> list[RawJob]:
        jobs: list[RawJob] = []
        for j in payload.get("data", []) or []:
            title = j.get("job_title", "") or ""
            company = j.get("employer_name", "") or "Unknown"
            city = j.get("job_city") or ""
            state = j.get("job_state") or ""
            loc = ", ".join(p for p in (city, state) if p) or (
                "Remote" if j.get("job_is_remote") else None
            )
            url = j.get("job_apply_link") or j.get("job_google_link") or ""
            ext = j.get("job_id") or url
            posted = _parse_dt(
                j.get("job_posted_at_timestamp")
                or j.get("job_posted_at_datetime_utc")
            )
            jobs.append(
                RawJob(
                    source=self.source,
                    company=company,
                    external_id=str(ext),
                    title=title,
                    url=url,
                    posted_at=posted,
                    location=loc,
                    department=None,
                    raw_employment=j.get("job_employment_type"),
                    description=(j.get("job_description") or "")[:4000],
                )
            )
        return jobs
