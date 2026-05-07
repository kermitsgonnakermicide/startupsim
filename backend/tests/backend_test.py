"""SCALE India Investment backend regression + approval/admin gating tests."""
import os
import uuid
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def s():
    return requests.Session()


# ---------------- Admin & Demo tokens ----------------
ADMIN_PW = "SCALEdaddySALLU67"


@pytest.fixture(scope="session")
def admin_token(s):
    r = s.post(f"{API}/auth/login", json={"username": "admin", "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["isAdmin"] is True
    return data["token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def demo_token(s):
    r = s.post(f"{API}/auth/login", json={"username": "demo_user", "password": "demo123"}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("isAdmin") is False
    return body["token"]


@pytest.fixture(scope="session")
def demo_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}"}


# ---------------- Signup gating ----------------
def _new_signup(s, password="pass123", reason="I want to learn paper trading and improve my skills."):
    uname = f"t{uuid.uuid4().hex[:10]}"
    payload = {
        "username": uname,
        "password": password,
        "email": f"{uname}@example.com",
        "reason": reason,
    }
    # rate-limit window is 10 calls / 60s; retry on 429
    for _ in range(8):
        r = s.post(f"{API}/auth/signup", json=payload, timeout=15)
        if r.status_code != 429:
            return uname, r
        time.sleep(8)
    return uname, r


def test_signup_creates_pending_no_token(s):
    uname, r = _new_signup(s)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("submitted") is True
    assert "token" not in body
    assert "message" in body


def test_signup_invalid_email(s):
    uname = f"t{uuid.uuid4().hex[:8]}"
    r = s.post(f"{API}/auth/signup", json={
        "username": uname, "password": "pass123",
        "email": "not-an-email", "reason": "Want access for trading practice please",
    })
    assert r.status_code == 400


def test_signup_without_reason_succeeds(s):
    """Iter 4: reason field is now optional on signup."""
    uname = f"t{uuid.uuid4().hex[:10]}"
    payload = {"username": uname, "password": "pass123", "email": f"{uname}@x.com"}
    for _ in range(8):
        r = s.post(f"{API}/auth/signup", json=payload, timeout=15)
        if r.status_code != 429:
            break
        time.sleep(8)
    assert r.status_code == 200, r.text
    assert r.json().get("submitted") is True


def test_signup_short_password(s):
    uname = f"t{uuid.uuid4().hex[:8]}"
    r = s.post(f"{API}/auth/signup", json={
        "username": uname, "password": "12",
        "email": f"{uname}@x.com", "reason": "Want access for trading practice",
    })
    assert r.status_code == 400


def test_signup_invalid_username(s):
    r = s.post(f"{API}/auth/signup", json={
        "username": "ab", "password": "pass123",
        "email": "a@b.com", "reason": "Want access for trading practice",
    })
    assert r.status_code == 400


def test_signup_duplicate_case_insensitive(s):
    uname, r = _new_signup(s)
    assert r.status_code == 200
    r2 = s.post(f"{API}/auth/signup", json={
        "username": uname.upper(), "password": "pass123",
        "email": f"{uname}2@x.com", "reason": "Duplicate signup attempt for tests",
    })
    assert r2.status_code == 409


# ---------------- Login gating ----------------
def test_login_pending_returns_403(s):
    uname, r = _new_signup(s)
    assert r.status_code == 200
    rl = s.post(f"{API}/auth/login", json={"username": uname, "password": "pass123"})
    assert rl.status_code == 403
    assert "pending" in rl.json().get("detail", "").lower()


def test_login_admin_returns_isadmin_true(admin_token):
    assert isinstance(admin_token, str) and len(admin_token) > 10


def test_login_demo_user_returns_isadmin_false(s):
    r = s.post(f"{API}/auth/login", json={"username": "demo_user", "password": "demo123"})
    assert r.status_code == 200
    assert r.json()["isAdmin"] is False


def test_login_bad_password(s):
    r = s.post(f"{API}/auth/login", json={"username": "demo_user", "password": "wrong"})
    assert r.status_code == 401


# ---------------- /auth/me ----------------
def test_me_admin_isadmin(s, admin_headers):
    r = s.get(f"{API}/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["isAdmin"] is True


def test_me_demo_not_admin(s, demo_headers):
    r = s.get(f"{API}/auth/me", headers=demo_headers)
    assert r.status_code == 200
    assert r.json()["isAdmin"] is False


def test_me_unauthorized(s):
    r = s.get(f"{API}/auth/me")
    assert r.status_code == 401


# ---------------- Admin endpoints ----------------
def test_admin_applications_requires_admin(s, demo_headers):
    r = s.get(f"{API}/admin/applications", headers=demo_headers)
    assert r.status_code == 403


def test_admin_applications_lists_pending(s, admin_headers):
    # create a fresh pending user
    uname, r = _new_signup(s)
    assert r.status_code == 200
    al = s.get(f"{API}/admin/applications", headers=admin_headers)
    assert al.status_code == 200
    body = al.json()
    for k in ("pending", "approved", "rejected", "counts"):
        assert k in body
    assert any(u["username"] == uname for u in body["pending"]), "newly-signed user not in pending list"


def test_admin_approve_then_login_works(s, admin_headers):
    uname, _ = _new_signup(s)
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    target = next(u for u in al["pending"] if u["username"] == uname)
    ap = s.post(f"{API}/admin/approve", headers=admin_headers, json={"userId": target["userId"]})
    assert ap.status_code == 200
    assert "approvedUntil" in ap.json()
    # user should now be able to login
    rl = s.post(f"{API}/auth/login", json={"username": uname, "password": "pass123"})
    assert rl.status_code == 200, rl.text
    assert rl.json()["isAdmin"] is False


def test_admin_reject_then_login_blocked(s, admin_headers):
    uname, _ = _new_signup(s)
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    target = next(u for u in al["pending"] if u["username"] == uname)
    rj = s.post(f"{API}/admin/reject", headers=admin_headers, json={"userId": target["userId"]})
    assert rj.status_code == 200
    rl = s.post(f"{API}/auth/login", json={"username": uname, "password": "pass123"})
    assert rl.status_code == 403
    assert "not approved" in rl.json()["detail"].lower() or "rejected" in rl.json()["detail"].lower() or "new application" in rl.json()["detail"].lower()


def test_admin_revoke_resets_to_pending(s, admin_headers):
    # create and approve a user, then revoke
    uname, _ = _new_signup(s)
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    target = next(u for u in al["pending"] if u["username"] == uname)
    s.post(f"{API}/admin/approve", headers=admin_headers, json={"userId": target["userId"]})
    # login should succeed first
    tok = s.post(f"{API}/auth/login", json={"username": uname, "password": "pass123"}).json()["token"]
    # revoke
    rv = s.post(f"{API}/admin/revoke", headers=admin_headers, json={"userId": target["userId"]})
    assert rv.status_code == 200
    # subsequent login blocked
    rl = s.post(f"{API}/auth/login", json={"username": uname, "password": "pass123"})
    assert rl.status_code == 403
    # /auth/me with old token should also now return 403 (live access check)
    me = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 403


def test_admin_cannot_modify_admin_account(s, admin_headers):
    # find admin id via /auth/me
    r = s.get(f"{API}/auth/me", headers=admin_headers).json()
    admin_id = r["userId"]
    for ep in ("approve", "reject", "revoke"):
        rr = s.post(f"{API}/admin/{ep}", headers=admin_headers, json={"userId": admin_id})
        # admin doesn't appear in /admin/applications (filtered) and direct-by-id should be 400 (if found) or 404
        assert rr.status_code in (400, 404), f"{ep} returned {rr.status_code}: {rr.text}"


# ---------------- Reapply flow ----------------
def test_reapply_after_reject_resets_to_pending(s, admin_headers):
    uname, _ = _new_signup(s)
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    target = next(u for u in al["pending"] if u["username"] == uname)
    s.post(f"{API}/admin/reject", headers=admin_headers, json={"userId": target["userId"]})
    # reapply
    rp = s.post(f"{API}/auth/reapply", json={
        "username": uname, "password": "pass123",
        "reason": "Please reconsider, I really want to learn paper trading.",
    })
    assert rp.status_code == 200
    assert rp.json().get("submitted") is True
    # status should be pending again
    al2 = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    assert any(u["username"] == uname for u in al2["pending"])


def test_reapply_bad_password(s):
    r = s.post(f"{API}/auth/reapply", json={
        "username": "demo_user", "password": "wrong",
        "reason": "Trying to reapply with wrong password",
    })
    assert r.status_code == 401


# ---------------- Stocks/Prices/Trade regression (subset) ----------------
def test_stocks_list(s):
    r = s.get(f"{API}/stocks")
    assert r.status_code == 200
    assert len(r.json()["stocks"]) >= 80


def test_prices(s):
    for _ in range(6):
        r = s.get(f"{API}/prices")
        if r.status_code == 200 and r.json().get("prices"):
            break
        time.sleep(3)
    assert r.status_code == 200
    assert len(r.json()["prices"]) >= 20


def test_portfolio_demo(s, demo_headers):
    r = s.get(f"{API}/portfolio", headers=demo_headers)
    assert r.status_code == 200
    assert "cash" in r.json()


def test_trade_buy_demo(s, demo_headers):
    prices = s.get(f"{API}/prices").json()["prices"]
    symbol = next((k for k, v in prices.items() if v.get("price")), "RELIANCE")
    price = prices.get(symbol, {}).get("price") or 1000
    r = s.post(f"{API}/trade", headers=demo_headers, json={"symbol": symbol, "type": "BUY", "qty": 1, "price": price})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_leaderboard(s, demo_headers):
    r = s.get(f"{API}/leaderboard", headers=demo_headers)
    assert r.status_code == 200
    assert r.json()["totalPlayers"] >= 10


# ---------------- Iteration 3: Change Password ----------------
def _make_approved_user(s, admin_headers, password="pass123"):
    uname, _ = _new_signup(s, password=password)
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    target = next(u for u in al["pending"] if u["username"] == uname)
    s.post(f"{API}/admin/approve", headers=admin_headers, json={"userId": target["userId"]})
    tok = s.post(f"{API}/auth/login", json={"username": uname, "password": password}).json()["token"]
    return uname, tok


def test_change_password_success_and_relogin(s, admin_headers):
    uname, tok = _make_approved_user(s, admin_headers, password="pass123")
    h = {"Authorization": f"Bearer {tok}"}
    r = s.post(f"{API}/auth/change-password", headers=h,
               json={"currentPassword": "pass123", "newPassword": "newpass456"})
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    # old pw fails
    r_old = s.post(f"{API}/auth/login", json={"username": uname, "password": "pass123"})
    assert r_old.status_code == 401
    # new pw works
    r_new = s.post(f"{API}/auth/login", json={"username": uname, "password": "newpass456"})
    assert r_new.status_code == 200


def test_change_password_wrong_current_returns_401(s, admin_headers):
    _, tok = _make_approved_user(s, admin_headers, password="pass123")
    h = {"Authorization": f"Bearer {tok}"}
    r = s.post(f"{API}/auth/change-password", headers=h,
               json={"currentPassword": "wrongpw", "newPassword": "another1"})
    assert r.status_code == 401


def test_change_password_same_as_current_returns_400(s, admin_headers):
    _, tok = _make_approved_user(s, admin_headers, password="pass123")
    h = {"Authorization": f"Bearer {tok}"}
    r = s.post(f"{API}/auth/change-password", headers=h,
               json={"currentPassword": "pass123", "newPassword": "pass123"})
    assert r.status_code == 400


def test_change_password_too_short_returns_400(s, admin_headers):
    _, tok = _make_approved_user(s, admin_headers, password="pass123")
    h = {"Authorization": f"Bearer {tok}"}
    r = s.post(f"{API}/auth/change-password", headers=h,
               json={"currentPassword": "pass123", "newPassword": "ab12"})
    assert r.status_code == 400


def test_change_password_unauthenticated_returns_401(s):
    r = s.post(f"{API}/auth/change-password",
               json={"currentPassword": "pass123", "newPassword": "newpass456"})
    assert r.status_code == 401


def test_admin_password_round_trip_stays_admin123(s, admin_headers):
    """Change admin's password to temp then back so admin/SCALEdaddySALLU67 stays valid."""
    h = admin_headers
    r1 = s.post(f"{API}/auth/change-password", headers=h,
                json={"currentPassword": ADMIN_PW, "newPassword": "tempPw9!"})
    assert r1.status_code == 200, r1.text
    # login with new
    r_new = s.post(f"{API}/auth/login", json={"username": "admin", "password": "tempPw9!"})
    assert r_new.status_code == 200
    new_tok = r_new.json()["token"]
    # restore
    r2 = s.post(f"{API}/auth/change-password", headers={"Authorization": f"Bearer {new_tok}"},
                json={"currentPassword": "tempPw9!", "newPassword": ADMIN_PW})
    assert r2.status_code == 200
    # final sanity
    r_final = s.post(f"{API}/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r_final.status_code == 200


# ---------------- Iteration 3: Chart endpoint (Yahoo) ----------------
def test_chart_unauth_returns_401(s):
    r = s.get(f"{API}/chart/RELIANCE?range=1d")
    assert r.status_code == 401


def test_chart_invalid_symbol_returns_404(s, demo_headers):
    r = s.get(f"{API}/chart/INVALIDSYM?range=1d", headers=demo_headers)
    assert r.status_code == 404


def test_chart_1d_returns_intraday_candles(s, demo_headers):
    r = s.get(f"{API}/chart/RELIANCE?range=1d", headers=demo_headers, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["symbol"] == "RELIANCE"
    assert body["range"] == "1d"
    assert body["interval"] == "5m"
    assert "candles" in body
    candles = body["candles"]
    # 1d 5m intraday should normally have ~75 candles; allow some leeway
    assert len(candles) >= 30, f"Got only {len(candles)} candles"
    c0 = candles[0]
    for k in ("t", "o", "h", "l", "c", "v"):
        assert k in c0
    assert c0["h"] >= c0["l"]


def test_chart_1y_returns_daily_candles_and_meta(s, demo_headers):
    r = s.get(f"{API}/chart/RELIANCE?range=1y", headers=demo_headers, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["range"] == "1y"
    assert body["interval"] == "1d"
    assert body.get("previousClose") is not None
    assert body.get("fiftyTwoWeekHigh") is not None
    assert body.get("fiftyTwoWeekLow") is not None
    candles = body["candles"]
    # ~250 trading days in a year; allow >=200
    assert len(candles) >= 200, f"Got only {len(candles)} 1y candles"


def test_chart_unsupported_range_returns_400(s, demo_headers):
    r = s.get(f"{API}/chart/RELIANCE?range=10y", headers=demo_headers)
    assert r.status_code == 400


# ---------------- Iteration 3: Email integration (signup -> admin email) ----------------
def test_signup_triggers_admin_email_log(s):
    """Signup endpoint should fire-and-forget admin notification.
    We can't directly read backend logs via API, so just assert endpoint succeeds.
    Manual log-line check is documented in the test report.
    """
    uname, r = _new_signup(s)
    assert r.status_code == 200
    assert r.json().get("submitted") is True


# ---------------- Iteration 4: Applications sorted newest first ----------------
def test_admin_applications_sorted_newest_first(s, admin_headers):
    uname1, _ = _new_signup(s)
    time.sleep(1.2)
    uname2, _ = _new_signup(s)
    al = s.get(f"{API}/admin/applications", headers=admin_headers)
    assert al.status_code == 200
    pending = al.json()["pending"]
    assert len(pending) >= 2
    # Newest must come first; uname2 should appear before uname1
    idx1 = next((i for i, u in enumerate(pending) if u["username"] == uname1), -1)
    idx2 = next((i for i, u in enumerate(pending) if u["username"] == uname2), -1)
    assert idx2 != -1 and idx1 != -1
    assert idx2 < idx1, f"Expected newer ({uname2}) before older ({uname1}); idx2={idx2} idx1={idx1}"
    # Also verify the first row's createdAt is the max
    first_ts = pending[0].get("reappliedAt") or pending[0].get("createdAt") or ""
    for row in pending[1:]:
        ts = row.get("reappliedAt") or row.get("createdAt") or ""
        assert first_ts >= ts


# ---------------- Iteration 4: One-click admin action endpoint ----------------
import sys
sys.path.insert(0, "/app/backend")
os.environ.setdefault("JWT_SECRET", "scale_india_investment_secret_change_in_prod_2ab9e71f4c6d8e0b3a5f7c9d1e2a4b6c")
from emailer import make_action_token  # noqa: E402


def test_admin_action_invalid_token_returns_400_html(s):
    r = s.get(f"{API}/admin/action?token=not-a-real-token")
    assert r.status_code == 400
    assert "text/html" in r.headers.get("content-type", "").lower()
    assert "invalid" in r.text.lower() or "expired" in r.text.lower()


def test_admin_action_approve_via_one_click(s, admin_headers):
    uname, _ = _new_signup(s)
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    target = next(u for u in al["pending"] if u["username"] == uname)
    tok = make_action_token(target["userId"], "approve")
    r = s.get(f"{API}/admin/action?token={tok}")
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers.get("content-type", "").lower()
    assert "approved" in r.text.lower()
    # User should now login successfully
    rl = s.post(f"{API}/auth/login", json={"username": uname, "password": "pass123"})
    assert rl.status_code == 200
    # Idempotent: a second click shows "Already approved"
    r2 = s.get(f"{API}/admin/action?token={tok}")
    assert r2.status_code == 200
    assert "already" in r2.text.lower() or "approved" in r2.text.lower()


def test_admin_action_reject_via_one_click(s, admin_headers):
    uname, _ = _new_signup(s)
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    target = next(u for u in al["pending"] if u["username"] == uname)
    tok = make_action_token(target["userId"], "reject")
    r = s.get(f"{API}/admin/action?token={tok}")
    assert r.status_code == 200
    assert "rejected" in r.text.lower()
    rl = s.post(f"{API}/auth/login", json={"username": uname, "password": "pass123"})
    assert rl.status_code == 403


def test_admin_action_refuses_admin_account(s, admin_headers):
    me = s.get(f"{API}/auth/me", headers=admin_headers).json()
    tok = make_action_token(me["userId"], "approve")
    r = s.get(f"{API}/admin/action?token={tok}")
    assert r.status_code == 400
    assert "not allowed" in r.text.lower() or "admin" in r.text.lower()


def test_admin_action_user_not_found_returns_404(s):
    tok = make_action_token("non-existent-uid-12345", "approve")
    r = s.get(f"{API}/admin/action?token={tok}")
    assert r.status_code == 404



# ==================== Iteration 5: leaderboard visibility / reset removed / trade-block ====================

DEMO_USER_ID = "8c87f3cf-2c5f-45cd-b281-d4319b3ad044"


def _get_demo_user_id(s, admin_headers):
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    for bucket in ("approved", "pending", "rejected"):
        for u in al.get(bucket, []):
            if u["username"] == "demo_user":
                return u["userId"]
    return DEMO_USER_ID


# Reset endpoint removed entirely
def test_portfolio_reset_endpoint_removed(s, demo_headers):
    r = s.post(f"{API}/portfolio/reset", headers=demo_headers)
    assert r.status_code in (404, 405), f"expected 404/405 (endpoint removed), got {r.status_code}: {r.text}"


# Admin leaderboard-visibility: auth gating
def test_leaderboard_visibility_requires_auth(s):
    r = s.post(f"{API}/admin/leaderboard-visibility", json={"userId": DEMO_USER_ID, "hidden": True})
    assert r.status_code == 401


def test_leaderboard_visibility_non_admin_forbidden(s, demo_headers):
    r = s.post(f"{API}/admin/leaderboard-visibility", headers=demo_headers,
               json={"userId": DEMO_USER_ID, "hidden": True})
    assert r.status_code == 403


def test_leaderboard_visibility_user_not_found_404(s, admin_headers):
    r = s.post(f"{API}/admin/leaderboard-visibility", headers=admin_headers,
               json={"userId": "does-not-exist-uid", "hidden": True})
    assert r.status_code == 404


def test_leaderboard_visibility_cannot_modify_admin(s, admin_headers):
    me = s.get(f"{API}/auth/me", headers=admin_headers).json()
    r = s.post(f"{API}/admin/leaderboard-visibility", headers=admin_headers,
               json={"userId": me["userId"], "hidden": True})
    assert r.status_code == 400


# Hide demo_user → admin leaderboard rows must NOT include demo_user, but demo_user `me` still set
def test_leaderboard_hidden_user_excluded_for_others_but_visible_to_self(s, admin_headers, demo_headers):
    demo_uid = _get_demo_user_id(s, admin_headers)

    # Hide demo_user
    r1 = s.post(f"{API}/admin/leaderboard-visibility", headers=admin_headers,
                json={"userId": demo_uid, "hidden": True})
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["ok"] is True and body["leaderboardHidden"] is True

    # Admin viewer sees no demo_user row
    lb_admin = s.get(f"{API}/leaderboard", headers=admin_headers).json()
    assert not any(r["username"] == "demo_user" for r in lb_admin["rows"]), \
        "demo_user should not appear in admin's leaderboard rows when hidden"

    # demo_user still sees self in `me`
    lb_demo = s.get(f"{API}/leaderboard", headers=demo_headers).json()
    assert lb_demo["me"] is not None, "Hidden user should still see their own `me` row"
    assert lb_demo["me"]["username"] == "demo_user"
    assert lb_demo["me"]["isCurrentUser"] is True

    # Admin row entry exposes leaderboardHidden=true
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    found = next((u for u in al["approved"] if u["username"] == "demo_user"), None)
    assert found is not None
    assert found["leaderboardHidden"] is True

    # Toggle visible again (cleanup)
    r2 = s.post(f"{API}/admin/leaderboard-visibility", headers=admin_headers,
                json={"userId": demo_uid, "hidden": False})
    assert r2.status_code == 200
    assert r2.json()["leaderboardHidden"] is False

    # Demo_user now visible to admin again
    lb_admin2 = s.get(f"{API}/leaderboard", headers=admin_headers).json()
    assert any(r["username"] == "demo_user" for r in lb_admin2["rows"]) or \
           lb_admin2.get("totalPlayers", 0) > 0


# Admin accounts excluded from leaderboard rows for others (but admin sees own `me`)
def test_admin_excluded_from_leaderboard_rows_for_demo_viewer(s, demo_headers):
    lb = s.get(f"{API}/leaderboard", headers=demo_headers).json()
    assert not any(r["username"] == "admin" for r in lb["rows"]), \
        "admin account should not appear in leaderboard rows for non-admin viewer"


# admin/applications now exposes leaderboardHidden boolean on every row
def test_admin_applications_includes_leaderboardHidden(s, admin_headers):
    al = s.get(f"{API}/admin/applications", headers=admin_headers).json()
    for bucket in ("pending", "approved", "rejected"):
        for u in al[bucket]:
            assert "leaderboardHidden" in u, f"missing leaderboardHidden on {u['username']}"
            assert isinstance(u["leaderboardHidden"], bool)


# Trade-block: live verify only when market actually closed; otherwise smoke-check success path
def test_trade_market_closed_block_or_success(s, demo_headers):
    ms = s.get(f"{API}/market-status").json()
    status = (ms.get("status") or "").upper()
    prices = s.get(f"{API}/prices").json()["prices"]
    symbol = next((k for k, v in prices.items() if v.get("price")), "RELIANCE")
    price = prices.get(symbol, {}).get("price") or 1000
    r = s.post(f"{API}/trade", headers=demo_headers,
               json={"symbol": symbol, "type": "BUY", "qty": 1, "price": price})
    if status == "OPEN":
        assert r.status_code == 200, f"trade should succeed when OPEN: {r.text}"
        assert r.json()["ok"] is True
    else:
        assert r.status_code == 400
        detail = r.json().get("detail", "").lower()
        assert "closed" in detail or "disabled" in detail, f"unexpected detail: {detail}"
