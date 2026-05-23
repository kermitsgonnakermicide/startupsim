"""Shared state, collections and helpers — imported by every route module
so the app surface stays slim. Keeps the FastAPI route files free of
Mongo / engine boilerplate.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from auth_utils import hash_password
from data.stocks import STOCKS, STOCK_MAP, BASE_VALUATIONS, base_price  # noqa: F401 (re-exported)
from market_timing import force_market_open, session_info
from nse_fetcher import fetcher
from startup_engine import engine

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger("state")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

APPROVAL_DAYS = 10
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
STARTING_CASH = 500000.0  # SimRupees ₹S — every new user starts with ₹5,00,000

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[DB_NAME]

# Collections
users_col = db["users"]
portfolios_col = db["portfolios"]
holdings_col = db["holdings"]
transactions_col = db["transactions"]
watchlists_col = db["watchlists"]
alerts_col = db["alerts"]


# --------------------- Helpers ---------------------
def market_is_open() -> bool:
    if force_market_open():
        return True
    ms = fetcher.cache.market_status or session_info()
    return (ms.get("status") or "").upper() == "OPEN"


def ist_now_str() -> str:
    import pytz
    return datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d-%b-%Y %H:%M:%S")


def portfolio_doc(user_id: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "userId": user_id,
        "cash": STARTING_CASH,
        "resetCount": 0,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }


def is_user_active(user: dict) -> tuple[bool, str]:
    """Return (allowed, reason). Admin always allowed."""
    if user.get("isAdmin"):
        return True, ""
    status = user.get("status", "pending")
    if status == "pending":
        return False, "Your account is pending creator approval. You'll be notified once approved."
    if status == "rejected":
        return False, "Your application was not approved. You may submit a new application via the Apply tab."
    exp_iso = user.get("approvedUntil")
    if exp_iso:
        try:
            exp = datetime.fromisoformat(exp_iso)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                return False, "Your access has expired (10 days). Submit a new application via the Apply tab."
        except Exception:
            pass
    return True, ""


async def compute_portfolio(user_id: str) -> dict:
    port = await portfolios_col.find_one({"userId": user_id}, {"_id": 0})
    if not port:
        port = portfolio_doc(user_id)
        await portfolios_col.insert_one({**port})
    holdings = await holdings_col.find({"userId": user_id}, {"_id": 0}).to_list(500)
    prices = engine.all_prices()
    invested = 0.0
    current = 0.0
    day_change = 0.0
    enriched = []
    for h in holdings:
        pdata = prices.get(h["symbol"], {}) or {}
        ltp = pdata.get("price") or h["avgBuyPrice"]
        prev_close = pdata.get("close") or ltp
        curr_val = ltp * h["qty"]
        inv_val = h["avgBuyPrice"] * h["qty"]
        pnl = curr_val - inv_val
        pnl_pct = (pnl / inv_val * 100) if inv_val > 0 else 0
        day_change += (ltp - prev_close) * h["qty"]
        invested += inv_val
        current += curr_val
        enriched.append({
            **h,
            "ltp": round(ltp, 2),
            "currentValue": round(curr_val, 2),
            "pnl": round(pnl, 2),
            "pnlPct": round(pnl_pct, 2),
            "change": round(ltp - prev_close, 2),
        })
    total_value = port["cash"] + current
    total_pnl = total_value - STARTING_CASH
    total_pnl_pct = (total_pnl / STARTING_CASH) * 100
    return {
        "cash": round(port["cash"], 2),
        "holdings": enriched,
        "totalInvested": round(invested, 2),
        "holdingsValue": round(current, 2),
        "totalValue": round(total_value, 2),
        "totalPnl": round(total_pnl, 2),
        "totalPnlPct": round(total_pnl_pct, 2),
        "dayChange": round(day_change, 2),
        "resetCount": port.get("resetCount", 0),
    }


def user_app_view(u: dict) -> dict:
    return {
        "userId": u["id"],
        "username": u["username"],
        "email": u.get("email", ""),
        "reason": u.get("reason", ""),
        "status": u.get("status", "pending"),
        "isAdmin": bool(u.get("isAdmin", False)),
        "createdAt": u.get("createdAt"),
        "approvedAt": u.get("approvedAt"),
        "approvedUntil": u.get("approvedUntil"),
        "reappliedAt": u.get("reappliedAt"),
        "leaderboardHidden": bool(u.get("leaderboardHidden", False)),
    }


def badge_for(pct: float) -> str:
    if pct > 20:
        return "BULL"
    if pct >= 10:
        return "TRADER"
    if pct >= 0:
        return "HODLER"
    return "BEAR"


# --------------------- Migrations / Seeding ---------------------
async def ensure_indexes():
    try:
        await users_col.create_index("username_lc", unique=True, name="uniq_username_lc")
        await portfolios_col.create_index("userId", unique=True)
        await holdings_col.create_index([("userId", 1), ("symbol", 1)], unique=True)
        await watchlists_col.create_index([("userId", 1), ("symbol", 1)], unique=True)
        await alerts_col.create_index([("userId", 1), ("createdAt", -1)])
        await alerts_col.create_index([("symbol", 1), ("active", 1)])
    except Exception as e:
        logger.warning("Index creation warn: %s", e)


async def migrate_to_startupmarket():
    """One-time pivot: drop NSE-era fake leaderboard users, holdings/transactions/
    watchlists referencing dead NSE symbols, and reset every real user's portfolio
    cash. Idempotent — guarded by a marker doc in the migrations collection."""
    flag_col = db["migrations"]
    marker = await flag_col.find_one({"_id": "startupmarket_pivot_v1"})
    if marker:
        return
    fake_count = await portfolios_col.count_documents({"fake": True})
    await portfolios_col.delete_many({"fake": True})
    h = (await holdings_col.delete_many({})).deleted_count
    t = (await transactions_col.delete_many({})).deleted_count
    w = (await watchlists_col.delete_many({})).deleted_count
    p = (await portfolios_col.update_many({}, {"$set": {"cash": STARTING_CASH}})).modified_count
    await flag_col.insert_one({"_id": "startupmarket_pivot_v1", "appliedAt": datetime.now(timezone.utc).isoformat()})
    logger.info(
        "Startup pivot migration: dropped %d fake users, %d holdings, %d transactions, %d watchlists; reset cash on %d portfolios",
        fake_count, h, t, w, p,
    )


async def migrate_starting_cash_5lakh():
    """One-time top-up: raise every user's cash floor to ₹5,00,000."""
    flag_col = db["migrations"]
    marker = await flag_col.find_one({"_id": "starting_cash_5lakh_v1"})
    if marker:
        return
    res = await portfolios_col.update_many(
        {"cash": {"$lt": STARTING_CASH}},
        {"$set": {"cash": STARTING_CASH}},
    )
    await flag_col.insert_one({"_id": "starting_cash_5lakh_v1", "appliedAt": datetime.now(timezone.utc).isoformat()})
    logger.info("Starting-cash uplift migration: bumped %d portfolios to ₹5,00,000", res.modified_count)


