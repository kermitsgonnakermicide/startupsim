"""SCALE India Investment — FastAPI app entrypoint.

This file is intentionally slim: lifespan + middleware + WebSocket + the
email-action HTML endpoint + router includes. All HTTP route handlers live
under `/app/backend/routes/`.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware

from alerts_service import alerts_service
from auth_utils import decode_token
from emailer import (
    fire_and_forget, notify_user_approved, notify_user_rejected, verify_action_token,
)
import marketbot
from market_timing import session_info
from news_feeds import news_feeds
from nse_fetcher import fetcher
from startup_engine import engine
from state import (
    APPROVAL_DAYS, alerts_col, ensure_indexes, market_is_open, mongo_client,
    migrate_grandfather, migrate_starting_cash_5lakh, migrate_to_startupmarket,
    seed_admin, users_col,
)

# Routers
from routes.admin import router as admin_router
from routes.alerts import router as alerts_router
from routes.auth import router as auth_router
from routes.backup import auto_backup_loop, router as backup_router
from routes.chart import router as chart_router
from routes.leaderboard import router as leaderboard_router
from routes.market import router as market_router
from routes.marketbot import router as marketbot_router
from routes.news import router as news_router
from routes.trade import router as trade_router
from routes.watchlist import router as watchlist_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("server")


# --------------------- Lifespan ---------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    # one-time pivot migration: clear NSE-era fake users + invalid holdings
    await migrate_to_startupmarket()
    # one-time top-up: bump everyone to ₹5,00,000 starting cash
    await migrate_starting_cash_5lakh()
    # seed admin
    await seed_admin()
    # grandfather existing users without approval fields
    await migrate_grandfather()
    # start fetcher (kept for real market open/close timing — quote cycle is now disabled)
    fetcher.start()
    # start live-news scraper (national Indian publications)
    news_feeds.start()
    # start startup price engine
    engine.set_market_open_fn(market_is_open)
    engine.set_news_fetcher(marketbot.fetch_news_sentiment)
    engine.set_live_news(marketbot.fetch_live_news_sentiment, news_feeds.find_for)
    # wire price alerts
    alerts_service.bind(alerts_col, asyncio.get_running_loop())
    await alerts_service.load()
    engine.set_alert_check(alerts_service.check)
    engine.start()
    # start periodic auto-backup (every 30 minutes)
    backup_task = asyncio.create_task(auto_backup_loop())
    yield
    backup_task.cancel()
    await fetcher.stop()
    await news_feeds.stop()
    await engine.stop()
    mongo_client.close()


app = FastAPI(lifespan=lifespan)

# Mount all routers
for _r in (
    auth_router, backup_router, market_router, trade_router, watchlist_router,
    alerts_router, leaderboard_router, admin_router, chart_router,
    marketbot_router, news_router,
):
    app.include_router(_r)


# --------------------- One-click Admin action (from email) ---------------------
def _action_html(title: str, message: str, color: str = "#00d4aa") -> str:
    url = os.environ.get("PUBLIC_APP_URL", "")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>SCALE · {title}</title>
<style>
body{{background:#0a0e1a;color:#e2e8f0;font-family:Inter,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}}
.card{{background:#111827;border:1px solid #1e293b;border-radius:14px;padding:36px;max-width:480px;width:100%;text-align:center;box-shadow:0 24px 60px rgba(0,0,0,.6);}}
h1{{color:{color};font-size:22px;margin:0 0 10px;}}
p{{color:#94a3b8;font-size:14px;line-height:1.5;}}
.brand{{font-family:'JetBrains Mono',monospace;color:#a01e20;font-size:22px;font-weight:700;margin-bottom:18px;letter-spacing:-0.02em;}}
.sub{{color:#94a3b8;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:22px;}}
a.btn{{display:inline-block;margin-top:18px;background:#a01e20;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;}}
</style></head><body>
<div class="card">
<div class="brand">SCALE</div>
<div class="sub">India Investment</div>
<h1>{title}</h1>
<p>{message}</p>
<a class="btn" href="{url}">Open SCALE →</a>
</div></body></html>"""


