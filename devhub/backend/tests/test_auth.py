"""Session/GitHub OAuth security regressions; database tests use the migrated PostgreSQL test DB."""

import base64
import hashlib
import httpx
from dataclasses import replace
from datetime import timedelta
import os
from urllib.parse import parse_qs, urlsplit

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from devhub import auth
from devhub.auth_models import Identity, OIDCFlow, Session
from devhub.db import get_db
from devhub.models import User

ORIGIN = "http://localhost:8000"


@pytest.fixture
def auth_settings(monkeypatch):
    configured = replace(
        auth.settings,
        environment="test",
        dev_auth_enabled=True,
        app_origin=ORIGIN,
        github_client_id="devhub-test",
        github_client_secret="test-client-secret",
    )
    monkeypatch.setattr(auth, "settings", configured)
    return configured


@pytest.fixture
def auth_database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL must point to a migrated PostgreSQL test database")
    engine = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with engine.connect() as connection:
        transaction = connection.begin()
        factory = sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield factory
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def auth_client(auth_settings, auth_database):
    app = FastAPI()
    app.include_router(auth.router)

    def override_database():
        with auth_database() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override_database

    @app.get("/private")
    def private(user=Depends(auth.require_user)):
        return {"id": user.id}

    @app.post("/private")
    def private_mutation(user=Depends(auth.require_user)):
        return {"id": user.id}

    with TestClient(app, base_url=ORIGIN) as client:
        yield client


