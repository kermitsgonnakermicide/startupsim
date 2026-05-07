"""StartupMarket pivot — backend tests for /stocks, /demand, /prices, /trade,
/chart synthetic, /marketbot/chat, /marketbot/refresh-news, /leaderboard (no fakes)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = ("admin", "SCALEdaddySALLU67")
DEMO = ("demo_user", "demo123")


# ---------- helpers ----------
def login(username, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"login {username} failed: {r.status_code} {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def user_token():
    return login(*DEMO)


@pytest.fixture(scope="module")
def market_open():
    s = requests.get(f"{BASE_URL}/api/market-status", timeout=10).json()
    return (s.get("status") or "").upper() == "OPEN"


# ---------- /api/stocks ----------
def test_stocks_returns_90_startup_symbols():
    r = requests.get(f"{BASE_URL}/api/stocks", timeout=10)
    assert r.status_code == 200
    stocks = r.json()["stocks"]
    assert len(stocks) == 90, f"expected 90 startup symbols, got {len(stocks)}"
    syms = {s["symbol"] for s in stocks}
    # New universe
    for must in ("RZRPAY", "BHARATPE", "ZOHO", "CASHFREE", "PWALLAH"):
        assert must in syms, f"missing startup symbol {must}"
    # Old NSE universe must NOT be present
    for legacy in ("RELIANCE", "TCS", "INFY", "HDFCBANK"):
        assert legacy not in syms, f"NSE legacy symbol {legacy} still present"
    # All entries have a sector
    for s in stocks:
        assert s.get("sector"), f"{s['symbol']} missing sector"


# ---------- /api/demand ----------
def test_demand_no_auth_required_and_covers_all_90():
    r = requests.get(f"{BASE_URL}/api/demand", timeout=10)
    assert r.status_code == 200
    body = r.json()
    pressure = body["pressure"]
    assert isinstance(pressure, dict)
    assert len(pressure) == 90
    # all values numeric and within plausible band
    for k, v in pressure.items():
        assert isinstance(v, (int, float))
        assert -1.0 <= v <= 1.0


# ---------- /api/prices ----------
def test_prices_keyed_by_startup_symbol(user_token):
    r = requests.get(f"{BASE_URL}/api/prices", headers={"Authorization": f"Bearer {user_token}"}, timeout=10)
    # /prices is unauthenticated in this server but accept either
    assert r.status_code == 200
    prices = r.json()["prices"]
    assert "RZRPAY" in prices
    p = prices["RZRPAY"]
    assert "price" in p and 0.0001 < p["price"] < 1.0  # PRICE_FACTOR=1e-6, RZRPAY 54000cr → 0.054
    assert "demandPressure" in p
    assert p.get("sector") == "Fintech" or "sector" in p


# ---------- /api/trade ----------
def test_trade_blocked_when_market_closed(user_token, market_open):
    if market_open:
        pytest.skip("market is OPEN; cannot exercise closed-branch live")
    r = requests.post(
        f"{BASE_URL}/api/trade",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"symbol": "CASHFREE", "type": "BUY", "qty": 100, "price": 0.01},
        timeout=10,
    )
    assert r.status_code == 400
    detail = (r.json().get("detail") or "").lower()
    assert "trading is disabled" in detail and "closed" in detail


def test_trade_buy_moves_demand_positive(user_token, market_open):
    if not market_open:
        pytest.skip("market is CLOSED; cannot exercise BUY pressure live")
    sym = "CASHFREE"
    before = requests.get(f"{BASE_URL}/api/demand", timeout=10).json()["pressure"][sym]
    r = requests.post(
        f"{BASE_URL}/api/trade",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"symbol": sym, "type": "BUY", "qty": 1000, "price": 0.01},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    time.sleep(0.5)
    after = requests.get(f"{BASE_URL}/api/demand", timeout=10).json()["pressure"][sym]
    assert after > before, f"BUY should raise demand: {before} → {after}"


# ---------- /api/chart synthetic ----------
def test_chart_synthetic_for_startup_returns_78_candles(user_token):
    r = requests.get(
        f"{BASE_URL}/api/chart/RZRPAY?range=1d",
        headers={"Authorization": f"Bearer {user_token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["isSynthetic"] is True
    assert body["symbol"] == "RZRPAY"
    assert "valuation" in body and body["valuation"] == 54000
    assert "demandPressure" in body
    assert "narrative" in body  # may be None
    candles = body["candles"]
    assert len(candles) == 78
    for c in candles[:3]:
        for k in ("t", "o", "h", "l", "c", "v"):
            assert k in c


def test_chart_deterministic_per_symbol_range(user_token):
    h = {"Authorization": f"Bearer {user_token}"}
    r1 = requests.get(f"{BASE_URL}/api/chart/ZOHO?range=1d", headers=h, timeout=15).json()
    r2 = requests.get(f"{BASE_URL}/api/chart/ZOHO?range=1d", headers=h, timeout=15).json()
    # Last candle close is pinned to live last_real → may drift between calls;
    # but interior candles should be identical (deterministic seed)
    a = r1["candles"][:60]
    b = r2["candles"][:60]
    for x, y in zip(a, b):
        assert x["o"] == y["o"]
        assert x["c"] == y["c"]


# ---------- /api/marketbot/chat ----------
def test_marketbot_chat_requires_auth():
    r = requests.post(f"{BASE_URL}/api/marketbot/chat", json={"message": "hi"}, timeout=10)
    assert r.status_code in (401, 403)


def test_marketbot_chat_empty_message_400(user_token):
    r = requests.post(
        f"{BASE_URL}/api/marketbot/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "   "},
        timeout=10,
    )
    assert r.status_code == 400


def test_marketbot_chat_returns_reply_with_disclaimer(user_token):
    r = requests.post(
        f"{BASE_URL}/api/marketbot/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "What is Razorpay in one sentence?"},
        timeout=60,
    )
    if r.status_code == 503:
        pytest.skip("MarketBot 503 (LLM glitch) — retest later")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "reply" in body and isinstance(body["reply"], str) and len(body["reply"]) > 0
    assert "sessionId" in body
    assert "MarketBot estimate — for educational use only" in body["reply"], (
        f"reply missing required disclaimer suffix: {body['reply'][-200:]}"
    )


# ---------- /api/marketbot/refresh-news ----------
def test_refresh_news_admin_only(user_token):
    r = requests.post(
        f"{BASE_URL}/api/marketbot/refresh-news",
        headers={"Authorization": f"Bearer {user_token}"},
        timeout=10,
    )
    assert r.status_code == 403


def test_refresh_news_admin_returns_items(admin_token):
    r = requests.post(
        f"{BASE_URL}/api/marketbot/refresh-news",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=120,
    )
    if r.status_code in (502, 503, 504):
        pytest.skip(f"LLM news refresh transient {r.status_code}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "applied" in body and isinstance(body["applied"], int)
    assert "items" in body and isinstance(body["items"], dict)


# ---------- /api/leaderboard — no fake users ----------
def test_leaderboard_has_no_fake_users(user_token):
    r = requests.get(
        f"{BASE_URL}/api/leaderboard",
        headers={"Authorization": f"Bearer {user_token}"},
        timeout=10,
    )
    assert r.status_code == 200
    rows = r.json().get("rows", [])
    for row in rows:
        assert row.get("fake") is False, f"fake user found: {row}"
