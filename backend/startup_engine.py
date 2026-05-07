"""Startup price simulation engine.

Simulates per-share prices for private/unlisted Indian startups based on:
1. A baseline derived from BASE_VALUATIONS (PRICE_FACTOR-scaled).
2. A small algorithmic random walk + momentum bias (during market hours only).
3. In-memory demand pressure that is moved by every successful BUY/SELL trade,
   then decays mean-reverting back to zero over time.

Effective price = base_price * (1 + demand_pressure[symbol]) * (1 + algo_drift[symbol])

State is in-memory only (resets on server restart — by design, "fresh school day").
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from datetime import datetime
from typing import Any, Callable

import pytz

from data.stocks import STOCKS, STOCK_MAP, BASE_VALUATIONS, base_price

logger = logging.getLogger("startup_engine")

IST = pytz.timezone("Asia/Kolkata")

# Tunables
DEMAND_DECAY = 0.92          # multiplied every 60s (mean-reversion)
DEMAND_BUY_IMPACT = 0.008    # +0.8% per BUY trade
DEMAND_SELL_IMPACT = 0.008   # -0.8% per SELL trade
DEMAND_CAP = 0.40            # ±40% max deviation from base

ALGO_TICK_INTERVAL_RANGE = (2.0, 5.0)   # seconds between random walk ticks
ALGO_BATCH_SIZE_RANGE = (3, 5)          # symbols nudged per tick
ALGO_NUDGE_RANGE = (-0.015, 0.015)      # ±1.5% per nudge
ALGO_MAX_DEVIATION = 0.30               # ±30% max algorithmic drift from base
ALGO_DECAY = 0.98                       # algo drift mean-reverts toward 0


def _ist_now_str() -> str:
    return datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S")


NEWS_CYCLE_INTERVAL = 600   # seconds between news refreshes (10 min)
NEWS_BATCH_SIZE = 5         # symbols per batch — full universe covered every ~3 hours
FULL_SWEEP_INTERVAL = 1800  # seconds between full-universe sweeps (30 min)
FULL_SWEEP_CHUNK = 10       # symbols per Claude call during a full sweep


class StartupEngine:
    def __init__(self):
        # demand_pressure: float in [-DEMAND_CAP, +DEMAND_CAP]; positive = buy pressure
        self.demand_pressure: dict[str, float] = {s["symbol"]: 0.0 for s in STOCKS}
        # algorithmic drift (random walk + momentum), multiplicative on base price
        self._algo_drift: dict[str, float] = {s["symbol"]: 0.0 for s in STOCKS}
        # last momentum direction per symbol (sign)
        self._momentum: dict[str, int] = {s["symbol"]: 0 for s in STOCKS}
        # full price snapshot per symbol
        self.prices: dict[str, dict[str, Any]] = {}
        # last 30 prices for sparklines
        self.sparks: dict[str, deque] = {s["symbol"]: deque(maxlen=30) for s in STOCKS}
        # Open prices recorded once per session start; stays for session
        self.opens: dict[str, float] = {}
        # MarketBot-generated reasons (latest news per symbol)
        self.reasons: dict[str, str] = {}
        # round-robin cursor for the news cycle
        self._news_cursor: int = 0
        # subscribers (asyncio queues for WebSocket fan-out)
        self._subscribers: set[asyncio.Queue] = set()
        # market-open getter, set from outside
        self._is_market_open_fn = lambda: False
        # news-fetcher (set externally to avoid circular import with marketbot)
        self._news_fetcher = None
        # live-news fetcher: async (items, article_lookup) -> dict
        self._live_news_fetcher = None
        # synchronous lookup: (symbol) -> list[article_dict]
        self._live_news_lookup = None
        # optional crossing-check callback: (symbol, prev_price, new_price) -> None
        self._alert_check: Callable[[str, float | None, float], None] | None = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._initialised_at = time.time()

    # ---------- subscribers ----------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

    async def _broadcast(self, msg: dict):
        dead = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    # ---------- accessors ----------
    def set_market_open_fn(self, fn):
        self._is_market_open_fn = fn

    def set_news_fetcher(self, fn):
        """Wire in an async news fetcher. Signature: async (items: list[dict]) -> dict[str, {score, reason}]."""
        self._news_fetcher = fn

    def set_live_news(self, fetcher, lookup):
        """Wire in the live-news pipeline.
        fetcher: async (items, article_lookup) -> dict
        lookup:  sync (symbol) -> list[article_dict]
        """
        self._live_news_fetcher = fetcher
        self._live_news_lookup = lookup

    def set_alert_check(self, fn):
        """Wire in a synchronous alert crossing-check hook.
        Signature: (symbol, prev_price, new_price) -> None."""
        self._alert_check = fn

    def all_prices(self) -> dict[str, dict[str, Any]]:
        return dict(self.prices)

    def get_price(self, symbol: str) -> dict | None:
        return self.prices.get(symbol)

    def get_demand(self) -> dict[str, float]:
        return {k: round(v, 4) for k, v in self.demand_pressure.items()}

    def spark(self, symbol: str) -> list[float]:
        return list(self.sparks.get(symbol, []))

    def all_sparks(self) -> dict[str, list[float]]:
        return {s["symbol"]: list(self.sparks[s["symbol"]]) for s in STOCKS}

    # ---------- demand pressure ----------
    def apply_trade_pressure(self, symbol: str, side: str):
        if symbol not in self.demand_pressure:
            return
        delta = DEMAND_BUY_IMPACT if side == "BUY" else -DEMAND_SELL_IMPACT
        new_v = self.demand_pressure[symbol] + delta
        if new_v > DEMAND_CAP:
            new_v = DEMAND_CAP
        elif new_v < -DEMAND_CAP:
            new_v = -DEMAND_CAP
        self.demand_pressure[symbol] = new_v
        # re-price immediately so subsequent reads see the new effective price
        self._reprice(symbol, broadcast=False)

    # ---------- pricing ----------
    def _effective_price(self, symbol: str) -> float:
        bp = base_price(symbol)
        dp = self.demand_pressure.get(symbol, 0.0)
        ad = self._algo_drift.get(symbol, 0.0)
        return max(bp * (1 + dp) * (1 + ad), 0.0001)

    def _reprice(self, symbol: str, broadcast: bool = True) -> dict | None:
        meta = STOCK_MAP.get(symbol)
        if not meta:
            return None
        prev = self.prices.get(symbol) or {}
        new_price = round(self._effective_price(symbol), 4)
        open_ = self.opens.get(symbol)
        if open_ is None:
            open_ = new_price
            self.opens[symbol] = new_price
        # high/low based on session range
        prev_high = prev.get("high") or new_price
        prev_low = prev.get("low") or new_price
        high = max(prev_high, new_price)
        low = min(prev_low, new_price)
        change = round(new_price - open_, 4)
        change_pct = round(((new_price - open_) / open_) * 100, 2) if open_ else 0.0
        # synthetic "volume" — count of demand+algo activity
        volume = int(prev.get("volume") or 0) + 1
        snap = {
            "symbol": symbol,
            "price": new_price,
            "open": round(open_, 4),
            "high": round(high, 4),
            "low": round(low, 4),
            "close": round(open_, 4),
            "change": change,
            "changePct": change_pct,
            "volume": volume,
            "weekHigh52": None,
            "weekLow52": None,
            "lastUpdated": _ist_now_str(),
            "source": "MarketBot",
            "name": meta["name"],
            "sector": meta["sector"],
            "valuation": BASE_VALUATIONS.get(symbol, 0),
            "demandPressure": round(self.demand_pressure.get(symbol, 0.0), 4),
            "reason": self.reasons.get(symbol),
        }
        self.prices[symbol] = snap
        self.sparks[symbol].append(new_price)
        # Threshold alerts — check crossing against prev price before broadcast.
        if self._alert_check is not None:
            try:
                self._alert_check(symbol, prev.get("price"), new_price)
            except Exception:
                logger.exception("alert_check hook failed for %s", symbol)
        if broadcast and prev.get("price") != new_price:
            ev = {
                "type": "TICK",
                "symbol": symbol,
                "oldPrice": prev.get("price"),
                "newPrice": new_price,
                "change": change,
                "changePct": change_pct,
                "lastUpdated": snap["lastUpdated"],
            }
            try:
                asyncio.get_event_loop().create_task(self._broadcast(ev))
            except RuntimeError:
                pass
        return snap

    def reprice_all(self):
        """Initial seeding — compute every price once."""
        for s in STOCKS:
            self._reprice(s["symbol"], broadcast=False)

    # ---------- background loops ----------
    async def _algo_walk_loop(self):
        while self._running:
            try:
                interval = random.uniform(*ALGO_TICK_INTERVAL_RANGE)
                await asyncio.sleep(interval)
                if not self._is_market_open_fn():
                    # decay drift slightly when closed so prices ease back to base
                    for sym in list(self._algo_drift.keys()):
                        self._algo_drift[sym] *= ALGO_DECAY
                    continue
                batch = random.sample(
                    [s["symbol"] for s in STOCKS],
                    k=random.randint(*ALGO_BATCH_SIZE_RANGE),
                )
                ticks = []
                for sym in batch:
                    nudge = random.uniform(*ALGO_NUDGE_RANGE)
                    # small momentum: bias 30% toward last move direction
                    mo = self._momentum.get(sym, 0)
                    if mo:
                        nudge += mo * 0.003
                    new_drift = self._algo_drift[sym] * 0.985 + nudge
                    if new_drift > ALGO_MAX_DEVIATION:
                        new_drift = ALGO_MAX_DEVIATION
                    elif new_drift < -ALGO_MAX_DEVIATION:
                        new_drift = -ALGO_MAX_DEVIATION
                    self._algo_drift[sym] = new_drift
                    self._momentum[sym] = 1 if nudge > 0 else (-1 if nudge < 0 else 0)
                    snap = self._reprice(sym, broadcast=False)
                    if snap:
                        ticks.append({
                            "type": "TICK",
                            "symbol": sym,
                            "newPrice": snap["price"],
                            "change": snap["change"],
                            "changePct": snap["changePct"],
                            "lastUpdated": snap["lastUpdated"],
                        })
                # broadcast batched
                if ticks:
                    await self._broadcast({"type": "PRICES", "data": self.all_prices()})
                    for t in ticks[:20]:
                        await self._broadcast(t)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("algo loop error: %s", e)
                await asyncio.sleep(2)

    async def _decay_loop(self):
        while self._running:
            try:
                await asyncio.sleep(60)
                touched = False
                for sym in list(self.demand_pressure.keys()):
                    v = self.demand_pressure[sym]
                    if abs(v) > 1e-6:
                        self.demand_pressure[sym] = v * DEMAND_DECAY
                        touched = True
                if touched:
                    # re-price all and broadcast snapshot
                    for s in STOCKS:
                        self._reprice(s["symbol"], broadcast=False)
                    await self._broadcast({"type": "PRICES", "data": self.all_prices()})
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("decay loop error: %s", e)
                await asyncio.sleep(2)

    # ---------- MarketBot insight integration ----------
    def apply_news_sentiment(self, items: dict[str, dict]):
        """Apply MarketBot-fetched news sentiment.
        items: { symbol: { "score": int(-5..+5), "reason": str } }
        Each unit of score nudges algo_drift by 1.2%.
        Range: ±5 score → ±6% price impact, decaying mean-reverting over hours.
        """
        for sym, item in items.items():
            if sym not in self._algo_drift:
                continue
            score = max(-5, min(5, int(item.get("score", 0))))
            nudge = score * 0.012
            new_drift = self._algo_drift[sym] + nudge
            if new_drift > ALGO_MAX_DEVIATION:
                new_drift = ALGO_MAX_DEVIATION
            elif new_drift < -ALGO_MAX_DEVIATION:
                new_drift = -ALGO_MAX_DEVIATION
            self._algo_drift[sym] = new_drift
            reason = (item.get("reason") or "").strip()
            if reason:
                self.reasons[sym] = reason[:240]
            self._reprice(sym, broadcast=False)

    async def _news_cycle_loop(self):
        """Round-robin news refresh: every NEWS_CYCLE_INTERVAL seconds, ask
        MarketBot to score the next NEWS_BATCH_SIZE symbols and apply the
        sentiment to algo drift. Prefers live RSS-scraped headlines when
        available; falls back to MarketBot's training knowledge for long-tail
        symbols with no recent coverage."""
        # short startup delay so first call doesn't race the engine init
        await asyncio.sleep(8)
        while self._running:
            try:
                if not self._news_fetcher:
                    await asyncio.sleep(NEWS_CYCLE_INTERVAL)
                    continue
                # next slice of the universe (round-robin)
                start = self._news_cursor
                end = start + NEWS_BATCH_SIZE
                slice_ = STOCKS[start:end]
                if len(slice_) < NEWS_BATCH_SIZE:
                    slice_ = slice_ + STOCKS[: (NEWS_BATCH_SIZE - len(slice_))]
                    self._news_cursor = NEWS_BATCH_SIZE - len(STOCKS[start:end])
                else:
                    self._news_cursor = end % len(STOCKS)
                logger.info("News cycle: scoring %s", [s["symbol"] for s in slice_])

                # Tier 1: live RSS-driven scoring (only for symbols with hits)
                live_items: dict[str, dict] = {}
                if self._live_news_lookup:
                    article_lookup = {
                        s["symbol"]: self._live_news_lookup(s["symbol"]) for s in slice_
                    }
                    have_articles = [s for s in slice_ if article_lookup[s["symbol"]]]
                    if have_articles and self._live_news_fetcher:
                        live_items = await self._live_news_fetcher(have_articles, article_lookup)

                # Tier 2: training-knowledge fallback for symbols not covered by live news
                fallback_slice = [s for s in slice_ if s["symbol"] not in live_items]
                fallback_items: dict[str, dict] = {}
                if fallback_slice:
                    fallback_items = await self._news_fetcher(fallback_slice)

                items = {**fallback_items}
                if live_items:
                    # Tag live-scored ones with a 🔴 LIVE prefix so users can
                    # tell real headlines apart from training-knowledge fallback.
                    for sym, info in live_items.items():
                        info["reason"] = "🔴 LIVE: " + info["reason"]
                    items.update(live_items)  # live takes precedence on overlap
                if items:
                    self.apply_news_sentiment(items)
                    await self._broadcast({"type": "NEWS", "data": dict(self.reasons)})
                    await self._broadcast({"type": "PRICES", "data": self.all_prices()})
                    logger.info(
                        "News cycle applied %d items (%d live, %d fallback)",
                        len(items), len(live_items), len(fallback_items),
                    )
                await asyncio.sleep(NEWS_CYCLE_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("News cycle error: %s", e)
                await asyncio.sleep(60)

    async def _full_sweep_loop(self):
        """Periodic full-universe MarketBot news refresh.

        Runs every FULL_SWEEP_INTERVAL seconds. Sweeps every listed startup in
        chunks of FULL_SWEEP_CHUNK, preferring live RSS headlines and falling
        back to MarketBot's training-knowledge for symbols without coverage.
        Complements the slow round-robin loop so long-tail companies always get
        a refreshed narrative within ~30 minutes of a server boot.
        """
        # initial offset so it doesn't collide with warmup or the round-robin's first tick
        await asyncio.sleep(120)
        while self._running:
            try:
                if not self._news_fetcher:
                    await asyncio.sleep(FULL_SWEEP_INTERVAL)
                    continue
                logger.info("Full-universe news sweep starting (%d symbols)", len(STOCKS))
                live_total = 0
                fallback_total = 0
                for i in range(0, len(STOCKS), FULL_SWEEP_CHUNK):
                    chunk = STOCKS[i : i + FULL_SWEEP_CHUNK]
                    live_items: dict[str, dict] = {}
                    if self._live_news_lookup:
                        article_lookup = {
                            s["symbol"]: self._live_news_lookup(s["symbol"]) for s in chunk
                        }
                        have_articles = [s for s in chunk if article_lookup[s["symbol"]]]
                        if have_articles and self._live_news_fetcher:
                            live_items = await self._live_news_fetcher(have_articles, article_lookup)
                    fallback_slice = [s for s in chunk if s["symbol"] not in live_items]
                    fallback_items: dict[str, dict] = {}
                    if fallback_slice:
                        fallback_items = await self._news_fetcher(fallback_slice)
                    items = {**fallback_items}
                    if live_items:
                        for sym, info in live_items.items():
                            info["reason"] = "🔴 LIVE: " + info["reason"]
                        items.update(live_items)
                    if items:
                        self.apply_news_sentiment(items)
                    live_total += len(live_items)
                    fallback_total += len(fallback_items)
                    # gentle pacing between chunks so we don't spam Claude
                    await asyncio.sleep(8)
                if live_total or fallback_total:
                    await self._broadcast({"type": "NEWS", "data": dict(self.reasons)})
                    await self._broadcast({"type": "PRICES", "data": self.all_prices()})
                logger.info(
                    "Full sweep done: %d live, %d fallback (%d total)",
                    live_total, fallback_total, live_total + fallback_total,
                )
                await asyncio.sleep(FULL_SWEEP_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Full sweep error: %s", e)
                await asyncio.sleep(120)

    # ---------- lifecycle ----------
    def start(self):
        if self._running:
            return
        self._running = True
        self.reprice_all()
        self._tasks.append(asyncio.create_task(self._algo_walk_loop()))
        self._tasks.append(asyncio.create_task(self._decay_loop()))
        self._tasks.append(asyncio.create_task(self._news_cycle_loop()))
        logger.info("Startup engine started (%d symbols)", len(STOCKS))

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except Exception:
                pass


# Singleton
engine = StartupEngine()
