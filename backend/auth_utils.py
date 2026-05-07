"""Auth helpers: password hashing and JWT tokens."""
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Header, Query

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me")
JWT_ALGO = "HS256"
JWT_EXPIRE_DAYS = 7

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, username: str, is_admin: bool = False) -> str:
    payload = {
        "userId": user_id,
        "username": username,
        "isAdmin": bool(is_admin),
        "iat": datetime.now(tz=timezone.utc),
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    return {
        "userId": payload["userId"],
        "username": payload["username"],
        "isAdmin": bool(payload.get("isAdmin", False)),
    }


async def require_admin(authorization: Optional[str] = Header(None)) -> dict:
    u = await get_current_user(authorization)
    if not u.get("isAdmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return u


# --- simple in-memory rate limiter (per-IP) ---
_rate_buckets: dict[str, list[float]] = {}


def rate_limit(key: str, max_calls: int = 10, window_sec: int = 60):
    now = time.time()
    bucket = _rate_buckets.setdefault(key, [])
    # drop old
    while bucket and bucket[0] < now - window_sec:
        bucket.pop(0)
    if len(bucket) >= max_calls:
        raise HTTPException(status_code=429, detail="Too many requests. Try again shortly.")
    bucket.append(now)
