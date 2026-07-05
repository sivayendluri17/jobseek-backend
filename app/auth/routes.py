"""Auth routes — signup and login."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import user_store
from .security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


def _public(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "name": user.get("name")}


@router.post("/signup")
def signup(body: SignupIn) -> dict:
    email = body.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if user_store.get_user_by_email(email):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    user = user_store.create_user(email, (body.name or "").strip() or None, hash_password(body.password))
    return {"token": create_token(user["id"]), "user": _public(user)}


@router.post("/login")
def login(body: LoginIn) -> dict:
    email = body.email.strip().lower()
    user = user_store.get_user_by_email(email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": create_token(user["id"]), "user": _public(user)}
