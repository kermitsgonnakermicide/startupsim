"""Threshold price alerts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from alerts_service import alerts_service
from auth_utils import get_current_user
from models import AlertReq
from startup_engine import engine
from state import STOCK_MAP

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(user=Depends(get_current_user)):
    rows = await alerts_service.list_for(user["userId"])
    return {"alerts": rows}


@router.post("")
async def create_alert(body: AlertReq, user=Depends(get_current_user)):
    sym = body.symbol.upper().strip()
    if sym not in STOCK_MAP:
        raise HTTPException(400, "Unknown symbol")
    direction = body.direction.lower().strip()
    if direction not in ("above", "below"):
        raise HTTPException(400, "direction must be 'above' or 'below'")
    if body.targetPrice <= 0:
        raise HTTPException(400, "targetPrice must be positive")
    snap = engine.get_price(sym) or {}
    current = snap.get("price") or 0
    if current and (body.targetPrice > current * 100 or body.targetPrice < current / 100):
        raise HTTPException(400, "targetPrice is unreasonably far from current price")
    alert = await alerts_service.create(
        user["userId"], sym, body.targetPrice, direction, body.note or ""
    )
    return {"alert": alert}


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, user=Depends(get_current_user)):
    ok = await alerts_service.delete(user["userId"], alert_id)
    return {"ok": ok}
