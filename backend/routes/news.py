"""Live news headlines + per-symbol news endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import get_current_user
from news_feeds import news_feeds
from state import STOCK_MAP

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/headlines")
async def news_headlines(limit: int = 60, matchedOnly: bool = False, minPerSector: int = 0):
    """Latest verified Indian news headlines aggregated from RSS feeds +
    Google News per-company queries. Each article is enriched with matched
    startup symbols + sectors. `minPerSector` (0..20) guarantees at least N
    freshest items per sector when available. Public endpoint."""
    return {
        "headlines": news_feeds.latest(
            limit=min(max(limit, 1), 500),
            matched_only=bool(matchedOnly),
            min_per_sector=min(max(minPerSector, 0), 20),
        ),
        "status": news_feeds.status(),
    }


@router.get("/for/{symbol}")
async def news_for_symbol(symbol: str, _user=Depends(get_current_user)):
    """Headlines mentioning a specific startup (last 72h)."""
    sym = symbol.upper()
    if sym not in STOCK_MAP:
        raise HTTPException(404, "Unknown symbol")
    arts = news_feeds.find_for(sym, limit=10)
    return {
        "symbol": sym,
        "name": STOCK_MAP[sym]["name"],
        "articles": [
            {
                "title": a["title"],
                "summary": a["summary"][:300],
                "source": a["source"],
                "link": a["link"],
                "publishedAt": a["published_at"].isoformat(),
            }
            for a in arts
        ],
    }
