"""Leaderboard endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from auth_utils import get_current_user
from startup_engine import engine
from state import (
    STARTING_CASH, badge_for, holdings_col, portfolios_col, transactions_col, users_col,
)

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard")
async def leaderboard(user=Depends(get_current_user)):
    prices = engine.all_prices()

    real_rows = []
    async for port in portfolios_col.find({"fake": {"$ne": True}}, {"_id": 0}):
        uid = port["userId"]
        u = await users_col.find_one({"id": uid}, {"_id": 0, "username": 1, "leaderboardHidden": 1, "isAdmin": 1})
        if not u:
            continue
        is_self = uid == user["userId"]
        if not is_self:
            if u.get("leaderboardHidden"):
                continue
            if u.get("isAdmin"):
                continue
            has_traded = await transactions_col.count_documents({"userId": uid}, limit=1)
            if not has_traded:
                continue
        holdings = await holdings_col.find({"userId": uid}, {"_id": 0}).to_list(500)
        current_val = port.get("cash", 0)
        for h in holdings:
            p = prices.get(h["symbol"], {}).get("price") or h["avgBuyPrice"]
            current_val += p * h["qty"]
        ret_pct = (current_val / STARTING_CASH - 1) * 100
        real_rows.append({
            "username": u["username"],
            "currentValue": round(current_val, 2),
            "pnl": round(current_val - STARTING_CASH, 2),
            "returnPct": round(ret_pct, 2),
            "isCurrentUser": is_self,
            "fake": False,
        })

    combined = real_rows
    combined.sort(key=lambda r: r["returnPct"], reverse=True)
    for i, r in enumerate(combined, start=1):
        r["rank"] = i
        r["badge"] = badge_for(r["returnPct"])

    top = combined[:20]
    my_row = next((r for r in combined if r["isCurrentUser"]), None)
    if my_row and my_row not in top:
        top.append(my_row)

    return {"rows": top, "totalPlayers": len(combined), "me": my_row}
