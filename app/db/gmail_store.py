"""Storage for users' Gmail OAuth tokens (PostgreSQL)."""
from __future__ import annotations

from psycopg2.extras import RealDictCursor

from .store import _connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS gmail_tokens (
    user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    access_token  TEXT NOT NULL,
    refresh_token TEXT,
    expires_at    BIGINT NOT NULL,
    connected_at  TIMESTAMPTZ DEFAULT now()
);
"""


def init_db() -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)


def save_tokens(user_id: int, access_token: str,
                refresh_token: str | None, expires_at: int) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO gmail_tokens (user_id, access_token, refresh_token, expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                access_token  = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token,
                                         gmail_tokens.refresh_token),
                expires_at    = EXCLUDED.expires_at
            """,
            (user_id, access_token, refresh_token, expires_at),
        )


def get_tokens(user_id: int) -> dict | None:
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM gmail_tokens WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def delete_tokens(user_id: int) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM gmail_tokens WHERE user_id = %s", (user_id,))
