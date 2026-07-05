"""Lever adapter.

Public endpoint (no key, no login):
  https://api.lever.co/v0/postings/{slug}?mode=json
Returns a JSON array of postings, each with:
  {"id", "text" (title), "createdAt" (epoch ms), "hostedUrl",
   "categories": {"location", "team", "commitment"}, "workplaceType"}
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..base import Adapter, RawJob

REMOTE_HINTS = ("remote", "anywhere", "distributed")


class LeverAdapter(Adapter):
    source = "lever"

    def url_for(self, slug: str) -> str:
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"

    def parse(self, slug: str, payload) -> list[RawJob]:
        jobs: list[RawJob] = []
        for p in payload:
            cats = p.get("categories") or {}
            loc = cats.get("location")
            workplace = (p.get("workplaceType") or "").lower()
            remote_flag = workplace == "remote" or bool(
                loc and any(h in loc.lower() for h in REMOTE_HINTS)
            )
            created_ms = p.get("createdAt") or 0
            jobs.append(
                RawJob(
                    source=self.source,
                    company=slug,
                    external_id=str(p.get("id")),
                    title=p.get("text", ""),
                    url=p.get("hostedUrl", ""),
                    posted_at=datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc),
                    location=loc,
                    department=cats.get("team"),
                )
            )
        return jobs
