"""PostgreSQL store for jobs (AWS RDS).

Same small surface as before (init / upsert / query / get / counts) so nothing
else in the app changes — only this file talks to the database. Connection
details live in app/db/settings.py (or environment variables).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

from ..models.job import FreshnessBucket, Job
from ..models.categories import categorize
from . import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    source           TEXT,
    company          TEXT,
    title            TEXT,
    location         TEXT,
    remote           BOOLEAN,
    url              TEXT,
    posted_at        TIMESTAMPTZ,
    freshness_bucket TEXT,
    department       TEXT,
    first_seen       TIMESTAMPTZ,
    last_seen        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_bucket ON jobs (freshness_bucket);
CREATE INDEX IF NOT EXISTS idx_posted ON jobs (posted_at);
"""


def _connect():
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        sslmode=os.environ.get("DB_SSLMODE", "require"),
        connect_timeout=10,
    )


def init_db() -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
    # 'with conn' commits on success


def upsert_jobs(jobs: list[Job]) -> int:
    if not jobs:
        return 0
    now = datetime.now(timezone.utc)
    rows = [
        (
            j.id, j.source, j.company, j.title, j.location, bool(j.remote), j.url,
            j.posted_at, j.freshness_bucket.value, j.department, now, now,
        )
        for j in jobs
    ]
    sql = """
        INSERT INTO jobs (id, source, company, title, location, remote, url,
                          posted_at, freshness_bucket, department, first_seen, last_seen)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            freshness_bucket = EXCLUDED.freshness_bucket,
            posted_at        = EXCLUDED.posted_at,
            url              = EXCLUDED.url,
            last_seen        = EXCLUDED.last_seen
    """
    with _connect() as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows)
    return len(rows)


def _row_to_job(row: dict) -> Job:
    return Job(
        id=row["id"], source=row["source"], company=row["company"], title=row["title"],
        location=row["location"], remote=bool(row["remote"]), url=row["url"],
        posted_at=row["posted_at"],
        freshness_bucket=FreshnessBucket(row["freshness_bucket"]),
        department=row["department"],
    )


def query_jobs(
    freshness: str | None = None,
    remote: bool | None = None,
    company: str | None = None,
    search: str | None = None,
    category: str | None = None,
    limit: int = 100,
) -> list[Job]:
    sql = "SELECT * FROM jobs WHERE 1=1"
    params: list = []
    if search:
        # Tokenized keyword search: every word in the query must appear
        # somewhere in the title, company, location, or department
        # (case-insensitive, any order). "java developer" matches
        # "Backend Developer — Java"; "engineer figma" matches Figma
        # engineering roles.
        for word in search.split()[:6]:  # cap tokens to keep queries sane
            like = f"%{word}%"
            sql += (
                " AND (title ILIKE %s OR company ILIKE %s"
                " OR COALESCE(location,'') ILIKE %s"
                " OR COALESCE(department,'') ILIKE %s)"
            )
            params += [like, like, like, like]
    if freshness:
        order = {"24h": ["24h"], "48h": ["24h", "48h"],
                 "72h": ["24h", "48h", "72h"]}.get(freshness)
        if order:
            sql += " AND freshness_bucket IN (" + ",".join(["%s"] * len(order)) + ")"
            params += order
    if remote is not None:
        sql += " AND remote = %s"
        params.append(remote)
    if company:
        sql += " AND company = %s"
        params.append(company)
    sql += " ORDER BY posted_at DESC LIMIT %s"
    # Fetch wide, then apply the tech-role classifier in Python (hides
    # non-tech roles and applies the category filter), then trim to limit.
    params.append(max(limit * 4, 800))
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    out: list[Job] = []
    for r in rows:
        cat = categorize(r["title"])
        if cat is None:
            continue                     # non-tech role -> hidden
        if category and cat != category:
            continue
        out.append(_row_to_job(r))
        if len(out) >= limit:
            break
    return out



def suggest_jobs(q: str, limit: int = 8) -> list[dict]:
    """Fast type-ahead suggestions. Ranks prefix matches on the title first,
    then mid-word title matches, then company matches; freshest first inside
    each rank."""
    term = q.strip()
    if not term:
        return []
    prefix = f"{term}%"
    anywhere = f"%{term}%"
    sql = """
        SELECT id, title, company, freshness_bucket,
               CASE
                   WHEN title ILIKE %s THEN 0
                   WHEN title ILIKE %s THEN 1
                   ELSE 2
               END AS rank
        FROM jobs
        WHERE title ILIKE %s OR company ILIKE %s
        ORDER BY rank, posted_at DESC
        LIMIT %s
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (prefix, anywhere, anywhere, anywhere, limit))
        return [
            {"id": r[0], "title": r[1], "company": r[2], "freshness_bucket": r[3]}
            for r in cur.fetchall()
        ]


def get_job(job_id: str) -> Job | None:
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
        row = cur.fetchone()
        return _row_to_job(row) if row else None


def counts_by_bucket() -> dict[str, int]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT freshness_bucket, COUNT(*) FROM jobs GROUP BY freshness_bucket")
        return {bucket: count for bucket, count in cur.fetchall()}


def counts_by_category(freshness: str | None = None,
                       remote: bool | None = None) -> dict[str, int]:
    """Live counts per tech category, respecting the active freshness and
    remote filters — so the chips never promise jobs a filter combination
    can't deliver."""
    sql = "SELECT title FROM jobs WHERE 1=1"
    params: list = []
    if freshness:
        order = {"24h": ["24h"], "48h": ["24h", "48h"],
                 "72h": ["24h", "48h", "72h"]}.get(freshness)
        if order:
            sql += " AND freshness_bucket IN (" + ",".join(["%s"] * len(order)) + ")"
            params += order
    if remote is not None:
        sql += " AND remote = %s"
        params.append(remote)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        titles = [r[0] for r in cur.fetchall()]
    counts: dict[str, int] = {}
    for t in titles:
        cat = categorize(t)
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    return counts
