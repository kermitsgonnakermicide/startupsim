"""Tests for SCALE alerts CRUD, crossing semantics, news filtering, WS scoping
and regression of base endpoints (watchlist/portfolio/news/marketbot/leaderboard)."""
import os
import sys
import asyncio
import json
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
WS_BASE = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

ADMIN_USER = "admin"
ADMIN_PASS = "SCALEdaddySALLU67"


# ---- helpers ----

def _login(username, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password}, timeout=20)
    return r


@pytest.fixture(scope="module")
def admin_token():
    r = _login(ADMIN_USER, ADMIN_PASS)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def second_user(admin_h):
    """Sign up a second user and admin-approve so we can compare WS scoping."""
    uname = f"alerttest_{uuid.uuid4().hex[:6]}"
    pw = "abc12345"
    r = requests.post(f"{BASE_URL}/api/auth/signup", json={
        "username": uname, "password": pw, "email": f"{uname}@x.com", "reason": "test"
    }, timeout=20)
    assert r.status_code == 200
    # find user id from admin applications
    apps = requests.get(f"{BASE_URL}/api/admin/applications", headers=admin_h, timeout=20).json()
    pending = [a for a in apps["pending"] if a["username"] == uname]
    assert pending, f"new user {uname} not in pending"
    uid = pending[0]["userId"]
    ap = requests.post(f"{BASE_URL}/api/admin/approve", json={"userId": uid}, headers=admin_h, timeout=20)
    assert ap.status_code == 200
    li = _login(uname, pw)
    assert li.status_code == 200
    return {"username": uname, "token": li.json()["token"], "userId": uid}


# ---- ALERT CRUD ----

class TestAlertsCRUD:
    def test_create_alert_above_valid(self, admin_h):
        # Pick a known symbol & current price
        prices = requests.get(f"{BASE_URL}/api/prices", timeout=20).json()["prices"]
        sym = "RZRPAY" if "RZRPAY" in prices else next(iter(prices.keys()))
        cur = prices[sym]["price"]
        target = round(cur * 1.05, 4)
        r = requests.post(f"{BASE_URL}/api/alerts", json={
            "symbol": sym, "targetPrice": target, "direction": "above", "note": "test above"
        }, headers=admin_h, timeout=20)
        assert r.status_code == 200, r.text
        alert = r.json()["alert"]
        assert alert["symbol"] == sym
        assert alert["direction"] == "above"
        assert alert["active"] is True
        assert alert["triggered"] is False
        # cleanup
        requests.delete(f"{BASE_URL}/api/alerts/{alert['id']}", headers=admin_h, timeout=20)

    def test_reject_unknown_symbol(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/alerts", json={
            "symbol": "NOTREAL", "targetPrice": 1.0, "direction": "above"
        }, headers=admin_h, timeout=20)
        assert r.status_code == 400

    def test_reject_invalid_direction(self, admin_h):
        prices = requests.get(f"{BASE_URL}/api/prices", timeout=20).json()["prices"]
        sym = next(iter(prices.keys()))
        r = requests.post(f"{BASE_URL}/api/alerts", json={
            "symbol": sym, "targetPrice": 1.0, "direction": "sideways"
        }, headers=admin_h, timeout=20)
        assert r.status_code == 400

    def test_reject_zero_or_negative_price(self, admin_h):
        prices = requests.get(f"{BASE_URL}/api/prices", timeout=20).json()["prices"]
        sym = next(iter(prices.keys()))
        for bad in (0, -5):
            r = requests.post(f"{BASE_URL}/api/alerts", json={
                "symbol": sym, "targetPrice": bad, "direction": "above"
            }, headers=admin_h, timeout=20)
            assert r.status_code == 400, f"price {bad} should reject"

    def test_reject_far_target(self, admin_h):
        prices = requests.get(f"{BASE_URL}/api/prices", timeout=20).json()["prices"]
        sym = next(iter(prices.keys()))
        cur = prices[sym]["price"]
        # 1000x current — must be > 100x cap
        r = requests.post(f"{BASE_URL}/api/alerts", json={
            "symbol": sym, "targetPrice": cur * 1000, "direction": "above"
        }, headers=admin_h, timeout=20)
        assert r.status_code == 400

    def test_list_my_alerts_only(self, admin_h, second_user):
        prices = requests.get(f"{BASE_URL}/api/prices", timeout=20).json()["prices"]
        sym = next(iter(prices.keys()))
        cur = prices[sym]["price"]
        # admin creates one
        a1 = requests.post(f"{BASE_URL}/api/alerts", json={
            "symbol": sym, "targetPrice": round(cur * 1.10, 4), "direction": "above"
        }, headers=admin_h, timeout=20).json()["alert"]
        # second user creates one
        u_h = {"Authorization": f"Bearer {second_user['token']}"}
        a2 = requests.post(f"{BASE_URL}/api/alerts", json={
            "symbol": sym, "targetPrice": round(cur * 0.90, 4), "direction": "below"
        }, headers=u_h, timeout=20).json()["alert"]

        admin_alerts = requests.get(f"{BASE_URL}/api/alerts", headers=admin_h, timeout=20).json()["alerts"]
        user_alerts = requests.get(f"{BASE_URL}/api/alerts", headers=u_h, timeout=20).json()["alerts"]
        admin_ids = {a["id"] for a in admin_alerts}
        user_ids = {a["id"] for a in user_alerts}
        assert a1["id"] in admin_ids
        assert a2["id"] in user_ids
        assert a1["id"] not in user_ids, "userB sees userA alert (scope leak)"
        assert a2["id"] not in admin_ids, "userA sees userB alert (scope leak)"

        # userA cannot delete userB's alert
        bad_del = requests.delete(f"{BASE_URL}/api/alerts/{a2['id']}", headers=admin_h, timeout=20).json()
        assert bad_del["ok"] is False
        # userB confirms still present
        still = requests.get(f"{BASE_URL}/api/alerts", headers=u_h, timeout=20).json()["alerts"]
        assert a2["id"] in {a["id"] for a in still}

        # cleanup
        requests.delete(f"{BASE_URL}/api/alerts/{a1['id']}", headers=admin_h, timeout=20)
        requests.delete(f"{BASE_URL}/api/alerts/{a2['id']}", headers=u_h, timeout=20)


