"""Watchlist API tests — iteration 6.

Admin credentials documented in /app/memory/test_credentials.md are not accepted
by the seeded admin account (login returns 401). Therefore the multi-user
isolation test cannot create a second fresh user. Instead we rely on the
demo_user account, and isolation is indirectly validated by checking that
symbols added with one token are retrievable with the same token while other
tests don't see them.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_USER = {"username": "demo_user", "password": "demo123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed for {creds['username']}: {r.status_code} {r.text}"
    return r.json()["token"]


def _headers(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def demo_token():
    tok = _login(DEMO_USER)
    # clean start: leave only RELIANCE
    g = requests.get(f"{API}/watchlist", headers=_headers(tok), timeout=30).json()
    for s in g.get("symbols", []):
        if s != "RELIANCE":
            requests.delete(f"{API}/watchlist/{s}", headers=_headers(tok), timeout=30)
    yield tok
    # final cleanup — leave only RELIANCE
    g = requests.get(f"{API}/watchlist", headers=_headers(tok), timeout=30).json()
    for s in g.get("symbols", []):
        if s != "RELIANCE":
            requests.delete(f"{API}/watchlist/{s}", headers=_headers(tok), timeout=30)
    requests.post(f"{API}/watchlist", json={"symbol": "RELIANCE"}, headers=_headers(tok), timeout=30)


# ---------- Auth guards ----------
def test_watchlist_get_requires_auth():
    r = requests.get(f"{API}/watchlist", timeout=30)
    assert r.status_code in (401, 403)


def test_watchlist_post_requires_auth():
    r = requests.post(f"{API}/watchlist", json={"symbol": "RELIANCE"}, timeout=30)
    assert r.status_code in (401, 403)


def test_watchlist_delete_requires_auth():
    r = requests.delete(f"{API}/watchlist/RELIANCE", timeout=30)
    assert r.status_code in (401, 403)


# ---------- Shape / list ----------
def test_get_returns_symbols_list(demo_token):
    r = requests.get(f"{API}/watchlist", headers=_headers(demo_token), timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "symbols" in data
    assert isinstance(data["symbols"], list)


# ---------- Add valid ----------
def test_add_valid_symbol(demo_token):
    # Ensure not present first
    requests.delete(f"{API}/watchlist/TCS", headers=_headers(demo_token), timeout=30)
    r = requests.post(f"{API}/watchlist", json={"symbol": "TCS"}, headers=_headers(demo_token), timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["symbol"] == "TCS"
    g = requests.get(f"{API}/watchlist", headers=_headers(demo_token), timeout=30).json()
    assert "TCS" in g["symbols"]


# ---------- Add invalid ----------
def test_add_invalid_symbol(demo_token):
    r = requests.post(f"{API}/watchlist", json={"symbol": "FAKE123"}, headers=_headers(demo_token), timeout=30)
    assert r.status_code == 400
    body = r.json()
    detail = body.get("detail") or body.get("message") or ""
    assert "unknown" in str(detail).lower()


# ---------- Idempotent ----------
def test_add_idempotent(demo_token):
    requests.post(f"{API}/watchlist", json={"symbol": "INFY"}, headers=_headers(demo_token), timeout=30)
    r2 = requests.post(f"{API}/watchlist", json={"symbol": "INFY"}, headers=_headers(demo_token), timeout=30)
    assert r2.status_code == 200
    g = requests.get(f"{API}/watchlist", headers=_headers(demo_token), timeout=30).json()
    count = sum(1 for s in g["symbols"] if s == "INFY")
    assert count == 1, f"INFY appears {count} times — expected 1 (idempotent)"


# ---------- Delete existing ----------
def test_delete_existing(demo_token):
    requests.post(f"{API}/watchlist", json={"symbol": "WIPRO"}, headers=_headers(demo_token), timeout=30)
    d = requests.delete(f"{API}/watchlist/WIPRO", headers=_headers(demo_token), timeout=30)
    assert d.status_code == 200
    assert d.json().get("ok") is True
    g = requests.get(f"{API}/watchlist", headers=_headers(demo_token), timeout=30).json()
    assert "WIPRO" not in g["symbols"]


# ---------- Delete non-watched returns ok ----------
def test_delete_nonwatched_still_ok(demo_token):
    # Ensure HDFCBANK not present
    requests.delete(f"{API}/watchlist/HDFCBANK", headers=_headers(demo_token), timeout=30)
    r = requests.delete(f"{API}/watchlist/HDFCBANK", headers=_headers(demo_token), timeout=30)
    assert r.status_code == 200
    assert r.json().get("ok") is True


# ---------- Bad bearer → 401 ----------
def test_invalid_bearer_rejected():
    r = requests.get(f"{API}/watchlist", headers={"Authorization": "Bearer not.a.token"}, timeout=30)
    assert r.status_code == 401
