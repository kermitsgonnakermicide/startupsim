"""Watchlist endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import get_current_user
from models import WatchlistReq
from state import STOCK_MAP, watchlists_col

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
async def get_watchlist(user=Depends(get_current_user)):
    rows = (
        await watchlists_col.find({"userId": user["userId"]}, {"_id": 0})
        .sort("addedAt", -1)
        .to_list(500)
    )
    return {"symbols": [r["symbol"] for r in rows if r["symbol"] in STOCK_MAP]}


@router.post("")
async def add_watchlist(body: WatchlistReq, user=Depends(get_current_user)):
    sym = body.symbol.upper().strip()
    if sym not in STOCK_MAP:
        raise HTTPException(400, "Unknown symbol")
    await watchlists_col.update_one(
        {"userId": user["userId"], "symbol": sym},
        {"$setOnInsert": {
            "userId": user["userId"],
            "symbol": sym,
            "addedAt": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "symbol": sym}


@router.delete("/{symbol}")
async def remove_watchlist(symbol: str, user=Depends(get_current_user)):
    sym = symbol.upper().strip()
    await watchlists_col.delete_one({"userId": user["userId"], "symbol": sym})
    return {"ok": True, "symbol": sym}