@app.get("/api/admin/action")
async def admin_action_one_click(token: str = Query(...)):
    """One-click approve/reject from email. Returns an HTML page."""
    from fastapi.responses import HTMLResponse
    try:
        data = verify_action_token(token)
    except Exception:
        return HTMLResponse(_action_html("Link invalid or expired", "This approval link is no longer valid. Please use the Admin tab.", "#f03e3e"), status_code=400)
    user_id = data["uid"]
    action = data["act"]
    user = await users_col.find_one({"id": user_id})
    if not user:
        return HTMLResponse(_action_html("User not found", "This user no longer exists.", "#f03e3e"), status_code=404)
    if user.get("isAdmin"):
        return HTMLResponse(_action_html("Not allowed", "You cannot modify the admin account.", "#f03e3e"), status_code=400)
    current_status = user.get("status")
    if action == "approve":
        if current_status == "approved":
            return HTMLResponse(_action_html("Already approved", f"@{user['username']} is already approved.", "#00d4aa"))
        now = datetime.now(timezone.utc)
        until = now + timedelta(days=APPROVAL_DAYS)
        await users_col.update_one(
            {"id": user_id},
            {"$set": {"status": "approved", "approvedAt": now.isoformat(), "approvedUntil": until.isoformat()}},
        )
        fire_and_forget(notify_user_approved(user.get("email", ""), user["username"], until.isoformat()))
        return HTMLResponse(_action_html("Approved ✓", f"@{user['username']} now has 10-day access. Email sent.", "#00d4aa"))
    elif action == "reject":
        if current_status == "rejected":
            return HTMLResponse(_action_html("Already rejected", f"@{user['username']} was already rejected.", "#f03e3e"))
        await users_col.update_one(
            {"id": user_id},
            {"$set": {"status": "rejected", "approvedAt": None, "approvedUntil": None}},
        )
        fire_and_forget(notify_user_rejected(user.get("email", ""), user["username"]))
        return HTMLResponse(_action_html("Rejected", f"@{user['username']} has been rejected. Email sent.", "#f03e3e"))
    return HTMLResponse(_action_html("Unknown action", "Invalid action in link.", "#f03e3e"), status_code=400)


# --------------------- WebSocket ---------------------
@app.websocket("/api/ws")
async def ws_endpoint(ws: WebSocket, token: Optional[str] = Query(None)):
    if not token:
        await ws.close(code=4401)
        return
    try:
        payload = decode_token(token)
    except HTTPException:
        await ws.close(code=4401)
        return
    user_id = payload.get("userId")
    await ws.accept()
    q_eng = engine.subscribe()
    q_mkt = fetcher.subscribe()
    q_alert = alerts_service.subscribe(user_id) if user_id else None
    try:
        await ws.send_json({"type": "PRICES", "data": engine.all_prices()})
        await ws.send_json({"type": "MARKET_STATUS", "data": fetcher.cache.market_status or session_info()})

        async def relay(q):
            while True:
                msg = await q.get()
                if msg.get("type") in ("PRICES", "TICK", "MARKET_STATUS", "NEWS", "ALERT"):
                    await ws.send_json(msg)

        relays = [asyncio.create_task(relay(q_eng)), asyncio.create_task(relay(q_mkt))]
        if q_alert is not None:
            relays.append(asyncio.create_task(relay(q_alert)))
        done, pending = await asyncio.wait(relays, return_when=asyncio.FIRST_EXCEPTION)
        for t in pending:
            t.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WS error: %s", e)
    finally:
        engine.unsubscribe(q_eng)
        fetcher.unsubscribe(q_mkt)
        if q_alert is not None and user_id:
            alerts_service.unsubscribe(user_id, q_alert)


# --------------------- Boilerplate ---------------------
@app.get("/api/")
async def root():
    return {"app": "SCALE India Investment", "status": "ok"}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("Incoming request: %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        logger.info("Response: %s %s -> status %d", request.method, request.url.path, response.status_code)
        return response
    except Exception as e:
        logger.error("Request failed: %s %s -> %s", request.method, request.url.path, e)
        raise

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
