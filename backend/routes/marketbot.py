"""MarketBot admin news refresh + reasons map."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from auth_utils import get_current_user, require_admin
import marketbot
from startup_engine import engine
from state import STOCKS

router = APIRouter(prefix="/api/marketbot", tags=["marketbot"])


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
