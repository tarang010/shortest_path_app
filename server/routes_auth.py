"""Signup / login / current-user endpoints."""
import datetime

from fastapi import APIRouter, Depends, HTTPException

from db import db
from models import LoginIn, SignupIn, TokenOut
from security import current_user, hash_password, make_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _split_identifier(identifier: str):
    """Return (email, phone) with exactly one set, based on whether it looks like an email."""
    ident = identifier.strip()
    if "@" in ident:
        return ident.lower(), None
    return None, ident.replace(" ", "")


@router.post("/signup", response_model=TokenOut)
def signup(body: SignupIn):
    if db is None:
        raise HTTPException(503, "Database not configured")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    email, phone = _split_identifier(body.identifier)
    if not email and not phone:
        raise HTTPException(400, "Enter an email or phone number")
    query = {"email": email} if email else {"phone": phone}
    if db.users.find_one(query):
        raise HTTPException(409, "An account with that email/phone already exists")
    doc = {"name": body.name.strip() or "User", "password_hash": hash_password(body.password),
           "created": datetime.datetime.utcnow()}
    if email:
        doc["email"] = email
    if phone:
        doc["phone"] = phone
    res = db.users.insert_one(doc)
    uid = str(res.inserted_id)
    return TokenOut(token=make_token(uid), user_id=uid, name=doc["name"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn):
    if db is None:
        raise HTTPException(503, "Database not configured")
    email, phone = _split_identifier(body.identifier)
    user = db.users.find_one({"email": email} if email else {"phone": phone})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(401, "Wrong email/phone or password")
    uid = str(user["_id"])
    return TokenOut(token=make_token(uid), user_id=uid, name=user.get("name", "User"))


@router.get("/me")
def me(user=Depends(current_user)):
    return {"user_id": str(user["_id"]), "name": user.get("name"),
            "email": user.get("email"), "phone": user.get("phone")}
