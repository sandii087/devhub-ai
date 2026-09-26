"""Same-origin GitHub OAuth authentication with opaque server-side sessions."""

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import ipaddress
import json
import secrets
from typing import Literal
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
import httpx
from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession

from devhub.auth_models import Identity, OIDCFlow, Session
from devhub.config import settings
from devhub.db import get_db
from devhub.models import User

router = APIRouter(prefix="/auth", tags=["authentication"])
IDLE_TIMEOUT = timedelta(minutes=30)
SESSION_LIFETIME = timedelta(hours=12)
FLOW_LIFETIME = timedelta(minutes=10)
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_email_adapter = TypeAdapter(EmailStr)
GITHUB_ISSUER = "https://github.com"
GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"
GITHUB_EMAILS = "https://api.github.com/user/emails"


class UserView(BaseModel):
    id: str
    email: str
    display_name: str


class SessionView(BaseModel):
    user: UserView | None
    csrf_token: str | None
    auth_mode: Literal["development", "github", "unconfigured"]


class DevelopmentLogin(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr = Field(max_length=254)
    display_name: str = Field(min_length=1, max_length=100)


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_loopback(hostname: str | None) -> bool:
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname or "").is_loopback
    except ValueError:
        return False


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid origin")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.scheme}://{parsed.hostname.lower()}:{port}"


def _development_enabled() -> bool:
    return (
        settings.dev_auth_enabled
        and settings.environment in {"development", "test"}
        and _is_loopback(urlsplit(settings.app_origin).hostname)
    )


def _github_configured() -> bool:
    return bool(settings.github_client_id.strip() and settings.github_client_secret.strip())


def auth_mode() -> Literal["development", "github", "unconfigured"]:
    if _development_enabled():
        return "development"
    if _github_configured():
        return "github"
    return "unconfigured"


def _secure_cookie() -> bool:
    return settings.environment not in {"development", "test"} or settings.app_origin.startswith("https://")


def _cookie_name() -> str:
    return "__Host-devhub_session" if _secure_cookie() else "devhub_session"


def _flow_cookie_name() -> str:
    return "__Host-devhub_oidc" if _secure_cookie() else "devhub_oidc"


def _private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"


def _check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    try:
        valid = origin is not None and _origin(origin) == _origin(settings.app_origin)
        if origin and (
            urlsplit(origin).path not in {"", "/"} or urlsplit(origin).query or urlsplit(origin).fragment
        ):
            valid = False
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(403, "Untrusted request origin")


def _get_session(request: Request, db: DatabaseSession) -> tuple[Session, User] | None:
    token = request.cookies.get(_cookie_name())
    if not token or len(token) > 128:
        return None
    now = _now()
    pair = db.execute(
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(
            Session.token_hash == _hash(token),
            Session.revoked_at.is_(None),
            Session.expires_at > now,
            Session.last_seen_at > now - IDLE_TIMEOUT,
            User.disabled.is_(False),
        )
    ).first()
    return (pair[0], pair[1]) if pair else None


def require_user(request: Request, db: DatabaseSession = Depends(get_db)) -> User:
    pair = _get_session(request, db)
    if pair is None:
        raise HTTPException(401, "Authentication required")
    session, user = pair
    if request.method in UNSAFE_METHODS:
        _check_origin(request)
        token = request.headers.get("x-csrf-token", "")
        if not token or not hmac.compare_digest(token, session.csrf_token):
            raise HTTPException(403, "Invalid CSRF token")
    session.last_seen_at = _now()
    request.state.auth_session = session
    return user


def _session_view(user: User | None = None, session: Session | None = None) -> SessionView:
    return SessionView(
        user=UserView(id=user.id, email=user.email, display_name=user.display_name) if user else None,
        csrf_token=session.csrf_token if session else None,
        auth_mode=auth_mode(),
    )


