"""Synthetic OHLC chart endpoint."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth_utils import get_current_user
from startup_engine import engine
from state import BASE_VALUATIONS, STOCK_MAP, base_price

router = APIRouter(prefix="/api", tags=["chart"])


@router.get("/chart/{symbol}")
async def chart(symbol: str, range: str = "1d", interval: str | None = None, user=Depends(get_current_user)):
    """Return synthetic OHLC candles for a private startup. Deterministic per
    (symbol, range) so charts are stable across reloads, with a small dependence
    on the current demand-pressure to subtly tilt recent candles."""
    import builtins
    import random as _random
    from data.stocks import TOTAL_SHARES_PER_COMPANY as _TOTAL_SHARES
    _range = builtins.range
    if symbol not in STOCK_MAP:
        raise HTTPException(404, "Unknown symbol")
    rng = range.lower()
    cfg = {
        "1d":  {"points": 78,  "step_min": 5,    "vol": 0.006},
        "5d":  {"points": 65,  "step_min": 30,   "vol": 0.012},
        "1mo": {"points": 22,  "step_min": 1440, "vol": 0.025},
        "3mo": {"points": 65,  "step_min": 1440, "vol": 0.030},
        "6mo": {"points": 130, "step_min": 1440, "vol": 0.035},
        "1y":  {"points": 252, "step_min": 1440, "vol": 0.045},
    }.get(rng)
    if not cfg:
        raise HTTPException(400, "Unsupported range")

    bp = base_price(symbol)
    if bp <= 0:
        raise HTTPException(404, "No base valuation")
    cur_dp = engine.demand_pressure.get(symbol, 0.0)
    cur_price = engine.get_price(symbol) or {}
    last_real = cur_price.get("price") or bp * (1 + cur_dp)

    rng_state = _random.Random(f"{symbol}-{rng}")
    n = cfg["points"]
    step_ms = cfg["step_min"] * 60 * 1000
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    prices = []
    cur = last_real * (1 - rng_state.uniform(0.05, 0.20))
    for i in _range(n):
        drift = rng_state.uniform(-cfg["vol"], cfg["vol"])
        if i > n * 0.75:
            drift += cur_dp * 0.05
        cur = max(cur * (1 + drift), bp * 0.3)
        prices.append(cur)
    prices[-1] = last_real

    candles = []
    for i, c in enumerate(prices):
        o = prices[i - 1] if i > 0 else c * (1 - rng_state.uniform(-0.005, 0.005))
        body_hi = max(o, c) * (1 + abs(rng_state.uniform(0, cfg["vol"]) * 0.4))
        body_lo = min(o, c) * (1 - abs(rng_state.uniform(0, cfg["vol"]) * 0.4))
        v = int(rng_state.uniform(50, 4000)) * 100
        candles.append({
            "t": now_ms - (n - 1 - i) * step_ms,
            "o": round(o, 4),
            "h": round(body_hi, 4),
            "l": round(body_lo, 4),
            "c": round(c, 4),
            "v": v,
        })

    week_high = max(p for p in prices)
    week_low = min(p for p in prices)
    return {
        "symbol": symbol,
        "range": rng,
        "interval": rng,
        "currency": "INR",
        "previousClose": round(prices[0], 4),
        "regularMarketPrice": round(last_real, 4),
        "fiftyTwoWeekHigh": round(week_high * 1.1, 4),
        "fiftyTwoWeekLow": round(week_low * 0.9, 4),
        "candles": candles,
        "valuation": BASE_VALUATIONS.get(symbol, 0),
        "sharesOutstanding": _TOTAL_SHARES,
        "demandPressure": round(cur_dp, 4),
        "isSynthetic": True,
        "narrative": cur_price.get("reason"),
    }
