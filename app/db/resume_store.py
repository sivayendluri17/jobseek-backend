"""Resume storage (PostgreSQL bytea) + text extraction + keyword matching.

One resume per user. The file bytes live in a bytea column; we also extract
the text on upload so match scoring doesn't re-parse the PDF every time.
"""
from __future__ import annotations

import io
import re

from psycopg2.extras import RealDictCursor

from .store import _connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS resumes (
    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    content_type TEXT NOT NULL,
    data        BYTEA NOT NULL,
    text        TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT now()
);
"""

# Words too common to be useful signal in a skills match.
_STOP = {
    "the", "and", "for", "with", "you", "our", "are", "has", "have", "will",
    "this", "that", "from", "your", "their", "они", "a", "an", "to", "of", "in",
    "on", "at", "as", "is", "be", "or", "by", "we", "it", "us", "i", "experience",
    "work", "team", "role", "job", "years", "year", "including", "ability",
    "strong", "using", "used", "new", "help", "across", "within", "etc",
}


def init_db() -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)


# ---------------------------------------------------------------- extraction

def extract_text(data: bytes, content_type: str, filename: str) -> str:
    """Pull plain text from a PDF or DOCX resume. Never raises."""
    name = (filename or "").lower()
    try:
        if "pdf" in content_type or name.endswith(".pdf"):
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        if "word" in content_type or name.endswith((".docx", ".doc")):
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""
    return ""


def _keywords(text: str) -> set[str]:
    """Distinctive lowercase tokens from a blob of text."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+.#-]{1,}", (text or "").lower())
    return {w for w in words if len(w) >= 3 and w not in _STOP}


# ---------------------------------------------------------------- storage

def save_resume(user_id: int, filename: str, content_type: str,
                data: bytes) -> None:
    text = extract_text(data, content_type, filename)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO resumes (user_id, filename, content_type, data, text)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                filename     = EXCLUDED.filename,
                content_type = EXCLUDED.content_type,
                data         = EXCLUDED.data,
                text         = EXCLUDED.text,
                uploaded_at  = now()
            """,
            (user_id, filename, content_type, memoryview(data), text),
        )


def get_resume_meta(user_id: int) -> dict | None:
    """Metadata only (no bytes) — for the UI to show current resume."""
    with _connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT user_id, filename, content_type, uploaded_at, "
            "(text IS NOT NULL AND length(text) > 0) AS has_text "
            "FROM resumes WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_resume_file(user_id: int) -> tuple[bytes, str, str] | None:
    """(data, content_type, filename) for download/preview."""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT data, content_type, filename FROM resumes WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return bytes(row[0]), row[1], row[2]


def get_resume_text(user_id: int) -> str | None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT text FROM resumes WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def delete_resume(user_id: int) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM resumes WHERE user_id = %s", (user_id,))


# ---------------------------------------------------------------- matching

def resume_keywords(user_id: int) -> set[str]:
    return _keywords(get_resume_text(user_id) or "")


def match_score(resume_kw: set[str], job_title: str,
                job_text: str = "") -> int | None:
    """Honest keyword-overlap score (0-100) between a resume and a job.
    Returns None if there's no resume to compare against."""
    if not resume_kw:
        return None
    job_kw = _keywords(f"{job_title} {job_text}")
    if not job_kw:
        return 0
    overlap = resume_kw & job_kw
    # Score = how much of the job's keyword set the resume covers, scaled.
    raw = len(overlap) / len(job_kw)
    # Map to a friendly 40-99 range (few real matches ever score <40 or =100).
    return max(1, min(99, round(40 + raw * 59)))
