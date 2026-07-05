"""User accounts + saved/applied jobs storage (PostgreSQL).

Reuses the same connection helper as the jobs store, and returns saved/applied
jobs as full Job objects by joining against the jobs table.
"""
from __future__ import annotations

from psycopg2.extras import RealDictCursor

from ..models.job import Job
from .store import _connect, _row_to_job

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS saved_jobs (
    user_id  INTEGER REFERENCES users(id) ON DELETE CASCADE,
    job_id   TEXT,
    saved_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, job_id)
);
CREATE TABLE IF NOT EXISTS applied_jobs (
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    job_id     TEXT,
    applied_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, job_id)
);
"""


def init_db() -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)


# ---- users ----

def create_user(email: str, name: str | None, password_hash: str) -> dict:
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s) "
            "RETURNING id, email, name",
            (email, name, password_hash),
        )
        return dict(cur.fetchone())


def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, email, name FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


# ---- saved ----

def add_saved(user_id: int, job_id: str) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO saved_jobs (user_id, job_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (user_id, job_id),
        )


def remove_saved(user_id: int, job_id: str) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM saved_jobs WHERE user_id = %s AND job_id = %s",
            (user_id, job_id),
        )


def saved_ids(user_id: int) -> list[str]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT job_id FROM saved_jobs WHERE user_id = %s", (user_id,))
        return [r[0] for r in cur.fetchall()]


def saved_jobs(user_id: int) -> list[Job]:
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT j.* FROM jobs j JOIN saved_jobs s ON j.id = s.job_id "
            "WHERE s.user_id = %s ORDER BY s.saved_at DESC",
            (user_id,),
        )
        return [_row_to_job(r) for r in cur.fetchall()]


# ---- applied ----

def add_applied(user_id: int, job_id: str) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO applied_jobs (user_id, job_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (user_id, job_id),
        )


def applied_ids(user_id: int) -> list[str]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT job_id FROM applied_jobs WHERE user_id = %s", (user_id,))
        return [r[0] for r in cur.fetchall()]


def applied_jobs(user_id: int) -> list[Job]:
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT j.* FROM jobs j JOIN applied_jobs a ON j.id = a.job_id "
            "WHERE a.user_id = %s ORDER BY a.applied_at DESC",
            (user_id,),
        )
        return [_row_to_job(r) for r in cur.fetchall()]
