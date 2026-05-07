"""Portfolio + Trade + Transactions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import get_current_user
from models import TradeReq
from startup_engine import engine
from state import (
    STOCK_MAP, compute_portfolio, holdings_col, market_is_open, portfolio_doc,
    portfolios_col, transactions_col,
)

router = APIRouter(prefix="/api", tags=["trade"])


@router.get("/portfolio")
async def get_portfolio(user=Depends(get_current_user)):
    return await compute_portfolio(user["userId"])


@router.post("/trade")
async def trade(body: TradeReq, user=Depends(get_current_user)):
    user_id = user["userId"]
    symbol = body.symbol
    if symbol not in STOCK_MAP:
        raise HTTPException(400, "Unknown symbol")
    if body.qty <= 0:
        raise HTTPException(400, "Quantity must be positive")
    if not market_is_open():
        raise HTTPException(400, "Trading is disabled. The market is currently closed.")
    cached = engine.get_price(symbol) or {}
    live_price = cached.get("price") or body.price
    if not live_price or live_price <= 0:
        raise HTTPException(400, "Price unavailable. Try again in a moment.")
    total = live_price * body.qty
    meta = STOCK_MAP[symbol]
    port = await portfolios_col.find_one({"userId": user_id})
    if not port:
        port = portfolio_doc(user_id)
        await portfolios_col.insert_one({**port})

    if body.type == "BUY":
        if port["cash"] < total:
            raise HTTPException(400, "Insufficient cash")
        new_cash = port["cash"] - total
        existing = await holdings_col.find_one({"userId": user_id, "symbol": symbol})
        if existing:
            new_qty = existing["qty"] + body.qty
            new_avg = (existing["avgBuyPrice"] * existing["qty"] + total) / new_qty
            await holdings_col.update_one(
                {"userId": user_id, "symbol": symbol},
                {"$set": {"qty": new_qty, "avgBuyPrice": round(new_avg, 4)}},
            )
        else:
            await holdings_col.insert_one({
                "id": str(uuid.uuid4()),
                "userId": user_id,
                "symbol": symbol,
                "name": meta["name"],
                "sector": meta["sector"],
                "qty": body.qty,
                "avgBuyPrice": round(live_price, 4),
            })
        await portfolios_col.update_one({"userId": user_id}, {"$set": {"cash": new_cash}})
    elif body.type == "SELL":
        existing = await holdings_col.find_one({"userId": user_id, "symbol": symbol})
        if not existing or existing["qty"] < body.qty:
            raise HTTPException(400, "Not enough shares to sell")
        new_qty = existing["qty"] - body.qty
        if new_qty == 0:
            await holdings_col.delete_one({"userId": user_id, "symbol": symbol})
        else:
            await holdings_col.update_one(
                {"userId": user_id, "symbol": symbol},
                {"$set": {"qty": new_qty}},
            )
        new_cash = port["cash"] + total
        await portfolios_col.update_one({"userId": user_id}, {"$set": {"cash": new_cash}})
    else:
        raise HTTPException(400, "Invalid trade type")

    await transactions_col.insert_one({
        "id": str(uuid.uuid4()),
        "userId": user_id,
        "symbol": symbol,
        "name": meta["name"],
        "sector": meta["sector"],
        "type": body.type,
        "qty": body.qty,
        "price": round(live_price, 4),
        "total": round(total, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    engine.apply_trade_pressure(symbol, body.type)
    portfolio = await compute_portfolio(user_id)
    return {"ok": True, "fillPrice": round(live_price, 4), "portfolio": portfolio}


@router.get("/transactions")
async def get_transactions(user=Depends(get_current_user)):
    rows = (
        await transactions_col.find({"userId": user["userId"]}, {"_id": 0})
        .sort("timestamp", -1)
        .to_list(100)
    )
    return {"transactions": rows}
