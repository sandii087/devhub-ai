"""Transactional auth email over HTTPS. Never log recipients, tokens or provider bodies."""

import logging
import httpx

from devhub.config import settings


def configured() -> bool:
    return bool(settings.resend_api_key.strip() and settings.email_from.strip())


def send_auth_email(email: str, token: str, purpose: str) -> None:
    action = "verify-email" if purpose == "verify" else "reset-password"
    title = "Verify your DevHub email" if purpose == "verify" else "Reset your DevHub password"
    # Fragment is never sent to HTTP servers, access logs, or Referer headers.
    url = settings.app_origin.rstrip("/") + f"/#{action}={token}"
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [email],
                    "subject": title,
                    "text": f"{title}:\n{url}\n\nThis link expires in 30 minutes and works once. "
                    "If you did not request it, ignore this message.",
                },
            )
            response.raise_for_status()
    except Exception:
        logging.getLogger("devhub.auth_mail").error("Authentication email delivery failed")
