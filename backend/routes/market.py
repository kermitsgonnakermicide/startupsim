"""Stocks, prices, demand, indices, market-status (public-ish endpoints)."""
from __future__ import annotations

from fastapi import APIRouter

from market_timing import session_info
from nse_fetcher import fetcher
from startup_engine import engine
from state import STOCKS, ist_now_str

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/stocks")
async def list_stocks():
    from data.stocks import TOTAL_SHARES_PER_COMPANY
    return {"stocks": STOCKS, "sharesOutstanding": TOTAL_SHARES_PER_COMPANY}


@router.get("/prices")
async def all_prices():
    return {
        "prices": engine.all_prices(),
        "sparks": engine.all_sparks(),
        "lastFullUpdate": engine._initialised_at,
    }


@router.get("/demand")
async def get_demand():
    """Public endpoint: real-time demand-pressure map driven by student trades.
    Range: -0.40 (max sell pressure) … +0.40 (max buy pressure)."""
    return {"pressure": engine.get_demand(), "lastFetchedAt": ist_now_str()}


@router.get("/indices")
async def indices():
    return {"indices": fetcher.cache.indices, "lastFetchedAt": ist_now_str()}


@router.get("/market-status")
async def market_status():
    """Real market open/close — sourced from NSE timing for IST market hours."""
    return fetcher.cache.market_status or session_info()
