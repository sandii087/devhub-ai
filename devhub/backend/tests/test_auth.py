"""Session/OIDC security regressions; database tests use the migrated PostgreSQL test DB."""

from dataclasses import replace
from datetime import timedelta
import os
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey
import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from devhub import auth
from devhub.auth_models import Identity, OIDCFlow, Session
from devhub.db import get_db
from devhub.models import User

ORIGIN = "http://localhost:8000"
ISSUER = "https://identity.example.com"


@pytest.fixture
def auth_settings(monkeypatch):
    configured = replace(
        auth.settings,
        environment="test",
        dev_auth_enabled=True,
        app_origin=ORIGIN,
        oidc_issuer=ISSUER,
        oidc_client_id="devhub-test",
        oidc_client_secret="test-client-secret",
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
    assert auth_client.get("/auth/session").json()["auth_mode"] == "oidc"


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


@pytest.fixture
def provider_metadata():
    return {
        "issuer": ISSUER,
        "authorization_endpoint": ISSUER + "/authorize",
        "token_endpoint": ISSUER + "/token",
        "jwks_uri": ISSUER + "/keys",
        "code_challenge_methods_supported": ["S256"],
    }


def begin_oidc(client, monkeypatch, metadata):
    monkeypatch.setattr(auth, "_provider_metadata", lambda: metadata)
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302, response.text
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [ORIGIN + "/auth/callback"]
    assert "code_verifier" not in query
    return query


def test_oidc_callback_is_bound_to_browser_and_consumed_once(
    auth_client,
    auth_database,
    monkeypatch,
    provider_metadata,
):
    query = begin_oidc(auth_client, monkeypatch, provider_metadata)
    state = query["state"][0]
    original_browser = auth_client.cookies.get("devhub_oidc")
    calls = []

    def exchange(code, verifier, nonce):
        calls.append((code, verifier, nonce))
        assert len(verifier) >= 43 and nonce == query["nonce"][0]
        return {"sub": "subject-1", "email": "oidc@example.com", "name": "OIDC User"}

    monkeypatch.setattr(auth, "_exchange_code", exchange)
    auth_client.cookies.clear()
    auth_client.cookies.set("devhub_oidc", "another-browser")
    assert auth_client.get(f"/auth/callback?state={state}&code=code-1").status_code == 400
    assert not calls
    auth_client.cookies.clear()
    auth_client.cookies.set("devhub_oidc", original_browser)
    response = auth_client.get(f"/auth/callback?state={state}&code=code-1", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/"
    assert len(calls) == 1
    with auth_database() as db:
        assert db.get(OIDCFlow, auth._hash(state)) is None
        assert db.scalar(select(Identity).where(Identity.subject == "subject-1")) is not None
    auth_client.cookies.set("devhub_oidc", original_browser)
    assert auth_client.get(f"/auth/callback?state={state}&code=code-1").status_code == 400
    assert len(calls) == 1


def test_failed_oidc_validation_still_consumes_attempt(auth_client, monkeypatch, provider_metadata):
    query = begin_oidc(auth_client, monkeypatch, provider_metadata)
    calls = []

    def exchange(*args):
        calls.append(args)
        raise ValueError("Invalid signature")

    monkeypatch.setattr(auth, "_exchange_code", exchange)
    path = f"/auth/callback?state={query['state'][0]}&code=invalid"
    assert auth_client.get(path).status_code == 400
    assert auth_client.get(path).status_code == 400
    assert len(calls) == 1


def test_expired_oidc_attempt_is_rejected(auth_client, auth_database, monkeypatch, provider_metadata):
    query = begin_oidc(auth_client, monkeypatch, provider_metadata)
    with auth_database() as db:
        db.execute(update(OIDCFlow).values(expires_at=auth._now() - timedelta(seconds=1)))
        db.commit()
    monkeypatch.setattr(auth, "_exchange_code", lambda *_: pytest.fail("Expired flow reached provider"))
    assert auth_client.get(f"/auth/callback?state={query['state'][0]}&code=code").status_code == 400


def test_oidc_does_not_merge_existing_user_by_email(auth_client, monkeypatch, provider_metadata):
    local_id = login(auth_client)["user"]["id"]
    query = begin_oidc(auth_client, monkeypatch, provider_metadata)
    monkeypatch.setattr(
        auth,
        "_exchange_code",
        lambda *_: {
            "sub": "distinct-provider-subject",
            "email": "developer@example.com",
            "name": "OIDC Developer",
        },
    )
    response = auth_client.get(
        f"/auth/callback?state={query['state'][0]}&code=code",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert auth_client.get("/auth/session").json()["user"]["id"] != local_id


@pytest.fixture(scope="module")
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private, RSAKey.import_key(public, {"kid": "test-key"}).as_dict()


def signed_token(private, **overrides):
    now = int(auth._now().timestamp())
    claims = {
        "iss": ISSUER,
        "sub": "oidc-subject",
        "aud": "devhub-test",
        "iat": now,
        "exp": now + 300,
        "nonce": "expected-nonce",
        "email": "oidc@example.com",
        "email_verified": True,
        "name": "OIDC User",
    }
    claims.update(overrides)
    return jwt.encode({"alg": "RS256", "kid": "test-key"}, claims, RSAKey.import_key(private))


def test_provider_claim_validation_uses_signature_and_expected_claims(
    auth_settings,
    monkeypatch,
    provider_metadata,
    signing_key,
):
    private, public = signing_key
    monkeypatch.setattr(auth, "_provider_json", lambda _: {"keys": [public]})
    claims = auth._validated_claims({"id_token": signed_token(private)}, provider_metadata, "expected-nonce")
    assert claims["sub"] == "oidc-subject"


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.example"},
        {"aud": "another-client"},
        {"nonce": "another-attempt"},
        {"exp": 1},
        {"iat": 4_000_000_000},
        {"email_verified": False},
        {"sub": ""},
        {"azp": "another-client"},
    ],
)
def test_provider_claim_validation_rejects_wrong_claims(
    auth_settings,
    monkeypatch,
    provider_metadata,
    signing_key,
    overrides,
):
    private, public = signing_key
    monkeypatch.setattr(auth, "_provider_json", lambda _: {"keys": [public]})
    with pytest.raises((JoseError, ValueError)):
        auth._validated_claims(
            {"id_token": signed_token(private, **overrides)}, provider_metadata, "expected-nonce"
        )


def test_provider_claim_validation_rejects_wrong_signature(
    auth_settings,
    monkeypatch,
    provider_metadata,
    signing_key,
):
    private, _ = signing_key
    other_key = RSAKey.generate_key(2048, {"kid": "test-key"})
    monkeypatch.setattr(auth, "_provider_json", lambda _: {"keys": [other_key.as_dict(private=False)]})
    with pytest.raises(JoseError):
        auth._validated_claims({"id_token": signed_token(private)}, provider_metadata, "expected-nonce")


@pytest.mark.parametrize(
    "field,value",
    [
        ("issuer", "https://attacker.example"),
        ("token_endpoint", "http://identity.example.com/token"),
        ("jwks_uri", "https://attacker.example/keys"),
        ("code_challenge_methods_supported", ["plain"]),
    ],
)
def test_discovery_rejects_untrusted_endpoints_and_missing_pkce(
    auth_settings,
    monkeypatch,
    provider_metadata,
    field,
    value,
):
    monkeypatch.setattr(auth, "_provider_json", lambda _: {**provider_metadata, field: value})
    with pytest.raises(ValueError):
        auth._provider_metadata()


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
    assert auth.auth_mode() == "oidc"