def _new_session(request: Request, response: Response, db: DatabaseSession, user: User) -> Session:
    if user.disabled:
        raise HTTPException(403, "Account unavailable")
    previous = request.cookies.get(_cookie_name())
    now = _now()
    if previous and len(previous) <= 128:
        db.execute(update(Session).where(Session.token_hash == _hash(previous)).values(revoked_at=now))
    token = secrets.token_urlsafe(32)
    session = Session(
        token_hash=_hash(token),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        created_at=now,
        last_seen_at=now,
        expires_at=now + SESSION_LIFETIME,
    )
    db.add(session)
    db.flush()
    response.set_cookie(
        _cookie_name(),
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        secure=_secure_cookie(),
        httponly=True,
        samesite="lax",
        path="/",
    )
    _private_response(response)
    return session


def _identity_user(db: DatabaseSession, issuer: str, subject: str, email: str, name: str) -> User:
    identity = db.scalar(select(Identity).where(Identity.issuer == issuer, Identity.subject == subject))
    if identity:
        user = db.get(User, identity.user_id)
        if user is None or user.disabled:
            raise HTTPException(403, "Account unavailable")
        return user
    # Email is never an account-linking key. Distinct provider subjects remain distinct users.
    try:
        with db.begin_nested():
            user = User(id=str(uuid4()), email=email, display_name=name, disabled=False, created_at=_now())
            db.add(user)
            db.flush()
            db.add(Identity(user_id=user.id, issuer=issuer, subject=subject))
            db.flush()
        return user
    except IntegrityError:
        # Concurrent first logins share the winning identity; the savepoint removes the losing user.
        identity = db.scalar(select(Identity).where(Identity.issuer == issuer, Identity.subject == subject))
        if identity is None:
            raise
        user = db.get(User, identity.user_id)
        if user is None or user.disabled:
            raise HTTPException(403, "Account unavailable")
        return user


@router.get("/session", response_model=SessionView)
def current_session(
    request: Request, response: Response, db: DatabaseSession = Depends(get_db)
) -> SessionView:
    _private_response(response)
    pair = _get_session(request, db)
    if not pair:
        return _session_view()
    session, user = pair
    session.last_seen_at = _now()
    return _session_view(user, session)


@router.post("/dev-login", response_model=SessionView)
def development_login(
    payload: DevelopmentLogin,
    request: Request,
    response: Response,
    db: DatabaseSession = Depends(get_db),
) -> SessionView:
    if not _development_enabled() or not _is_loopback(request.url.hostname):
        raise HTTPException(404, "Not found")
    _check_origin(request)
    email = str(payload.email).casefold()
    user = _identity_user(db, "urn:devhub:development", email, email, payload.display_name)
    session = _new_session(request, response, db, user)
    return _session_view(user, session)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    db: DatabaseSession = Depends(get_db),
) -> None:
    request.state.auth_session.revoked_at = _now()
    db.flush()
    response.delete_cookie(_cookie_name(), path="/", secure=_secure_cookie(), httponly=True, samesite="lax")
    _private_response(response)


def _github_json(client: httpx.Client, method: str, url: str, **kwargs):
    """Fixed callers only; bound responses and never follow credential-bearing redirects."""
    with client.stream(method, url, **kwargs) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("Unexpected GitHub redirect")
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > 262_144:
                raise ValueError("GitHub response too large")
    return json.loads(data)


