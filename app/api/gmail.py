"""Gmail integration — read-only.

Flow:
  1. GET  /gmail/connect        (logged-in user) -> returns Google's consent URL
  2. User approves on Google -> Google redirects to /auth/google/callback
  3. We exchange the code for tokens, store them for the user, and bounce
     the user back to the frontend inbox.
  4. GET  /gmail/messages       -> list recent messages (recruiting-filtered or all)
  5. GET  /gmail/messages/{id}  -> full message body for reading

Only the gmail.readonly scope is requested. Replies happen in Gmail itself —
each message includes a deep link.
"""
from __future__ import annotations

import base64
import os
import time
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from ..auth.security import get_current_user, create_token, JWT_SECRET, JWT_ALG
import jwt as pyjwt

from ..db import gmail_store

router = APIRouter(prefix="/gmail", tags=["gmail"])

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# Where Google sends the user back to (must match the console exactly).
OAUTH_REDIRECT_URI = os.environ.get(
    "OAUTH_REDIRECT_URI", "https://api.jobseek.ink/auth/google/callback"
)
# Where we send the user after connecting (the frontend inbox).
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://jobseek.ink")

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

# Search query used for the recruiting-focused view.
RECRUITING_QUERY = (
    'subject:(interview OR application OR recruiter OR opportunity OR position '
    'OR role OR "job") OR from:(recruiting OR careers OR talent OR noreply@hire)'
)


# ---------------------------------------------------------------- connect

@router.get("/connect")
def gmail_connect(user: dict = Depends(get_current_user)) -> dict:
    """Build the Google consent URL for the logged-in user."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google integration not configured on the server")
    # Carry the user's identity through the OAuth round-trip in `state`
    # as a short-lived signed token.
    state = create_token(user["id"])
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # gives us a refresh token
        "prompt": "consent",        # ensures refresh token on repeat connects
        "state": state,
    }
    return {"auth_url": f"{AUTH_URL}?{urllib.parse.urlencode(params)}"}


# The callback path is /auth/google/callback (registered without the /gmail
# prefix in main.py via this second router).
callback_router = APIRouter(tags=["gmail"])


@callback_router.get("/auth/google/callback")
async def google_callback(code: str | None = None, state: str | None = None,
                          error: str | None = None):
    if error or not code or not state:
        return RedirectResponse(f"{FRONTEND_URL}?gmail=denied")
    # Identify the user from the signed state token.
    try:
        payload = pyjwt.decode(state, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(400, "Invalid state")

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
    if resp.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}?gmail=error")
    tok = resp.json()
    gmail_store.save_tokens(
        user_id,
        access_token=tok["access_token"],
        refresh_token=tok.get("refresh_token"),
        expires_at=int(time.time()) + int(tok.get("expires_in", 3600)),
    )
    return RedirectResponse(f"{FRONTEND_URL}?gmail=connected")


# ---------------------------------------------------------------- helpers

async def _valid_access_token(user_id: int) -> str:
    row = gmail_store.get_tokens(user_id)
    if not row:
        raise HTTPException(status_code=428, detail="Gmail not connected")
    if row["expires_at"] > time.time() + 60:
        return row["access_token"]
    # refresh
    if not row.get("refresh_token"):
        gmail_store.delete_tokens(user_id)
        raise HTTPException(status_code=428, detail="Gmail reconnect required")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TOKEN_URL, data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": row["refresh_token"],
            "grant_type": "refresh_token",
        })
    if resp.status_code != 200:
        gmail_store.delete_tokens(user_id)
        raise HTTPException(status_code=428, detail="Gmail reconnect required")
    tok = resp.json()
    gmail_store.save_tokens(
        user_id,
        access_token=tok["access_token"],
        refresh_token=row["refresh_token"],
        expires_at=int(time.time()) + int(tok.get("expires_in", 3600)),
    )
    return tok["access_token"]


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _decode_body(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", "replace")
    except Exception:
        return ""


def _extract_text(payload: dict) -> str:
    """Prefer text/plain; fall back to text/html; walk multiparts."""
    if payload.get("mimeType") == "text/plain":
        return _decode_body(payload)
    if payload.get("mimeType") == "text/html":
        return _decode_body(payload)
    best = ""
    for part in payload.get("parts", []) or []:
        text = _extract_text(part)
        if part.get("mimeType") == "text/plain" and text:
            return text
        if text and not best:
            best = text
    return best


# ---------------------------------------------------------------- endpoints

@router.get("/status")
def gmail_status(user: dict = Depends(get_current_user)) -> dict:
    return {"connected": gmail_store.get_tokens(user["id"]) is not None}


@router.get("/messages")
async def list_messages(
    view: str = Query("recruiting", pattern="^(recruiting|all)$"),
    limit: int = Query(25, ge=1, le=50),
    user: dict = Depends(get_current_user),
) -> list[dict]:
    token = await _valid_access_token(user["id"])
    params: dict = {"maxResults": limit}
    if view == "recruiting":
        params["q"] = RECRUITING_QUERY
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=25) as client:
        resp = await client.get(f"{GMAIL_API}/messages", params=params, headers=headers)
        if resp.status_code == 401:
            raise HTTPException(428, "Gmail reconnect required")
        resp.raise_for_status()
        ids = [m["id"] for m in resp.json().get("messages", [])]

        out: list[dict] = []
        for mid in ids:
            r = await client.get(
                f"{GMAIL_API}/messages/{mid}",
                params={"format": "metadata",
                        "metadataHeaders": ["From", "Subject", "Date"]},
                headers=headers,
            )
            if r.status_code != 200:
                continue
            m = r.json()
            hs = m.get("payload", {}).get("headers", [])
            out.append({
                "id": m["id"],
                "thread_id": m.get("threadId"),
                "from": _header(hs, "From"),
                "subject": _header(hs, "Subject") or "(no subject)",
                "date": _header(hs, "Date"),
                "snippet": m.get("snippet", ""),
                "unread": "UNREAD" in (m.get("labelIds") or []),
            })
    return out


@router.get("/messages/{message_id}")
async def read_message(message_id: str, user: dict = Depends(get_current_user)) -> dict:
    token = await _valid_access_token(user["id"])
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.get(f"{GMAIL_API}/messages/{message_id}",
                             params={"format": "full"}, headers=headers)
    if r.status_code == 404:
        raise HTTPException(404, "Message not found")
    if r.status_code == 401:
        raise HTTPException(428, "Gmail reconnect required")
    r.raise_for_status()
    m = r.json()
    hs = m.get("payload", {}).get("headers", [])
    body = _extract_text(m.get("payload", {})) or m.get("snippet", "")
    return {
        "id": m["id"],
        "thread_id": m.get("threadId"),
        "from": _header(hs, "From"),
        "to": _header(hs, "To"),
        "subject": _header(hs, "Subject") or "(no subject)",
        "date": _header(hs, "Date"),
        "body": body,
        "is_html": "<html" in body.lower() or "<div" in body.lower(),
        "gmail_link": f"https://mail.google.com/mail/u/0/#inbox/{m.get('threadId')}",
    }


@router.delete("/disconnect")
def gmail_disconnect(user: dict = Depends(get_current_user)) -> dict:
    gmail_store.delete_tokens(user["id"])
    return {"ok": True}
