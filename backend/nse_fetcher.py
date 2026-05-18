"""
NSE price fetcher with Yahoo Finance fallback and an in-memory cache.

Strategy:
- Try NSE first (session cookies + quote-equity endpoint) in batches of 5 with 1.2s delays.
- On any NSE failure for a symbol, fall back to Yahoo Finance (free, unauthenticated).
- Maintain in-memory price map + last 30 ticks per symbol (for sparklines).
- Broadcast snapshots + ticks over a registered asyncio queue (WebSocket fan-out).
- Refresh NSE session every 25 minutes.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime
from typing import Any

import httpx
import pytz

from data.stocks import STOCKS, STOCK_MAP
from market_timing import force_market_open, session_info

logger = logging.getLogger("nse_fetcher")

IST = pytz.timezone("Asia/Kolkata")
NSE_BASE = "https://www.nseindia.com"
NSE_HOME = NSE_BASE + "/"
NSE_WARMUP = NSE_BASE + "/market-data/live-equity-market"
NSE_QUOTE = NSE_BASE + "/api/quote-equity?symbol={symbol}"
NSE_MARKET_STATUS = NSE_BASE + "/api/marketStatus"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

NSE_HEADERS_HTML = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

NSE_HEADERS_API = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_BASE + "/",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
}

YAHOO_QUOTE = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?interval=1d&range=5d"
)


class PriceCache:
    def __init__(self):
        # symbol -> {price, open, high, low, close, change, changePct, volume,
        #            weekHigh52, weekLow52, lastUpdated, source}
        self.prices: dict[str, dict[str, Any]] = {}
        # symbol -> deque[last 30 prices]
        self.sparks: dict[str, deque] = {s["symbol"]: deque(maxlen=30) for s in STOCKS}
        # last 50 tick events per symbol
        self.tick_history: dict[str, deque] = {s["symbol"]: deque(maxlen=50) for s in STOCKS}
        self.market_status: dict[str, Any] = {}
        self.last_full_update: float | None = None
        self.indices: dict[str, dict[str, Any]] = {}  # name -> {last, open, previousClose, percentChange, ...}

    def get(self, symbol: str) -> dict | None:
        return self.prices.get(symbol)

    def all(self) -> dict[str, dict[str, Any]]:
        return dict(self.prices)

    def record(self, symbol: str, data: dict[str, Any]) -> dict | None:
        """Update cache. Return tick event dict if price changed, else None."""
        prev = self.prices.get(symbol)
        self.prices[symbol] = data
        price = data["price"]
        self.sparks[symbol].append(price)
        if prev and prev.get("price") != price:
            ev = {
                "symbol": symbol,
                "oldPrice": prev["price"],
                "newPrice": price,
                "change": data.get("change"),
                "changePct": data.get("changePct"),
                "lastUpdated": data.get("lastUpdated"),
            }
            self.tick_history[symbol].append(ev)
            return ev
        return None

    def spark_data(self, symbol: str) -> list[float]:
        return list(self.sparks.get(symbol, []))


class NSEFetcher:
    def __init__(self):
        self.cache = PriceCache()
        self._cookies: httpx.Cookies | None = None
        self._session_ts: float | None = None
        self._subscribers: set[asyncio.Queue] = set()
        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ---------- subscribers (WebSockets) ----------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

    async def _broadcast(self, message: dict):
        dead = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    # ---------- session ----------
    async def _init_session(self, client: httpx.AsyncClient):
        try:
            r = await client.get(NSE_HOME, headers=NSE_HEADERS_HTML, timeout=12.0)
            self._cookies = r.cookies
            try:
                await client.get(NSE_WARMUP, headers=NSE_HEADERS_HTML, timeout=12.0)
            except Exception:
                pass
            self._session_ts = time.time()
            logger.info("NSE session initialised (%d cookies)", len(self._cookies or {}))
        except Exception as e:
            logger.warning("NSE session init failed: %s", e)
            self._cookies = None

    def _session_stale(self) -> bool:
        if self._session_ts is None:
            return True
        return (time.time() - self._session_ts) > 25 * 60

    # ---------- single-symbol fetch ----------
    async def _fetch_nse(self, client: httpx.AsyncClient, symbol: str) -> dict | None:
        try:
            r = await client.get(
                NSE_QUOTE.format(symbol=symbol),
                headers=NSE_HEADERS_API,
                timeout=10.0,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            pi = data.get("priceInfo") or {}
            mdob = data.get("marketDeptOrderBook") or {}
            ti = mdob.get("tradeInfo") or {}
            meta = data.get("metadata") or {}
            price = pi.get("lastPrice")
            if price is None:
                return None
            ihl = pi.get("intraDayHighLow") or {}
            whl = pi.get("weekHighLow") or {}
            return {
                "symbol": symbol,
                "price": float(price),
                "open": _num(pi.get("open")),
                "high": _num(ihl.get("max")),
                "low": _num(ihl.get("min")),
                "close": _num(pi.get("previousClose")),
                "change": _num(pi.get("change")),
                "changePct": _num(pi.get("pChange")),
                "volume": _num(ti.get("totalTradedVolume")),
                "weekHigh52": _num(whl.get("max")),
                "weekLow52": _num(whl.get("min")),
                "lastUpdated": meta.get("lastUpdateTime") or _ist_now_str(),
                "source": "NSE",
            }
        except Exception as e:
            logger.debug("NSE fetch %s failed: %s", symbol, e)
            return None

    async def _fetch_yahoo(self, client: httpx.AsyncClient, symbol: str) -> dict | None:
        # Yahoo uses different symbol for M&M
        y_sym = symbol.replace("&", "%26")
        try:
            r = await client.get(
                YAHOO_QUOTE.format(symbol=y_sym),
                headers={"User-Agent": UA, "Accept": "application/json"},
                timeout=10.0,
            )
            if r.status_code != 200:
                return None
            j = r.json()
            res = (j.get("chart") or {}).get("result") or []
            if not res:
                return None
            meta = res[0].get("meta") or {}
            price = meta.get("regularMarketPrice")
            if price is None:
                return None
            prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
            change = price - prev
            change_pct = (change / prev * 100) if prev else 0
            return {
                "symbol": symbol,
                "price": float(price),
                "open": _num(meta.get("regularMarketDayOpen") or meta.get("chartPreviousClose")),
                "high": _num(meta.get("regularMarketDayHigh")),
                "low": _num(meta.get("regularMarketDayLow")),
                "close": _num(prev),
                "change": round(change, 2),
                "changePct": round(change_pct, 2),
                "volume": _num(meta.get("regularMarketVolume")),
                "weekHigh52": _num(meta.get("fiftyTwoWeekHigh")),
                "weekLow52": _num(meta.get("fiftyTwoWeekLow")),
                "lastUpdated": _ist_now_str(),
                "source": "Yahoo",
            }
        except Exception as e:
            logger.debug("Yahoo fetch %s failed: %s", symbol, e)
            return None

    async def _fetch_one(self, client: httpx.AsyncClient, symbol: str) -> dict | None:
        data = await self._fetch_nse(client, symbol)
        if data:
            return data
        return await self._fetch_yahoo(client, symbol)

    # ---------- batched cycle ----------
    async def _run_cycle(self, client: httpx.AsyncClient):
        if self._session_stale():
            await self._init_session(client)
        client.cookies = self._cookies or httpx.Cookies()

        batch_size = 5
        gap = 1.2
        symbols = [s["symbol"] for s in STOCKS]
        ticks: list[dict] = []

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            results = await asyncio.gather(
                *(self._fetch_one(client, sym) for sym in batch),
                return_exceptions=True,
            )
            for sym, res in zip(batch, results):
                if isinstance(res, Exception) or not res:
                    continue
                meta = STOCK_MAP.get(sym, {})
                res["name"] = meta.get("name", sym)
                res["sector"] = meta.get("sector", "Other")
                ev = self.cache.record(sym, res)
                if ev:
                    ticks.append(ev)
            await asyncio.sleep(gap)

        self.cache.last_full_update = time.time()

        # broadcast snapshot
        await self._broadcast({"type": "PRICES", "data": self.cache.all()})
        for ev in ticks[:40]:
            await self._broadcast({"type": "TICK", **ev})

    async def _run_market_status(self, client: httpx.AsyncClient):
        info = session_info()
        nse_state = None
        try:
            r = await client.get(
                NSE_MARKET_STATUS, headers=NSE_HEADERS_API, timeout=8.0,
                cookies=self._cookies or None,
            )
            if r.status_code == 200:
                data = r.json()
                for m in data.get("marketState", []) or []:
                    if m.get("market") == "Capital Market":
                        nse_state = m
                        break
        except Exception as e:
            logger.debug("NSE marketStatus failed: %s", e)

        status = {
            **info,
            "nseMarketStatus": (nse_state or {}).get("marketStatus"),
            "nseMarketStatusMessage": (nse_state or {}).get("marketStatusMessage"),
            "tradeDate": (nse_state or {}).get("tradeDate"),
            "index": (nse_state or {}).get("index"),
            "lastFetchedAt": _ist_now_str(),
        }
        # NSE is the source of truth for open/closed. If NSE says Close
        # (e.g., trading holiday like Labour Day, Republic Day, etc.)
        # override the time-based session to CLOSED.
        nse_ms = (status.get("nseMarketStatus") or "").strip().lower()
        if nse_ms == "close" and status["status"] == "OPEN" and not force_market_open():
            status["status"] = "CLOSED"
            status["sessionType"] = "CLOSED"
            status["holidayOverride"] = True
            status["countdownLabel"] = None
            # Next open = next weekday at 09:15, but NSE may still be closed.
            # Best-effort: leave nextOpen as weekday 9:15 (already computed if present).
        elif nse_ms == "open" and status["status"] == "CLOSED":
            # Rare: NSE says open but our time calc says closed (ignore).
            pass
        self.cache.market_status = status
        await self._broadcast({"type": "MARKET_STATUS", "data": status})

        # Also fetch NSE indices
        try:
            r = await client.get(
                NSE_BASE + "/api/allIndices",
                headers=NSE_HEADERS_API, timeout=8.0,
                cookies=self._cookies or None,
            )
            if r.status_code == 200:
                j = r.json()
                wanted = {"NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY NEXT 50", "INDIA VIX"}
                idx: dict[str, dict[str, Any]] = {}
                for x in j.get("data", []) or []:
                    name = x.get("index")
                    if name in wanted:
                        idx[name] = {
                            "name": name,
                            "last": _num(x.get("last")),
                            "open": _num(x.get("open")),
                            "previousClose": _num(x.get("previousClose")),
                            "high": _num(x.get("high")),
                            "low": _num(x.get("low")),
                            "change": _num(x.get("variation")),
                            "changePct": _num(x.get("percentChange")),
                        }
                # SENSEX via Yahoo (BSE index, not in NSE allIndices)
                try:
                    yr = await client.get(
                        "https://query1.finance.yahoo.com/v8/finance/chart/%5EBSESN?interval=1d&range=1d",
                        headers={"User-Agent": UA, "Accept": "application/json"},
                        timeout=8.0,
                    )
                    if yr.status_code == 200:
                        yj = yr.json()
                        res = (yj.get("chart") or {}).get("result") or []
                        if res:
                            meta = res[0].get("meta") or {}
                            last = _num(meta.get("regularMarketPrice"))
                            prev = _num(meta.get("chartPreviousClose") or meta.get("previousClose"))
                            if last is not None:
                                change = last - (prev or last)
                                chg_pct = (change / prev * 100) if prev else 0
                                idx["SENSEX"] = {
                                    "name": "SENSEX",
                                    "last": last,
                                    "open": _num(meta.get("regularMarketDayOpen")),
                                    "previousClose": prev,
                                    "high": _num(meta.get("regularMarketDayHigh")),
                                    "low": _num(meta.get("regularMarketDayLow")),
                                    "change": round(change, 2),
                                    "changePct": round(chg_pct, 2),
                                }
                except Exception as ye:
                    logger.debug("Yahoo SENSEX failed: %s", ye)
                if idx:
                    self.cache.indices = idx
                    await self._broadcast({"type": "INDICES", "data": idx})
        except Exception as e:
            logger.debug("NSE indices failed: %s", e)

    async def _main_loop(self):
        async with httpx.AsyncClient(follow_redirects=True, http2=False) as client:
            await self._init_session(client)
            try:
                # StartupMarket: skip per-symbol NSE quote cycle; only need market status
                await self._run_market_status(client)
            except Exception as e:
                logger.exception("First market-status error: %s", e)
            while self._running:
                try:
                    await asyncio.sleep(60)
                    await self._run_market_status(client)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception("Market-status cycle error: %s", e)
                    await asyncio.sleep(5)

    def start(self):
        if self._running:
            return
        self._running = True
        self._tasks.append(asyncio.create_task(self._main_loop()))
        logger.info("NSE fetcher started")

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except Exception:
                pass


def _num(v) -> float | None:
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(v)
    except Exception:
        return None


def _ist_now_str() -> str:
    return datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S")


# Singleton
fetcher = NSEFetcher()
