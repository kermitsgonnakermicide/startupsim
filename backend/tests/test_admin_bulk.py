"""
Backend tests for admin bulk endpoints + admin login.
Tests:
- Admin login with reset password SCALEdaddySALLU67
- Bulk endpoints return 403 to non-admin
- Bulk reject-pending rejects only pending non-admin users
- Bulk revoke-approved moves approved non-admins to pending (admin untouched)
- Bulk leaderboard-hide-all / show-all toggles leaderboardHidden on non-admins
- After tests, restore demo_user back to approved
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "SCALEdaddySALLU67"
DEMO_USER = "demo_user"
DEMO_PASS = "demo123"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=60)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("isAdmin") is True
    assert isinstance(data.get("token"), str) and len(data["token"]) > 0
    return data["token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _signup_user(username, password="abc123", email=None, reason="TEST bulk"):
    email = email or f"{username}@example.com"
    r = requests.post(
        f"{API}/auth/signup",
        json={"username": username, "password": password, "email": email, "reason": reason},
        timeout=15,
    )
    return r


@pytest.fixture(scope="session")
def test_users(admin_headers):
    """Create 3 fresh pending test users."""
    users = []
    for i in range(3):
        uname = f"TEST_bulk_{uuid.uuid4().hex[:8]}"
        r = _signup_user(uname)
        assert r.status_code in (200, 201), f"signup failed: {r.status_code} {r.text}"
        users.append(uname)
    # Give time for writes
    time.sleep(0.3)
    # Fetch their IDs from admin applications
    apps = requests.get(f"{API}/admin/applications", headers=admin_headers, timeout=30).json()
    pending = {u["username"]: u["userId"] for u in apps.get("pending", [])}
    ids = {u: pending[u] for u in users if u in pending}
    assert len(ids) == 3, f"Not all test users pending: {ids}"
    yield ids
    # Teardown: nothing strict - users stay but can't login


# ---------- Admin login ----------
def test_admin_login_works(admin_token):
    assert admin_token


def test_admin_me(admin_headers):
    r = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    assert r.json().get("isAdmin") is True


# ---------- Non-admin 403 ----------
@pytest.fixture(scope="session")
def demo_token():
    r = requests.post(f"{API}/auth/login", json={"username": DEMO_USER, "password": DEMO_PASS}, timeout=60)
    if r.status_code != 200:
        pytest.skip(f"demo_user login failed: {r.status_code} {r.text}")
    return r.json()["token"]


@pytest.mark.parametrize("path", [
    "/admin/bulk/reject-pending",
    "/admin/bulk/revoke-approved",
    "/admin/bulk/leaderboard-hide-all",
    "/admin/bulk/leaderboard-show-all",
])
def test_bulk_non_admin_forbidden(path, demo_token):
    r = requests.post(f"{API}{path}", headers={"Authorization": f"Bearer {demo_token}"}, timeout=15)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


# ---------- Leaderboard hide/show all ----------
def test_bulk_leaderboard_hide_all(admin_headers):
    r = requests.post(f"{API}/admin/bulk/leaderboard-hide-all", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert isinstance(data.get("count"), int)
    assert data["count"] >= 0

    # Verify via admin applications
    apps = requests.get(f"{API}/admin/applications", headers=admin_headers, timeout=15).json()
    all_users = apps.get("pending", []) + apps.get("approved", []) + apps.get("rejected", [])
    non_admin = [u for u in all_users if not u.get("isAdmin")]
    if non_admin:
        assert all(u.get("leaderboardHidden") is True for u in non_admin), "Not all non-admins hidden"
    # Admin must not be modified
    admins = [u for u in all_users if u.get("isAdmin")]
    for a in admins:
        assert a.get("leaderboardHidden") is not True


def test_bulk_leaderboard_show_all(admin_headers):
    r = requests.post(f"{API}/admin/bulk/leaderboard-show-all", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert isinstance(data.get("count"), int)

    apps = requests.get(f"{API}/admin/applications", headers=admin_headers, timeout=15).json()
    all_users = apps.get("pending", []) + apps.get("approved", []) + apps.get("rejected", [])
    non_admin = [u for u in all_users if not u.get("isAdmin")]
    if non_admin:
        assert all(u.get("leaderboardHidden") is False for u in non_admin), "Not all non-admins visible"


# ---------- Bulk revoke-approved ----------
def test_bulk_revoke_approved(admin_headers, test_users):
    # Approve all 3 test users
    for uid in test_users.values():
        r = requests.post(f"{API}/admin/approve", headers=admin_headers, json={"userId": uid}, timeout=15)
        assert r.status_code == 200, f"approve failed: {r.text}"

    # Snapshot approved non-admin count BEFORE revoke
    apps_before = requests.get(f"{API}/admin/applications", headers=admin_headers, timeout=15).json()
    approved_before = [u for u in apps_before.get("approved", []) if not u.get("isAdmin")]
    pending_before = len(apps_before.get("pending", []))

    r = requests.post(f"{API}/admin/bulk/revoke-approved", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("count") == len(approved_before), f"count {data.get('count')} != {len(approved_before)}"

    apps_after = requests.get(f"{API}/admin/applications", headers=admin_headers, timeout=15).json()
    # No approved non-admin left
    approved_after_non_admin = [u for u in apps_after.get("approved", []) if not u.get("isAdmin")]
    assert approved_after_non_admin == []
    # Admin still present (admin doesn't carry status=approved in list; just ensure admin login still works)
    r = requests.post(f"{API}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, "Admin login broke after bulk-revoke"
    # Pending count should equal old pending + old approved-non-admin
    assert len(apps_after.get("pending", [])) == pending_before + len(approved_before)


# ---------- Bulk reject-pending ----------
def test_bulk_reject_pending(admin_headers):
    apps_before = requests.get(f"{API}/admin/applications", headers=admin_headers, timeout=15).json()
    pending_before = apps_before.get("pending", [])
    rejected_before = len(apps_before.get("rejected", []))

    r = requests.post(f"{API}/admin/bulk/reject-pending", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert data.get("count") == len(pending_before)

    apps_after = requests.get(f"{API}/admin/applications", headers=admin_headers, timeout=15).json()
    assert apps_after.get("pending", []) == []
    assert len(apps_after.get("rejected", [])) == rejected_before + len(pending_before)


# ---------- Restore demo_user to approved ----------
def test_zz_restore_demo_user(admin_headers):
    """Runs last (alphabetically) - re-approve demo_user so next iterations work."""
    apps = requests.get(f"{API}/admin/applications", headers=admin_headers, timeout=15).json()
    all_users = apps.get("pending", []) + apps.get("rejected", []) + apps.get("approved", [])
    demo = next((u for u in all_users if u.get("username") == DEMO_USER), None)
    if demo and demo.get("status") != "approved":
        r = requests.post(f"{API}/admin/approve", headers=admin_headers, json={"userId": demo["userId"]}, timeout=30)
        assert r.status_code == 200
    # Verify demo can login
    r = requests.post(f"{API}/auth/login", json={"username": DEMO_USER, "password": DEMO_PASS}, timeout=15)
    assert r.status_code == 200, f"demo_user cannot login after restore: {r.text}"
