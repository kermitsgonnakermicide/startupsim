"""Brevo (Sendinblue) email service. Non-blocking, never raises."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt

logger = logging.getLogger("emailer")

BREVO_API = "https://api.brevo.com/v3/smtp/email"


def _api_key() -> str | None:
    return os.environ.get("BREVO_API_KEY")


def _sender() -> dict:
    return {
        "name": "SCALE India Investment",
        "email": os.environ.get("SENDER_EMAIL", "scalesupportteam2@gmail.com"),
    }


def _admin_email() -> str:
    return os.environ.get("ADMIN_EMAIL", "")


def _public_url() -> str:
    return os.environ.get("PUBLIC_APP_URL", "")


def _reply_to() -> dict | None:
    rt = os.environ.get("REPLY_TO_EMAIL", "").strip()
    return {"email": rt} if rt else None


def _wrap(body_html: str, footer: str = "") -> str:
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e1a;padding:24px;font-family:Inter,Arial,sans-serif;color:#e2e8f0;">
  <tr><td align="center">
    <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#111827;border:1px solid #1e293b;border-radius:14px;padding:28px;">
      <tr><td>
        <div style="font-family:'JetBrains Mono',monospace;color:#a01e20;font-size:22px;font-weight:700;letter-spacing:-0.02em;">SCALE</div>
        <div style="color:#94a3b8;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:18px;">India Investment</div>
        {body_html}
        <div style="margin-top:24px;padding-top:14px;border-top:1px solid #1e293b;color:#475569;font-size:11px;">
          {footer or "SCALE India Investment — paper trading simulator. No real money is involved."}
        </div>
      </td></tr>
    </table>
  </td></tr>
</table>
"""


async def _send(to: str, subject: str, html: str) -> bool:
    key = _api_key()
    if not key:
        logger.warning("BREVO_API_KEY missing — email skipped (to=%s)", to)
        return False
    if not to or "@" not in to:
        logger.warning("Skipping email — invalid recipient: %r", to)
        return False
    payload = {
        "sender": _sender(),
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
    }
    rt = _reply_to()
    if rt:
        payload["replyTo"] = rt
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                BREVO_API,
                headers={
                    "api-key": key,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                json=payload,
            )
        if 200 <= r.status_code < 300:
            msg_id = (r.json() or {}).get("messageId")
            logger.info("Brevo email sent to=%s id=%s", to, msg_id)
            return True
        logger.warning("Brevo send failed to=%s status=%s body=%s", to, r.status_code, r.text[:300])
        return False
    except Exception as e:
        logger.warning("Brevo send error to=%s err=%s", to, e)
        return False


def fire_and_forget(coro):
    """Schedule an awaitable without awaiting; safe in FastAPI request handlers."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        try:
            asyncio.run(coro)
        except Exception as e:
            logger.warning("fire_and_forget fallback failed: %s", e)


# ---------- Signed action tokens for one-click approve/reject ----------
def make_action_token(user_id: str, action: str, ttl_hours: int = 24) -> str:
    secret = os.environ.get("JWT_SECRET", "change-me")
    payload = {
        "uid": user_id,
        "act": action,  # "approve" | "reject"
        "exp": datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        "kind": "admin_action",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_action_token(token: str) -> dict:
    secret = os.environ.get("JWT_SECRET", "change-me")
    data = jwt.decode(token, secret, algorithms=["HS256"])
    if data.get("kind") != "admin_action":
        raise ValueError("Invalid token kind")
    return data


# ---------- Templates ----------
async def notify_admin_new_application(username: str, email: str, reason: str, user_id: str = ""):
    admin_to = _admin_email()
    if not admin_to:
        logger.warning("ADMIN_EMAIL not set — skipping admin notification")
        return
    public_url = _public_url()
    approve_url = f"{public_url}/api/admin/action?token={make_action_token(user_id, 'approve')}" if user_id else ""
    reject_url = f"{public_url}/api/admin/action?token={make_action_token(user_id, 'reject')}" if user_id else ""
    reason_block = ""
    if reason and reason.strip():
        safe = (reason or "").replace('<', '&lt;').replace('>', '&gt;')
        reason_block = f'<tr><td style="color:#94a3b8;vertical-align:top;">Reason</td><td style="color:#e2e8f0;">{safe}</td></tr>'
    one_click = ""
    if approve_url and reject_url:
        one_click = f"""
<p style="margin:18px 0 0;">
  <a href="{approve_url}" style="display:inline-block;background:#00d4aa;color:#0a0e1a;text-decoration:none;padding:10px 20px;border-radius:8px;font-size:14px;font-weight:700;margin-right:8px;">
    ✓ Approve
  </a>
  <a href="{reject_url}" style="display:inline-block;background:#f03e3e;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-size:14px;font-weight:700;">
    ✗ Reject
  </a>
</p>
<p style="margin:10px 0 0;color:#475569;font-size:11px;">One-click actions expire in 24 hours.</p>
"""
    body = f"""
<h2 style="color:#e2e8f0;font-size:18px;margin:0 0 12px;">New access request</h2>
<p style="color:#94a3b8;font-size:14px;margin:0 0 16px;">A new user has applied for access to SCALE.</p>
<table role="presentation" cellpadding="8" cellspacing="0" style="background:#1a2235;border:1px solid #1e293b;border-radius:10px;width:100%;font-size:14px;">
  <tr><td style="color:#94a3b8;width:100px;">Username</td><td style="color:#a01e20;font-family:'JetBrains Mono',monospace;font-weight:600;">@{username}</td></tr>
  <tr><td style="color:#94a3b8;">Email</td><td style="color:#e2e8f0;">{email or "—"}</td></tr>
  {reason_block}
</table>
{one_click}
<p style="margin:14px 0 0;">
  <a href="{public_url}" style="color:#a01e20;font-size:12px;">Or open Admin tab →</a>
</p>
"""
    await _send(admin_to, f"New SCALE access request from @{username}", _wrap(body))


async def notify_user_approved(email: str, username: str, approved_until_iso: str | None):
    if not email:
        return
    expires_str = ""
    if approved_until_iso:
        try:
            d = datetime.fromisoformat(approved_until_iso)
            expires_str = d.strftime("%d %b %Y, %H:%M UTC")
        except Exception:
            expires_str = approved_until_iso
    body = f"""
<h2 style="color:#00d4aa;font-size:18px;margin:0 0 12px;">You're approved!</h2>
<p style="color:#94a3b8;font-size:14px;margin:0 0 12px;">Hi @{username}, your access to SCALE India Investment has been approved.</p>
<p style="color:#94a3b8;font-size:14px;margin:0 0 16px;">You can now log in with your username and password.</p>
{f'<p style="color:#94a3b8;font-size:13px;margin:0 0 16px;">Access valid until: <span style="color:#e2e8f0;font-family:JetBrains Mono,monospace;">{expires_str}</span> (10-day window).</p>' if expires_str else ''}
<p>
  <a href="{_public_url()}" style="display:inline-block;background:#a01e20;color:#fff;text-decoration:none;padding:10px 20px;border-radius:8px;font-size:14px;font-weight:600;">
    Log in to SCALE →
  </a>
</p>
"""
    await _send(email, "Your SCALE access has been approved", _wrap(body))


async def notify_user_rejected(email: str, username: str):
    if not email:
        return
    body = f"""
<h2 style="color:#f03e3e;font-size:18px;margin:0 0 12px;">Access request not approved</h2>
<p style="color:#94a3b8;font-size:14px;margin:0 0 16px;">Hi @{username}, your access request was not approved at this time.</p>
"""
    await _send(email, "Your SCALE access request — update", _wrap(body))
