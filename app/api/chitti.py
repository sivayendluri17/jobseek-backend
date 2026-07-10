"""Chitti — JobSeek's AI assistant. 🤖

POST /chitti/ask
  body: { "message": str,
          "job_id": str | null,          # if asking about a specific job
          "history": [ {role, content} ] # this conversation so far (client-held)
        }

Uses Claude (Haiku) via the Anthropic API. Conversations are held by the
client and passed back each turn — nothing stored server-side in v1.
A per-user daily rate limit keeps costs bounded.
"""
from __future__ import annotations

import os
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.security import get_current_user
from ..db import store

router = APIRouter(prefix="/chitti", tags=["chitti"])

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CHITTI_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = 700
DAILY_LIMIT = int(os.environ.get("CHITTI_DAILY_LIMIT", "25"))

SYSTEM_PROMPT = """You are Chitti, the friendly AI assistant inside JobSeek — a job
platform by QuantumGen Inc that shows candidates the freshest US roles.

You help candidates with:
1. Questions about a specific job (fit, skills needed, what to emphasize) when
   job details are provided in the conversation.
2. Career and interview preparation: interview questions, STAR method, resume
   tips, salary negotiation basics, explaining technical concepts.
3. Drafting short application materials: cover notes, brief recruiter replies,
   LinkedIn messages. Keep drafts concise and genuine, never exaggerated.
4. How JobSeek works: jobs are swept from top company boards many times a day
   and sorted by freshness (last 24h/48h/72h); candidates can search with
   type-ahead suggestions, save jobs with the heart, one-tap apply (opens the
   company's real posting), and connect Gmail to read their emails in-app
   (read-only; replies happen in Gmail).

Style: warm, encouraging, practical. Keep answers tight — a few short
paragraphs at most. Use plain language.

Boundaries: You are not a lawyer or immigration advisor — for visa/immigration
questions, give only general public information and recommend consulting an
immigration attorney. Don't invent salary figures or company facts you don't
know; say when you're unsure. Never make up details about a job beyond what's
provided."""

# ---- simple in-memory daily rate limiter (resets on service restart) ----
_usage: dict[int, tuple[str, int]] = {}  # user_id -> (yyyymmdd, count)


def _check_rate(user_id: int) -> None:
    today = time.strftime("%Y%m%d")
    day, count = _usage.get(user_id, (today, 0))
    if day != today:
        day, count = today, 0
    if count >= DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Chitti is resting — you've reached today's limit of "
                   f"{DAILY_LIMIT} questions. Come back tomorrow!",
        )
    _usage[user_id] = (day, count + 1)


class HistoryTurn(BaseModel):
    role: str      # "user" | "assistant"
    content: str


class AskIn(BaseModel):
    message: str
    job_id: str | None = None
    history: list[HistoryTurn] = []


@router.post("/ask")
async def ask_chitti(body: AskIn, user: dict = Depends(get_current_user)) -> dict:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(500, "Chitti is not configured on the server")
    msg = body.message.strip()
    if not msg:
        raise HTTPException(400, "Ask Chitti something!")
    if len(msg) > 2000:
        raise HTTPException(400, "Please keep questions under 2000 characters")

    _check_rate(user["id"])

    # Build the message list: optional job context + prior turns + new question.
    messages: list[dict] = []
    for turn in body.history[-10:]:  # cap context to last 10 turns
        if turn.role in ("user", "assistant") and turn.content.strip():
            messages.append({"role": turn.role, "content": turn.content[:4000]})

    if body.job_id:
        job = store.get_job(body.job_id)
        if job:
            job_ctx = (
                f"[Job the candidate is asking about]\n"
                f"Title: {job.title}\nCompany: {job.company}\n"
                f"Location: {job.location or ('Remote' if job.remote else 'n/a')}\n"
                f"Remote: {'yes' if job.remote else 'no'}\n"
                f"Posted: {job.posted_at} (freshness: {job.freshness_bucket.value})\n"
                f"Posting URL: {job.url}\n\n{msg}"
            )
            messages.append({"role": "user", "content": job_ctx})
        else:
            messages.append({"role": "user", "content": msg})
    else:
        messages.append({"role": "user", "content": msg})

    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "system": SYSTEM_PROMPT,
                "messages": messages,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(502, "Chitti had trouble thinking — please try again")
    data = resp.json()
    reply = "".join(
        block.get("text", "") for block in data.get("content", [])
        if block.get("type") == "text"
    ).strip()
    return {"reply": reply or "Hmm, I came up empty — try rephrasing?"}