def login(client):
    response = client.post(
        "/auth/dev-login",
        json={"email": "developer@example.com", "display_name": "Developer"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_session_cookie_is_hashed_and_only_profile_is_exposed(auth_client, auth_database):
    anonymous = auth_client.get("/auth/session")
    assert anonymous.json() == {"user": None, "csrf_token": None, "auth_mode": "development"}
    assert anonymous.headers["cache-control"] == "no-store"
    response = auth_client.post(
        "/auth/dev-login",
        json={"email": "developer@example.com", "display_name": "Developer"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert "Domain=" not in cookie
    value = auth_client.cookies.get("devhub_session")
    with auth_database() as db:
        stored = db.get(Session, auth._hash(value))
        assert stored is not None and stored.token_hash != value
    assert set(response.json()["user"]) == {"id", "email", "display_name"}
    assert auth_client.get("/private").status_code == 200


@pytest.mark.parametrize("headers", [{}, {"Origin": ORIGIN}, {"Origin": "https://attacker.example"}])
def test_mutation_rejects_missing_token_or_bad_origin(auth_client, headers):
    session = login(auth_client)
    if "attacker" in headers.get("Origin", ""):
        headers = {**headers, "X-CSRF-Token": session["csrf_token"]}
    assert auth_client.post("/private", headers=headers).status_code == 403


def test_logout_revokes_cookie_and_replay_fails(auth_client, auth_database):
    session = login(auth_client)
    original = auth_client.cookies.get("devhub_session")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}
    assert auth_client.post("/private", headers=headers).status_code == 200
    assert auth_client.post("/auth/logout", headers=headers).status_code == 204
    with auth_database() as db:
        assert db.get(Session, auth._hash(original)).revoked_at is not None
    auth_client.cookies.set("devhub_session", original)
    assert auth_client.get("/private").status_code == 401


def test_login_rotates_existing_session(auth_client, auth_database):
    first = login(auth_client)
    original = auth_client.cookies.get("devhub_session")
    second = login(auth_client)
    assert original != auth_client.cookies.get("devhub_session")
    assert first["csrf_token"] != second["csrf_token"]
    assert first["user"]["id"] == second["user"]["id"]
    with auth_database() as db:
        assert db.get(Session, auth._hash(original)).revoked_at is not None


@pytest.mark.parametrize("reason", ["idle", "absolute", "revoked", "disabled"])
def test_expired_revoked_or_disabled_session_is_rejected(auth_client, auth_database, reason):
    session = login(auth_client)
    with auth_database() as db:
        stored = db.get(Session, auth._hash(auth_client.cookies.get("devhub_session")))
        if reason == "idle":
            stored.last_seen_at = auth._now() - timedelta(minutes=31)
        elif reason == "absolute":
            stored.expires_at = auth._now() - timedelta(seconds=1)
        elif reason == "revoked":
            stored.revoked_at = auth._now()
        else:
            db.get(User, session["user"]["id"]).disabled = True
        db.commit()
    assert auth_client.get("/private").status_code == 401
    assert auth_client.get("/auth/session").json()["user"] is None


@pytest.mark.parametrize(
    "environment,enabled,origin",
    [
        ("production", True, ORIGIN),
        ("test", False, ORIGIN),
        ("development", True, "https://public.example.com"),
    ],
)
def test_development_login_cannot_fall_back_in_unsafe_configuration(
    auth_client,
    monkeypatch,
    auth_settings,
    environment,
    enabled,
    origin,
):
    monkeypatch.setattr(
        auth,
        "settings",
        replace(
            auth_settings,
            environment=environment,
            dev_auth_enabled=enabled,
            app_origin=origin,
        ),
    )
    response = auth_client.post(
        "/auth/dev-login",
        json={"email": "developer@example.com", "display_name": "Developer"},
        headers={"Origin": origin},
    )
    assert response.status_code == 404
    assert auth_client.get("/auth/session").json()["auth_mode"] == "github"


def test_development_login_rejects_cross_origin_and_extra_fields(auth_client):
    payload = {"email": "developer@example.com", "display_name": "Developer"}
    assert auth_client.post("/auth/dev-login", json=payload).status_code == 403
    assert (
        auth_client.post(
            "/auth/dev-login",
            json={**payload, "role": "owner"},
            headers={"Origin": ORIGIN},
        ).status_code
        == 422
    )


def begin_github(client):
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302, response.text
    location = urlsplit(response.headers["location"])
    assert location.scheme + "://" + location.netloc + location.path == auth.GITHUB_AUTHORIZE
    query = parse_qs(location.query)
    assert query["scope"] == ["read:user user:email"]
    assert query["client_id"] == ["devhub-test"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [ORIGIN + "/auth/callback"]
    assert len(query["state"][0]) >= 43
    assert "code_verifier" not in query and "client_secret" not in query and "nonce" not in query
    return query


@pytest.fixture
def github_transport(monkeypatch):
    original = httpx.Client
    calls = []
    responses = {
        auth.GITHUB_TOKEN: {"access_token": "test-access-token", "token_type": "bearer"},
        auth.GITHUB_USER: {
            "id": 12345,
            "login": "octocat",
            "name": "GitHub User",
            "email": "untrusted@example.com",
        },
        auth.GITHUB_EMAILS: [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ],
    }

    def handle(request):
        calls.append(request)
        url = str(request.url.copy_with(query=None))
        assert url in responses, "Unexpected external endpoint"
        result = responses[url]
        if isinstance(result, Exception):
            raise result
        if isinstance(result, httpx.Response):
            return result
        return httpx.Response(200, json=result)

    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return original(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(httpx, "Client", client)
    return responses, calls


def test_github_state_pkce_and_success_reuses_existing_identity(auth_client, auth_database, github_transport):
    _, calls = github_transport
    user_ids = []
    states = []
    for _ in range(2):
        query = begin_github(auth_client)
        state = query["state"][0]
        states.append(state)
        with auth_database() as db:
            flow = db.get(OIDCFlow, auth._hash(state))
            assert flow.state_hash != state
            assert flow.browser_hash == auth._hash(auth_client.cookies.get(auth._flow_cookie_name()))
            assert auth._now() < flow.expires_at <= auth._now() + auth.FLOW_LIFETIME
            verifier = flow.code_verifier
            assert query["code_challenge"] == [
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            ]
        response = auth_client.get(f"/auth/callback?state={state}&code=valid", follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/"
        assert "HttpOnly" in response.headers["set-cookie"]
        session = auth_client.get("/auth/session").json()
        user_ids.append(session["user"]["id"])
        assert session["user"]["email"] == "primary@example.com"
        assert session["csrf_token"]
        assert "test-access-token" not in response.text + str(response.headers) + str(session)
        with auth_database() as db:
            assert db.get(OIDCFlow, auth._hash(state)) is None
            identity = db.scalar(
                select(Identity).where(Identity.issuer == "https://github.com", Identity.subject == "12345")
            )
            assert identity.user_id == user_ids[-1]
            assert db.get(User, identity.user_id) is not None
            assert (
                db.get(Session, auth._hash(auth_client.cookies.get(auth._cookie_name()))).user_id
                == identity.user_id
            )
        exchange = calls[-3]
        assert exchange.method == "POST" and not exchange.url.query
        body = parse_qs(exchange.content.decode())
        assert body["code_verifier"] == [verifier]
        assert body["client_id"] == ["devhub-test"]
        assert body["client_secret"] == [auth.settings.github_client_secret]
        assert body["redirect_uri"] == [ORIGIN + "/auth/callback"]
        assert exchange.headers["accept"] == "application/json"
        for profile_call in calls[-2:]:
            assert profile_call.method == "GET"
            assert profile_call.headers["authorization"] == "Bearer test-access-token"
    assert states[0] != states[1] and user_ids[0] == user_ids[1]


def test_callback_browser_binding_and_replay(auth_client, github_transport):
    _, calls = github_transport
    state = begin_github(auth_client)["state"][0]
    browser = auth_client.cookies.get(auth._flow_cookie_name())
    auth_client.cookies.clear()
    path = f"/auth/callback?state={state}&code=valid"
    assert auth_client.get(path).status_code == 400
    auth_client.cookies.set(auth._flow_cookie_name(), "another-browser")
    assert auth_client.get(path).status_code == 400
    assert not calls
    auth_client.cookies.clear()
    auth_client.cookies.set(auth._flow_cookie_name(), browser)
    assert auth_client.get(path, follow_redirects=False).status_code == 303
    auth_client.cookies.set(auth._flow_cookie_name(), browser)
    assert auth_client.get(path).status_code == 400
    assert len(calls) == 3


@pytest.mark.parametrize(
    "query",
    [
        "",
        "code=valid",
        "state=invalid&code=valid",
        "state={state}&state=other&code=valid",
        "state={state}&code=one&code=two",
    ],
)
def test_invalid_callback_state(auth_client, github_transport, query):
    _, calls = github_transport
    state = begin_github(auth_client)["state"][0]
    assert auth_client.get("/auth/callback?" + query.format(state=state)).status_code == 400
    assert not calls


@pytest.mark.parametrize("suffix", ["", "&error=access_denied", "&code=" + "x" * 4097])
def test_missing_code_or_denial_consumes_flow(auth_client, auth_database, github_transport, suffix):
    _, calls = github_transport
    state = begin_github(auth_client)["state"][0]
    assert auth_client.get(f"/auth/callback?state={state}{suffix}").status_code == 400
    with auth_database() as db:
        assert db.get(OIDCFlow, auth._hash(state)) is None
    assert not calls


@pytest.mark.parametrize("change", ["expired", "old_oidc"])
def test_expired_or_legacy_flow_rejected(auth_client, auth_database, github_transport, change):
    _, calls = github_transport
    state = begin_github(auth_client)["state"][0]
    with auth_database() as db:
        values = (
            {"expires_at": auth._now() - timedelta(seconds=1)}
            if change == "expired"
            else {"nonce": "old-nonce"}
        )
        db.execute(update(OIDCFlow).where(OIDCFlow.state_hash == auth._hash(state)).values(**values))
        db.commit()
    assert auth_client.get(f"/auth/callback?state={state}&code=valid").status_code == 400
    assert not calls


@pytest.mark.parametrize(
    "endpoint,result,status",
    [
        (
            auth.GITHUB_TOKEN,
            {"error": "bad_verification_code", "error_description": "sensitive-provider-data"},
            400,
        ),
        (auth.GITHUB_TOKEN, {"access_token": "", "token_type": "bearer"}, 400),
        (auth.GITHUB_TOKEN, {"access_token": "token", "token_type": "unknown"}, 400),
        (auth.GITHUB_TOKEN, httpx.Response(500), 503),
        (auth.GITHUB_TOKEN, httpx.ReadTimeout("sensitive-provider-data"), 503),
        (auth.GITHUB_TOKEN, httpx.Response(302, headers={"location": "https://attacker.example"}), 400),
        (auth.GITHUB_USER, httpx.Response(401), 503),
        (auth.GITHUB_USER, {"id": True}, 400),
        (auth.GITHUB_USER, {"id": "12345"}, 400),
        (auth.GITHUB_USER, [], 400),
        (auth.GITHUB_EMAILS, httpx.Response(403), 503),
        (auth.GITHUB_EMAILS, httpx.Response(429), 503),
        (auth.GITHUB_EMAILS, httpx.Response(200, text="not-json"), 400),
        (auth.GITHUB_EMAILS, httpx.Response(200, content=b"x" * 262145), 400),
    ],
)
def test_provider_errors_are_safe_and_single_use(
    auth_client, auth_database, github_transport, endpoint, result, status, caplog
):
    responses, calls = github_transport
    responses[endpoint] = result
    state = begin_github(auth_client)["state"][0]
    browser = auth_client.cookies.get(auth._flow_cookie_name())
    path = f"/auth/callback?state={state}&code=valid"
    response = auth_client.get(path)
    assert response.status_code == status
    assert "sensitive-provider-data" not in response.text + caplog.text
    assert "test-access-token" not in response.text + caplog.text
    assert auth.settings.github_client_secret not in response.text + caplog.text
    assert auth_client.get("/auth/session").json()["user"] is None
    with auth_database() as db:
        assert db.get(OIDCFlow, auth._hash(state)) is None
    auth_client.cookies.set(auth._flow_cookie_name(), browser)
    assert auth_client.get(path).status_code == 400
    assert sum(str(call.url) == auth.GITHUB_TOKEN for call in calls) == 1


@pytest.mark.parametrize(
    "emails",
    [
        [],
        {},
        [None],
        [{"email": "primary@example.com", "primary": True, "verified": False}],
        [{"email": "secondary@example.com", "primary": False, "verified": True}],
        [{"email": "bad-email", "primary": True, "verified": True}],
        [{"primary": True, "verified": True}],
    ],
)
def test_no_verified_primary_email_rejected(auth_client, auth_database, github_transport, emails):
    responses, _ = github_transport
    responses[auth.GITHUB_EMAILS] = emails
    state = begin_github(auth_client)["state"][0]
    assert auth_client.get(f"/auth/callback?state={state}&code=valid").status_code == 400
    with auth_database() as db:
        assert db.scalar(select(Identity).where(Identity.issuer == auth.GITHUB_ISSUER)) is None


def test_github_does_not_merge_by_email(auth_client, github_transport):
    local_id = login(auth_client)["user"]["id"]
    responses, _ = github_transport
    responses[auth.GITHUB_EMAILS] = [{"email": "developer@example.com", "primary": True, "verified": True}]
    responses[auth.GITHUB_USER]["name"] = None
    state = begin_github(auth_client)["state"][0]
    assert (
        auth_client.get(f"/auth/callback?state={state}&code=valid", follow_redirects=False).status_code == 303
    )
    user = auth_client.get("/auth/session").json()["user"]
    assert user["id"] != local_id and user["display_name"] == "octocat"


def test_missing_credentials_disable_login(auth_client, auth_settings, monkeypatch, github_transport):
    monkeypatch.setattr(
        auth, "settings", replace(auth_settings, dev_auth_enabled=False, github_client_secret="")
    )
    assert auth_client.get("/auth/session").json()["auth_mode"] == "unconfigured"
    assert auth_client.get("/auth/login").status_code == 503
    assert not github_transport[1]


def test_production_cookie_uses_host_prefix_and_secure(auth_settings, monkeypatch):
    monkeypatch.setattr(
        auth,
        "settings",
        replace(
            auth_settings,
            environment="production",
            dev_auth_enabled=False,
            app_origin="https://devhub.example.com",
        ),
    )
    assert auth._cookie_name() == "__Host-devhub_session"
    assert auth._secure_cookie()
    assert auth.auth_mode() == "github"