async def seed_admin():
    """Seed the admin account on first boot if missing."""
    lc = ADMIN_USERNAME.lower()
    existing = await users_col.find_one({"username_lc": lc})
    if existing:
        logger.info("Admin user '%s' already exists. Ensuring isAdmin is True and status is approved.", ADMIN_USERNAME)
        await users_col.update_one(
            {"username_lc": lc},
            {"$set": {
                "isAdmin": True, 
                "status": "approved",
            }},
        )
        return
    user_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    await users_col.insert_one({
        "id": user_id,
        "username": ADMIN_USERNAME,
        "username_lc": lc,
        "passwordHash": hash_password(ADMIN_PASSWORD),
        "email": "admin@scale.local",
        "reason": "Creator account",
        "status": "approved",
        "isAdmin": True,
        "approvedAt": now_iso,
        "approvedUntil": None,
        "createdAt": now_iso,
    })
    await portfolios_col.insert_one(portfolio_doc(user_id))
    logger.info("Seeded admin user '%s'", ADMIN_USERNAME)


async def migrate_grandfather():
    """Grandfather existing users without a status field → approved with 10d expiry."""
    cursor = users_col.find({"status": {"$exists": False}}, {"_id": 0})
    n = 0
    async for u in cursor:
        try:
            created = datetime.fromisoformat(u["createdAt"]) if u.get("createdAt") else datetime.now(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except Exception:
            created = datetime.now(timezone.utc)
        approved_until = created + timedelta(days=APPROVAL_DAYS)
        await users_col.update_one(
            {"id": u["id"]},
            {"$set": {
                "status": "approved",
                "isAdmin": False,
                "approvedAt": created.isoformat(),
                "approvedUntil": approved_until.isoformat(),
                "email": u.get("email", ""),
                "reason": u.get("reason", "Grandfathered user"),
            }},
        )
        n += 1
    if n:
        logger.info("Grandfathered %d existing users (10-day expiry from signup)", n)
