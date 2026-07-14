"""Resume endpoints — upload, preview, download, delete.

One resume per user, stored in PostgreSQL. Upload accepts PDF or DOCX.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response

from ..auth.security import get_current_user
from ..db import resume_store

router = APIRouter(prefix="/me/resume", tags=["resume"])

MAX_BYTES = 5 * 1024 * 1024  # 5 MB is plenty for a resume
ALLOWED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
}


@router.get("")
def resume_status(user: dict = Depends(get_current_user)) -> dict:
    meta = resume_store.get_resume_meta(user["id"])
    if not meta:
        return {"has_resume": False}
    return {
        "has_resume": True,
        "filename": meta["filename"],
        "content_type": meta["content_type"],
        "uploaded_at": meta["uploaded_at"].isoformat() if meta["uploaded_at"] else None,
        "previewable": meta["content_type"] == "application/pdf",
    }


@router.post("")
async def upload_resume(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> dict:
    ctype = file.content_type or ""
    name = file.filename or "resume"
    if ctype not in ALLOWED and not name.lower().endswith((".pdf", ".docx", ".doc")):
        raise HTTPException(400, "Please upload a PDF or Word document")
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(400, "That file appears to be empty")
    if len(data) > MAX_BYTES:
        raise HTTPException(400, "Resume must be under 5 MB")
    resume_store.save_resume(user["id"], name, ctype or "application/pdf", data)
    meta = resume_store.get_resume_meta(user["id"])
    return {
        "ok": True,
        "filename": name,
        "previewable": (ctype == "application/pdf"),
        "parsed": bool(meta and meta.get("has_text")),
    }


@router.get("/file")
def resume_file(
    download: bool = False,
    user: dict = Depends(get_current_user),
):
    got = resume_store.get_resume_file(user["id"])
    if not got:
        raise HTTPException(404, "No resume uploaded yet")
    data, ctype, filename = got
    disposition = "attachment" if download else "inline"
    return Response(
        content=data,
        media_type=ctype,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.delete("")
def delete_resume(user: dict = Depends(get_current_user)) -> dict:
    resume_store.delete_resume(user["id"])
    return {"ok": True}
