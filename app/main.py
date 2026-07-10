"""JobSeek backend — FastAPI application entry point.

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.jobs import router as jobs_router
from .api.user_data import router as me_router
from .api.gmail import router as gmail_router, callback_router as gmail_callback_router
from .api.chitti import router as chitti_router
from .auth.routes import router as auth_router
from .db import store, user_store, gmail_store

app = FastAPI(title="JobSeek API", version="0.3.0")

# Allow the frontend to call the API. Loosen for local dev; tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(gmail_router)
app.include_router(gmail_callback_router)
app.include_router(chitti_router)


@app.on_event("startup")
def _startup() -> None:
    store.init_db()
    user_store.init_db()
    gmail_store.init_db()
