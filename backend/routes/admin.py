"""Admin (creator-only) endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import require_admin
from emailer import fire_and_forget, notify_user_approved, notify_user_rejected
from models import AdminActionReq, AdminLeaderboardVisibilityReq
from state import APPROVAL_DAYS, user_app_view, users_col

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/applications")
async def admin_list(admin=Depends(require_admin)):
    rows = []
    async for u in users_col.find({"isAdmin": {"$ne": True}}, {"_id": 0, "passwordHash": 0}):
        rows.append(user_app_view(u))
    rows.sort(key=lambda r: r.get("reappliedAt") or r.get("createdAt") or "", reverse=True)
    pending = [r for r in rows if r["status"] == "pending"]
    approved = [r for r in rows if r["status"] == "approved"]
    rejected = [r for r in rows if r["status"] == "rejected"]
    return {
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "counts": {"pending": len(pending), "approved": len(approved), "rejected": len(rejected)},
    }


@router.post("/approve")
async def admin_approve(body: AdminActionReq, admin=Depends(require_admin)):
    user = await users_col.find_one({"id": body.userId})
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("isAdmin"):
        raise HTTPException(400, "Cannot modify admin account")
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=APPROVAL_DAYS)
    await users_col.update_one(
        {"id": body.userId},
        {"$set": {
            "status": "approved",
            "approvedAt": now.isoformat(),
            "approvedUntil": until.isoformat(),
        }},
    )
    fire_and_forget(notify_user_approved(user.get("email", ""), user["username"], until.isoformat()))
    return {"ok": True, "approvedUntil": until.isoformat()}


@router.post("/reject")
async def admin_reject(body: AdminActionReq, admin=Depends(require_admin)):
    user = await users_col.find_one({"id": body.userId})
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("isAdmin"):
        raise HTTPException(400, "Cannot modify admin account")
    await users_col.update_one(
        {"id": body.userId},
        {"$set": {"status": "rejected", "approvedAt": None, "approvedUntil": None}},
    )
    fire_and_forget(notify_user_rejected(user.get("email", ""), user["username"]))
    return {"ok": True}


@router.post("/revoke")
async def admin_revoke(body: AdminActionReq, admin=Depends(require_admin)):
    user = await users_col.find_one({"id": body.userId})
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("isAdmin"):
        raise HTTPException(400, "Cannot modify admin account")
    await users_col.update_one(
        {"id": body.userId},
        {"$set": {"status": "pending", "approvedAt": None, "approvedUntil": None}},
    )
    return {"ok": True}


@router.post("/leaderboard-visibility")
async def admin_leaderboard_visibility(body: AdminLeaderboardVisibilityReq, admin=Depends(require_admin)):
    user = await users_col.find_one({"id": body.userId})
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("isAdmin"):
        raise HTTPException(400, "Cannot modify admin account")
    await users_col.update_one(
        {"id": body.userId},
        {"$set": {"leaderboardHidden": bool(body.hidden)}},
    )
    return {"ok": True, "leaderboardHidden": bool(body.hidden)}


@router.post("/bulk/reject-pending")
async def admin_bulk_reject_pending(admin=Depends(require_admin)):
    targets = await users_col.find(
        {"status": "pending", "isAdmin": {"$ne": True}},
        {"_id": 0, "id": 1, "email": 1, "username": 1},
    ).to_list(10000)
    if not targets:
        return {"ok": True, "count": 0}
    ids = [t["id"] for t in targets]
    await users_col.update_many(
        {"id": {"$in": ids}},
        {"$set": {"status": "rejected", "approvedAt": None, "approvedUntil": None}},
    )
    for t in targets:
        if t.get("email"):
            fire_and_forget(notify_user_rejected(t["email"], t["username"]))
    return {"ok": True, "count": len(ids)}


@router.post("/bulk/revoke-approved")
async def admin_bulk_revoke_approved(admin=Depends(require_admin)):
    res = await users_col.update_many(
        {"status": "approved", "isAdmin": {"$ne": True}},
        {"$set": {"status": "pending", "approvedAt": None, "approvedUntil": None}},
    )
    return {"ok": True, "count": res.modified_count}


@router.post("/bulk/leaderboard-hide-all")
async def admin_bulk_leaderboard_hide_all(admin=Depends(require_admin)):
    res = await users_col.update_many(
        {"isAdmin": {"$ne": True}},
        {"$set": {"leaderboardHidden": True}},
    )
    return {"ok": True, "count": res.modified_count}


@router.post("/bulk/leaderboard-show-all")
async def admin_bulk_leaderboard_show_all(admin=Depends(require_admin)):
    res = await users_col.update_many(
        {"isAdmin": {"$ne": True}},
        {"$set": {"leaderboardHidden": False}},
    )
    return {"ok": True, "count": res.modified_count}
