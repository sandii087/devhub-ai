"""Transactional auth email over HTTPS. Never log recipients, tokens or provider bodies."""

import logging
from html import escape
import httpx

from devhub.config import settings


def configured() -> bool:
    return bool(settings.resend_api_key.strip() and settings.email_from.strip())


def send_auth_email(email: str, token: str, purpose: str) -> None:
    action = "verify-email" if purpose == "verify" else "reset-password"
    title = "Verify your DevHub email" if purpose == "verify" else "Reset your DevHub password"
    # Fragment is never sent to HTTP servers, access logs, or Referer headers.
    url = settings.app_origin.rstrip("/") + f"/#{action}={token}"
    safe_url, safe_title = escape(url, quote=True), escape(title)
    html = (
        '<!doctype html><html><body style="margin:0;background:#f5f6fa;font-family:Arial,sans-serif;color:#202338">'
        '<main style="max-width:560px;margin:32px auto;padding:32px;background:white;border-radius:16px">'
        '<p style="font-weight:bold;color:#6254d9">DEVHUB</p>'
        f'<h1 style="font-size:24px">{safe_title}</h1>'
        "<p>Keep your workspace secure. Use the button below to continue.</p>"
        f'<p style="margin:32px 0"><a href="{safe_url}" style="background:#6254d9;color:white;'
        f'padding:14px 20px;border-radius:8px;text-decoration:none">{safe_title}</a></p>'
        "<p>This link expires in 30 minutes and can only be used once.</p>"
        "<p>If you did not request this email, you can safely ignore it.</p>"
        f'<p style="font-size:12px;overflow-wrap:anywhere">Button not working? Open <a href="{safe_url}">'
        "this secure link</a>.</p></main></body></html>"
    )
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [email],
                    "subject": title,
                    "html": html,
                    "text": f"{title}:\n{url}\n\nThis link expires in 30 minutes and works once. "
                    "If you did not request it, ignore this message.",
                },
            )
            response.raise_for_status()
    except Exception:
        logging.getLogger("devhub.auth_mail").error("Authentication email delivery failed")
