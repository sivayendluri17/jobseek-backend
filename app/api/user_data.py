"""Per-user endpoints — saved and applied jobs (all require login)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.security import get_current_user
from ..db import user_store
from ..models.job import Job

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def me(user: dict = Depends(get_current_user)) -> dict:
    """Current user plus their saved/applied job ids (for the UI state)."""
    return {
        "user": {"id": user["id"], "email": user["email"], "name": user.get("name")},
        "saved_ids": user_store.saved_ids(user["id"]),
        "applied_ids": user_store.applied_ids(user["id"]),
    }


@router.post("/saved/{job_id}")
def save_job(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    user_store.add_saved(user["id"], job_id)
    return {"ok": True}


@router.delete("/saved/{job_id}")
def unsave_job(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    user_store.remove_saved(user["id"], job_id)
    return {"ok": True}


@router.get("/saved", response_model=list[Job])
def list_saved(user: dict = Depends(get_current_user)) -> list[Job]:
    return user_store.saved_jobs(user["id"])


@router.post("/applied/{job_id}")
def apply_job(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    user_store.add_applied(user["id"], job_id)
    return {"ok": True}


@router.get("/applied", response_model=list[Job])
def list_applied(user: dict = Depends(get_current_user)) -> list[Job]:
    return user_store.applied_jobs(user["id"])