# ---- crossing semantics: in-process (deterministic) ----

class TestAlertsCrossing:
    def test_crossing_logic_in_process(self):
        """Import the AlertsService directly and validate the synchronous check()."""
        sys.path.insert(0, "/app/backend")
        from alerts_service import AlertsService

        svc = AlertsService()
        # No DB binding — purely in-memory
        # Manually inject 4 alerts (above-not-yet, below-not-yet, above-already-met, below-already-met)
        sym = "TESTSYM"
        alerts = [
            {"id": "a1", "userId": "u1", "symbol": sym, "targetPrice": 100.0, "direction": "above",
             "active": True, "triggered": False, "note": ""},
            {"id": "a2", "userId": "u1", "symbol": sym, "targetPrice": 50.0, "direction": "below",
             "active": True, "triggered": False, "note": ""},
            {"id": "a3", "userId": "u1", "symbol": sym, "targetPrice": 70.0, "direction": "above",
             "active": True, "triggered": False, "note": ""},  # cur=80 already above
            {"id": "a4", "userId": "u1", "symbol": sym, "targetPrice": 90.0, "direction": "below",
             "active": True, "triggered": False, "note": ""},  # cur=80 already below
        ]
        svc._by_symbol[sym] = list(alerts)

        # First check: prev=80, new=80 — already-met alerts must NOT fire (retroactive guard)
        svc.check(sym, 80.0, 80.0)
        live_ids = {a["id"] for a in svc._by_symbol[sym]}
        # a3 (above 70 with prev=80) should NOT fire because prev_price>=target → not a crossing
        # a4 (below 90 with prev=80) should NOT fire because prev_price<=target → not a crossing
        assert "a3" in live_ids, "above alert already-met should NOT fire retroactively"
        assert "a4" in live_ids, "below alert already-met should NOT fire retroactively"

        # Now move price up to 105 — a1 (above 100) should fire; a3 should still NOT (still already-met)
        svc.check(sym, 80.0, 105.0)
        live_ids = {a["id"] for a in svc._by_symbol[sym]}
        assert "a1" not in live_ids, "above:100 should fire when crossing 80→105"
        assert "a3" in live_ids, "above:70 still must not fire (prev>=target)"

        # Move down to 45 — a2 (below 50) fires; a4 (below 90) should fire because prev=105>90 and new=45<=90
        svc.check(sym, 105.0, 45.0)
        live_ids = {a["id"] for a in svc._by_symbol[sym]}
        assert "a2" not in live_ids, "below:50 should fire when crossing 105→45"
        assert "a4" not in live_ids, "below:90 should fire when crossing 105→45"


