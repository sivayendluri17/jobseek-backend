"""Base classes for source adapters.

Each adapter knows how to talk to ONE job source (Greenhouse, Lever, ...).
`fetch` does the network call; `parse` turns a raw payload into RawJobs and is
kept separate so it can be unit-tested without hitting the network.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx


@dataclass
class RawJob:
    """A job as pulled from a source, before normalization."""

    source: str
    company: str
    external_id: str
    title: str
    url: str
    posted_at: datetime
    location: str | None = None
    department: str | None = None
    raw_employment: str | None = None   # aggregator's own type hint
    description: str | None = None       # for C2C/W2 text parsing


class Adapter(ABC):
    """A source adapter. Subclasses implement url_for() and parse()."""

    source: str = "base"

    @abstractmethod
    def url_for(self, slug: str) -> str:
        """The public endpoint for a given company slug."""

    @abstractmethod
    def parse(self, slug: str, payload) -> list[RawJob]:
        """Turn a raw JSON payload into RawJobs. Pure, testable."""

    async def fetch(self, client: httpx.AsyncClient, slug: str) -> list[RawJob]:
        """Fetch and parse one company's jobs. Never raises — returns [] on failure."""
        try:
            resp = await client.get(self.url_for(slug), timeout=15)
            resp.raise_for_status()
            return self.parse(slug, resp.json())
        except Exception as exc:  # noqa: BLE001 - one bad slug must not stop the sweep
            print(f"[{self.source}] {slug}: skipped ({type(exc).__name__})")
            return []
