"""Password hashing (bcrypt) and JWT tokens, plus the FastAPI auth dependency."""
import datetime

import bcrypt
import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config
from db import db

bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def make_token(user_id: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"sub": user_id, "iat": now,
               "exp": now + datetime.timedelta(days=config.JWT_TTL_DAYS)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALG)


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        payload = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALG])
        uid = payload["sub"]
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.users.find_one({"_id": ObjectId(uid)}) if db is not None else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user
