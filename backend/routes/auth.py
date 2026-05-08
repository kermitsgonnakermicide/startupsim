"""Authentication, signup/login/reapply/me/change-password."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from auth_utils import (
    USERNAME_RE, create_token, get_current_user, hash_password, rate_limit, verify_password,
)
from emailer import fire_and_forget, notify_admin_new_application
from models import ChangePasswordReq, LoginReq, ReapplyReq, SignupReq
from state import is_user_active, portfolio_doc, portfolios_col, users_col

logger = logging.getLogger("routes.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/signup")
async def signup(body: SignupReq, request: Request):
    rate_limit(f"signup:{request.client.host}", max_calls=10, window_sec=60)
    username = body.username.strip()
    email = (body.email or "").strip()
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "Username must be 3–20 chars (letters, numbers, underscore).")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "Please provide a valid email address.")
    lc = username.lower()
    existing = await users_col.find_one({"username_lc": lc})
    now_iso = datetime.now(timezone.utc).isoformat()

    if existing:
        if existing.get("isAdmin"):
            raise HTTPException(409, "Username already taken")
        status = existing.get("status", "pending")
        exp_iso = existing.get("approvedUntil")
        expired = False
        if status == "approved" and exp_iso:
            try:
                exp = datetime.fromisoformat(exp_iso)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                expired = datetime.now(timezone.utc) > exp
            except Exception:
                expired = False
        can_reapply = status == "rejected" or expired
        if not can_reapply:
            raise HTTPException(409, "Username already taken")
        await users_col.update_one(
            {"id": existing["id"]},
            {"$set": {
                "passwordHash": hash_password(body.password),
                "email": email,
                "status": "pending",
                "approvedAt": None,
                "approvedUntil": None,
                "reappliedAt": now_iso,
            }},
        )
        fire_and_forget(notify_admin_new_application(existing["username"], email, "", existing["id"]))
        return {"submitted": True, "message": "New application submitted. You'll be able to log in once the creator approves your access."}

    import uuid
    user_id = str(uuid.uuid4())
    await users_col.insert_one({
        "id": user_id,
        "username": username,
        "username_lc": lc,
        "passwordHash": hash_password(body.password),
        "email": email,
        "reason": "",
        "status": "pending",
        "isAdmin": False,
        "approvedAt": None,
        "approvedUntil": None,
        "createdAt": now_iso,
    })
    await portfolios_col.insert_one(portfolio_doc(user_id))
    fire_and_forget(notify_admin_new_application(username, email, "", user_id))
    return {"submitted": True, "message": "Application submitted. You'll be able to log in once the creator approves your access."}


@router.post("/login")
async def login(body: LoginReq, request: Request):
    rate_limit(f"login:{request.client.host}", max_calls=10, window_sec=60)
    lc = body.username.strip().lower()
    logger.info("Login attempt for username: %s", lc)
    
    user = await users_col.find_one({"username_lc": lc})
    if not user:
        logger.warning("Login failed: User '%s' not found", lc)
        raise HTTPException(401, "Invalid username or password")
        
    if not verify_password(body.password, user["passwordHash"]):
        logger.warning("Login failed: Incorrect password for user '%s'", lc)
        raise HTTPException(401, "Invalid username or password")
        
    ok, reason = is_user_active(user)
    if not ok:
        logger.warning("Login failed: User '%s' is inactive. Reason: %s", lc, reason)
        raise HTTPException(status_code=403, detail=reason)
        
    logger.info("Login successful for user: %s (isAdmin=%s)", user["username"], bool(user.get("isAdmin")))
    token = create_token(user["id"], user["username"], bool(user.get("isAdmin", False)))
    return {
        "token": token,
        "userId": user["id"],
        "username": user["username"],
        "isAdmin": bool(user.get("isAdmin", False)),
    }


@router.post("/reapply")
async def reapply(body: ReapplyReq, request: Request):
    rate_limit(f"reapply:{request.client.host}", max_calls=5, window_sec=60)
    lc = body.username.strip().lower()
    user = await users_col.find_one({"username_lc": lc})
    if not user or not verify_password(body.password, user["passwordHash"]):
        raise HTTPException(401, "Invalid username or password")
    if user.get("isAdmin"):
        raise HTTPException(400, "Admin doesn't need to reapply.")
    if len((body.reason or "").strip()) < 10:
        raise HTTPException(400, "Please tell us why you'd like access (min 10 characters).")
    await users_col.update_one(
        {"id": user["id"]},
        {"$set": {
            "status": "pending",
            "reason": body.reason.strip(),
            "approvedAt": None,
            "approvedUntil": None,
            "reappliedAt": datetime.now(timezone.utc).isoformat(),
        }},
    )
    fire_and_forget(notify_admin_new_application(user["username"], user.get("email", ""), body.reason.strip(), user["id"]))
    return {"submitted": True, "message": "New application submitted. Awaiting creator approval."}


@router.get("/me")
async def me(user=Depends(get_current_user)):
    u = await users_col.find_one({"id": user["userId"]}, {"_id": 0})
    if not u:
        raise HTTPException(401, "User not found")
    ok, reason = is_user_active(u)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)
    return {
        "userId": u["id"],
        "username": u["username"],
        "isAdmin": bool(u.get("isAdmin", False)),
        "approvedUntil": u.get("approvedUntil"),
    }


@router.post("/change-password")
async def change_password(body: ChangePasswordReq, user=Depends(get_current_user)):
    if len(body.newPassword) < 6:
        raise HTTPException(400, "New password must be at least 6 characters.")
    if body.newPassword == body.currentPassword:
        raise HTTPException(400, "New password must differ from current password.")
    u = await users_col.find_one({"id": user["userId"]})
    if not u or not verify_password(body.currentPassword, u["passwordHash"]):
        raise HTTPException(401, "Current password is incorrect.")
    await users_col.update_one(
        {"id": user["userId"]},
        {"$set": {"passwordHash": hash_password(body.newPassword)}},
    )
    return {"ok": True, "message": "Password updated successfully."}
