"""MarketBot chat + admin news refresh + reasons map."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import get_current_user, require_admin
import marketbot
from models import MarketBotChatReq
from startup_engine import engine
from state import STOCKS

logger = logging.getLogger("routes.marketbot")
router = APIRouter(prefix="/api/marketbot", tags=["marketbot"])


@router.post("/chat")
async def marketbot_chat(body: MarketBotChatReq, user=Depends(get_current_user)):
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(400, "Empty message")
    if len(msg) > 1000:
        raise HTTPException(400, "Message too long (max 1000 chars)")
    sid = body.sessionId or f"chat-{user['userId']}"
    try:
        reply = await marketbot.chat_with_history(sid, body.history or [], msg)
        return {"reply": reply, "sessionId": sid}
    except Exception as e:
        logger.warning("MarketBot chat failed: %s", e)
        raise HTTPException(503, "MarketBot is taking a break. Try again shortly!")


@router.post("/refresh-news")
async def marketbot_refresh_news(_admin=Depends(require_admin)):
    """Admin-triggered: pick 8 random symbols and refresh their sentiment."""
    import random as _r
    batch = _r.sample(STOCKS, k=min(8, len(STOCKS)))
    items = await marketbot.fetch_news_sentiment(batch)
    if items:
        engine.apply_news_sentiment(items)
    return {"ok": True, "applied": len(items), "items": items}


@router.get("/news")
async def marketbot_get_news(_user=Depends(get_current_user)):
    """Latest known reason strings keyed by symbol (populated by news refresh)."""
    return {"news": dict(engine.reasons)}