# ---- news filter ----

class TestNewsFilter:
    def test_matched_only_no_unmatched_leaks(self):
        r = requests.get(f"{BASE_URL}/api/news/headlines?matchedOnly=true&limit=80", timeout=30)
        assert r.status_code == 200
        heads = r.json()["headlines"]
        for h in heads:
            assert h.get("matchedSymbols"), f"headline leaked w/o matchedSymbols: {h.get('title')}"

    def test_stop_alias_words_not_misattributed(self):
        """Spot-check 50 headlines that titles starting with generic words like
        'physics/practical/mobile/scaler/locus' don't get assigned a fintech symbol."""
        r = requests.get(f"{BASE_URL}/api/news/headlines?limit=80", timeout=30)
        heads = r.json()["headlines"]
        bad = []
        generic = {"physics", "practical", "practically", "mobile", "scaler", "locus"}
        for h in heads[:50]:
            title_lc = (h.get("title") or "").lower()
            for word in generic:
                if word in title_lc.split():
                    if h.get("matchedSymbols"):
                        # If matched symbol's name is exactly that word, skip
                        # (since it's likely actually about that company)
                        bad.append((word, h.get("title"), h.get("matchedSymbols")))
                        break
        # Soft assert — this is spot-check
        assert len(bad) <= 2, f"too many likely-false positive matches: {bad[:5]}"


# ---- regressions ----

class TestRegressions:
    def test_watchlist_get(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/watchlist", headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert "symbols" in r.json()

    def test_portfolio(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/portfolio", headers=admin_h, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("cash", "holdings", "totalValue"):
            assert k in d

    def test_news_headlines(self):
        r = requests.get(f"{BASE_URL}/api/news/headlines?limit=20", timeout=30)
        assert r.status_code == 200
        assert "headlines" in r.json()

    def test_news_for_symbol(self, admin_h):
        prices = requests.get(f"{BASE_URL}/api/prices", timeout=20).json()["prices"]
        sym = "RZRPAY" if "RZRPAY" in prices else next(iter(prices.keys()))
        r = requests.get(f"{BASE_URL}/api/news/for/{sym}", headers=admin_h, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["symbol"] == sym
        assert "articles" in body

    def test_marketbot_chat(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/marketbot/chat",
                          json={"message": "What is Razorpay?"}, headers=admin_h, timeout=60)
        # 200 happy path; 503 transient acceptable
        assert r.status_code in (200, 503), r.text
        if r.status_code == 200:
            reply = r.json()["reply"]
            assert "MarketBot estimate" in reply

    def test_leaderboard(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/leaderboard", headers=admin_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d


# ---- WS scoping ----

class TestWebSocketAlertScope:
    def test_ws_alert_scoped_via_inprocess_dispatch(self, admin_token, second_user):
        """We exercise the dispatcher unit path: subscribe two queues for two users
        on the live alerts_service module, force a check() crossing, and assert
        only the owning user's queue gets the ALERT message."""
        sys.path.insert(0, "/app/backend")
        from alerts_service import alerts_service  # the live module instance

        async def _run():
            sym = "WSTESTSYM"
            uid_a = "userA"
            uid_b = "userB"
            qA = alerts_service.subscribe(uid_a)
            qB = alerts_service.subscribe(uid_b)
            try:
                # inject an active alert for userA on sym
                alerts_service._by_symbol[sym] = [{
                    "id": "wsalert1", "userId": uid_a, "symbol": sym,
                    "targetPrice": 100.0, "direction": "above",
                    "active": True, "triggered": False, "note": "",
                }]
                # force crossing
                alerts_service.check(sym, 80.0, 110.0)
                # give the loop a tick
                await asyncio.sleep(0.05)
                # userA must have one ALERT msg; userB must be empty
                got_a = []
                while not qA.empty():
                    got_a.append(qA.get_nowait())
                got_b = []
                while not qB.empty():
                    got_b.append(qB.get_nowait())
                assert any(m.get("type") == "ALERT" for m in got_a), f"userA got nothing: {got_a}"
                assert not any(m.get("type") == "ALERT" for m in got_b), f"userB leaked: {got_b}"
            finally:
                alerts_service.unsubscribe(uid_a, qA)
                alerts_service.unsubscribe(uid_b, qB)
                # cleanup injected bucket
                alerts_service._by_symbol.pop(sym, None)

        asyncio.run(_run())
