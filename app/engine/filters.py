"""US location filter.

Keeps only jobs that look US-based, so listings from London, Bangalore, etc.
don't show up. The rule is conservative: a job is DROPPED only when its location
clearly names a non-US place AND gives no US signal. Anything US, ambiguous, or
plain "Remote" is kept, so real US roles are never lost.

Edit the lists below to tune it. Locations from job boards are messy, so this is
sensible rules, not perfection — extend NON_US_MARKERS if you spot leaks.
"""
from __future__ import annotations

import re

from ..models.job import Job

# US state abbreviations (+ DC) — matched as standalone tokens like "CA", "NY".
US_STATE_ABBR = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

# US country tokens (matched as standalone tokens).
US_COUNTRY_TOKENS = {"US", "USA"}

# US signals matched as plain substrings (lowercased).
US_TEXT = ("united states", "u.s.", "u.s.a", "remote - us", "remote (us)", "us-remote")

# Full state names as substrings (lowercased).
US_STATE_NAMES = (
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
)

# Clear non-US signals (countries + major cities/regions), lowercased substrings.
NON_US_MARKERS = (
    "united kingdom", "uk", "england", "scotland", "london", "manchester",
    "canada", "toronto", "vancouver", "montreal", "ontario",
    "india", "bangalore", "bengaluru", "hyderabad", "mumbai", "pune", "delhi",
    "chennai", "gurgaon", "noida", "kolkata",
    "germany", "berlin", "munich", "hamburg",
    "france", "paris", "ireland", "dublin",
    "netherlands", "amsterdam", "spain", "madrid", "barcelona",
    "poland", "warsaw", "krakow", "wroclaw",
    "brazil", "sao paulo", "australia", "sydney", "melbourne",
    "singapore", "japan", "tokyo", "china", "shanghai", "beijing",
    "israel", "tel aviv", "mexico", "portugal", "lisbon", "porto",
    "sweden", "stockholm", "switzerland", "zurich", "geneva",
    "italy", "milan", "rome", "romania", "bucharest",
    "argentina", "colombia", "bogota", "philippines", "manila",
    "new zealand", "south africa", "cape town", "nigeria", "lagos",
    "dubai", "uae", "saudi", "egypt", "kenya", "vietnam", "hanoi",
    "emea", "apac", "latam", "united arab emirates",
)

_TOKEN_SPLIT = re.compile(r"[\s,/|•·()\[\]]+")


def _tokens(location: str) -> set[str]:
    return {t.strip().upper() for t in _TOKEN_SPLIT.split(location) if t.strip()}


def is_us(job: Job) -> bool:
    """True if the job should be kept (US-based or ambiguous)."""
    loc = job.location or ""
    if not loc:
        return True  # unknown location — keep rather than risk dropping a US role

    low = loc.lower()
    toks = _tokens(loc)

    us_hit = (
        any(t in US_STATE_ABBR for t in toks)
        or any(t in US_COUNTRY_TOKENS for t in toks)
        or any(m in low for m in US_TEXT)
        or any(s in low for s in US_STATE_NAMES)
    )
    non_us_hit = any(m in low for m in NON_US_MARKERS)

    # Drop only when clearly non-US with no US signal.
    if non_us_hit and not us_hit:
        return False
    return True


def filter_us(jobs: list[Job]) -> list[Job]:
    return [j for j in jobs if is_us(j)]