def _exchange_code(code: str, verifier: str) -> dict:
    if not _github_configured():
        raise HTTPException(503, "GitHub sign-in is not configured")
    with httpx.Client(
        timeout=httpx.Timeout(10, connect=3),
        follow_redirects=False,
        trust_env=False,
        headers={"Accept": "application/json", "User-Agent": "DevHub"},
    ) as client:
        token = _github_json(
            client,
            "POST",
            GITHUB_TOKEN,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": settings.app_origin.rstrip("/") + "/auth/callback",
            },
        )
        if not isinstance(token, dict) or token.get("error"):
            raise ValueError("GitHub rejected the authorization code")
        access_token = token.get("access_token")
        if (
            not isinstance(access_token, str)
            or not access_token
            or len(access_token) > 4096
            or any(ord(c) < 33 or ord(c) > 126 for c in access_token)
            or str(token.get("token_type", "")).lower() != "bearer"
        ):
            raise ValueError("Invalid GitHub access token")
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
        profile = _github_json(client, "GET", GITHUB_USER, headers=headers)
        emails = _github_json(client, "GET", GITHUB_EMAILS, headers=headers, params={"per_page": 100})
    # The OAuth token is used only for these identity calls and is never persisted.
    if not isinstance(profile, dict) or type(profile.get("id")) is not int or profile["id"] <= 0:
        raise ValueError("Invalid GitHub user identity")
    if not isinstance(emails, list):
        raise ValueError("Invalid GitHub email response")
    primary = [
        item
        for item in emails
        if isinstance(item, dict) and item.get("primary") is True and item.get("verified") is True
    ]
    if len(primary) != 1:
        raise ValueError("A verified primary GitHub email is required")
    email = str(_email_adapter.validate_python(primary[0].get("email")))
    if len(email) > 254:
        raise ValueError("Invalid email")
    name = profile.get("name") or profile.get("login")
    name = name.strip()[:100] if isinstance(name, str) and name.strip() else email[:100]
    return {"sub": str(profile["id"]), "email": email, "name": name}


@router.get("/login")
def github_login(request: Request, db: DatabaseSession = Depends(get_db)) -> Response:
    if not _github_configured():
        raise HTTPException(503, "GitHub sign-in is not configured")
    state, verifier, browser = (secrets.token_urlsafe(32) for _ in range(3))
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    url = (
        GITHUB_AUTHORIZE
        + "?"
        + urlencode(
            {
                "client_id": settings.github_client_id,
                "redirect_uri": settings.app_origin.rstrip("/") + "/auth/callback",
                "scope": "read:user user:email",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )
    db.add(
        OIDCFlow(
            state_hash=_hash(state),
            # Retain the existing schema. This marker rejects pre-switch OIDC attempts.
            nonce="github-oauth",
            code_verifier=verifier,
            browser_hash=_hash(browser),
            expires_at=_now() + FLOW_LIFETIME,
        )
    )
    db.flush()
    response = Response(status_code=302, headers={"Location": url})
    response.set_cookie(
        _flow_cookie_name(),
        browser,
        max_age=int(FLOW_LIFETIME.total_seconds()),
        secure=_secure_cookie(),
        httponly=True,
        samesite="lax",
        path="/",
    )
    _private_response(response)
    return response


@router.get("/callback")
def github_callback(request: Request, db: DatabaseSession = Depends(get_db)) -> Response:
    state = request.query_params.get("state", "")
    browser = request.cookies.get(_flow_cookie_name(), "")
    if not state or not browser or len(state) > 128 or len(browser) > 128:
        raise HTTPException(400, "Invalid or expired sign-in attempt")
    if any(len(request.query_params.getlist(key)) > 1 for key in ("state", "code", "error", "iss")):
        raise HTTPException(400, "Invalid sign-in response")
    # Atomic delete + commit makes attempts single-use even if token exchange or validation fails.
    flow = db.execute(
        delete(OIDCFlow)
        .where(
            OIDCFlow.state_hash == _hash(state),
            OIDCFlow.browser_hash == _hash(browser),
            OIDCFlow.expires_at > _now(),
        )
        .returning(OIDCFlow.nonce, OIDCFlow.code_verifier)
    ).first()
    db.commit()
    if not flow or flow.nonce != "github-oauth":
        raise HTTPException(400, "Invalid or expired sign-in attempt")
    code = request.query_params.get("code", "")
    if request.query_params.get("error") or not code or len(code) > 4096:
        raise HTTPException(400, "Sign-in was not completed")
    try:
        claims = _exchange_code(code, flow.code_verifier)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Identity provider unavailable; restart sign-in") from exc
    except (ValueError, KeyError, ValidationError) as exc:
        raise HTTPException(400, "Invalid sign-in response; restart sign-in") from exc
    user = _identity_user(db, GITHUB_ISSUER, claims["sub"], claims["email"], claims["name"])
    response = Response(status_code=303, headers={"Location": "/"})
    _new_session(request, response, db, user)
    response.delete_cookie(
        _flow_cookie_name(), path="/", secure=_secure_cookie(), httponly=True, samesite="lax"
    )
    return response
