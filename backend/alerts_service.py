"""Threshold price alerts on watchlisted (or any) startup symbols.

User creates an alert: { symbol, targetPrice, direction: 'above'|'below' }.
The startup engine calls `alerts_service.check(symbol, new_price)` on every
reprice; any active alert whose target has been crossed is marked triggered
in Mongo and broadcast over WebSocket to the owning user.

In-memory index keeps the hot path (per-tick check) O(n_active_alerts_for_symbol)
so we don't slam Mongo on every tick.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger("alerts_service")


class AlertsService:
    def __init__(self):
        self._col = None
        # symbol -> list of alert dicts (active only)
        self._by_symbol: dict[str, list[dict]] = defaultdict(list)
        # userId -> asyncio.Queue for WS fan-out
        self._user_queues: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()

    def bind(self, alerts_col, loop: asyncio.AbstractEventLoop):
        self._col = alerts_col
        self._loop = loop

    async def load(self):
        """Warm the in-memory index from Mongo at startup."""
        self._by_symbol.clear()
        if self._col is None:
            return
        async for a in self._col.find({"active": True}, {"_id": 0}):
            self._by_symbol[a["symbol"]].append(a)
        logger.info(
            "Loaded %d active alerts across %d symbols",
            sum(len(v) for v in self._by_symbol.values()), len(self._by_symbol),
        )

    # --------- WS fan-out ---------
    def subscribe(self, user_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._user_queues[user_id].add(q)
        return q

    def unsubscribe(self, user_id: str, q: asyncio.Queue):
        s = self._user_queues.get(user_id)
        if s:
            s.discard(q)
            if not s:
                self._user_queues.pop(user_id, None)

    def _dispatch(self, user_id: str, msg: dict):
        for q in list(self._user_queues.get(user_id, ())):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    # --------- CRUD ---------
    async def list_for(self, user_id: str) -> list[dict]:
        if self._col is None:
            return []
        rows = await self._col.find({"userId": user_id}, {"_id": 0}).sort("createdAt", -1).to_list(500)
        return rows

    async def create(self, user_id: str, symbol: str, target: float, direction: str, note: str = "") -> dict:
        assert direction in ("above", "below")
        alert = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "symbol": symbol,
            "targetPrice": round(float(target), 4),
            "direction": direction,
            "note": (note or "")[:200],
            "active": True,
            "triggered": False,
            "triggeredAt": None,
            "triggeredPrice": None,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        if self._col is not None:
            await self._col.insert_one(dict(alert))
        async with self._lock:
            self._by_symbol[symbol].append(dict(alert))
        return alert

    async def delete(self, user_id: str, alert_id: str) -> bool:
        if self._col is None:
            return False
        res = await self._col.delete_one({"id": alert_id, "userId": user_id})
        # remove from memory index
        async with self._lock:
            for sym, lst in list(self._by_symbol.items()):
                self._by_symbol[sym] = [a for a in lst if a["id"] != alert_id]
        return res.deleted_count > 0

    # --------- hot path ---------
    def check(self, symbol: str, prev_price: Optional[float], new_price: float):
        """Synchronous crossing check — called from the engine reprice.
        Triggers = direction=='above' and new_price >= target and (prev_price is None or prev_price < target);
                   direction=='below' and new_price <= target and (prev_price is None or prev_price > target).
        """
        bucket = self._by_symbol.get(symbol)
        if not bucket:
            return
        triggered: list[dict] = []
        survivors: list[dict] = []
        for a in bucket:
            if not a.get("active"):
                continue
            tp = a["targetPrice"]
            if a["direction"] == "above":
                crossed = new_price >= tp and (prev_price is None or prev_price < tp)
            else:
                crossed = new_price <= tp and (prev_price is None or prev_price > tp)
            if crossed:
                triggered.append(a)
            else:
                survivors.append(a)
        if not triggered:
            return
        self._by_symbol[symbol] = survivors
        ts = datetime.now(timezone.utc).isoformat()
        for a in triggered:
            a["active"] = False
            a["triggered"] = True
            a["triggeredAt"] = ts
            a["triggeredPrice"] = round(new_price, 4)
            # dispatch WS event to the owning user
            self._dispatch(a["userId"], {
                "type": "ALERT",
                "alert": {
                    "id": a["id"],
                    "symbol": a["symbol"],
                    "targetPrice": a["targetPrice"],
                    "direction": a["direction"],
                    "triggeredPrice": a["triggeredPrice"],
                    "triggeredAt": ts,
                    "note": a.get("note", ""),
                },
            })
            # persist the flip (fire-and-forget on the engine loop)
            if self._col is not None and self._loop is not None:
                async def _mark(a=a, ts=ts):
                    try:
                        await self._col.update_one(
                            {"id": a["id"]},
                            {"$set": {
                                "active": False,
                                "triggered": True,
                                "triggeredAt": ts,
                                "triggeredPrice": a["triggeredPrice"],
                            }},
                        )
                    except Exception as e:
                        logger.warning("alert persist failed: %s", e)
                asyncio.run_coroutine_threadsafe(_mark(), self._loop)


alerts_service = AlertsService()
