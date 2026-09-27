from dataclasses import replace
from datetime import timedelta
import json
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest
from sqlalchemy import func, select, update

from devhub import auth, auth_mail, email_auth, google_auth, main
from devhub.auth_models import EmailToken, Identity, OIDCFlow, PasswordCredential, Session
from devhub.db import get_db
from devhub.models import User

ORIGIN = "http://localhost:8000"
PASSWORD = "A unique river lantern passphrase!"  # pragma: allowlist secret
NEW_PASSWORD = "Another safe mountain lantern phrase!"  # pragma: allowlist secret


class CapturedMail(list):
    def __repr__(self):
        return "<captured synthetic email messages>"


@pytest.fixture
def account_client(database, monkeypatch):
    config = replace(
        auth.settings,
        environment="test",
        dev_auth_enabled=False,
        app_origin=ORIGIN,
        email_auth_enabled=True,
        resend_api_key="test-mail",  # pragma: allowlist secret -- synthetic fixture
        email_from="noreply@example.com",
        google_client_id="test-google",
        google_client_secret="test-google-secret",  # pragma: allowlist secret
        github_client_id="test-github",
        github_client_secret="test-github-secret",  # pragma: allowlist secret -- synthetic fixture
    )  # pragma: allowlist secret
    for module in (auth, auth_mail, email_auth, google_auth, main):
        monkeypatch.setattr(module, "settings", config)
    app = main.create_app()

    def override():
        with database() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override
    mail = CapturedMail()
    monkeypatch.setattr(auth_mail, "send_auth_email", lambda *args: mail.append(args))
    client = TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN})
    yield client, mail
    client.close()


def signup(client, email="person@example.com"):
    return client.post("/auth/signup", json={"email": email, "password": PASSWORD, "display_name": "Person"})


def verified(account_client):
    client, mail = account_client
    assert signup(client).status_code == 202
    assert (
        client.post("/auth/verify-email", json={"token": mail[-1][1], "password": PASSWORD}).status_code
        == 200
    )
    return client, mail


def login(client, password=PASSWORD):
    return client.post("/auth/email-login", json={"email": "PERSON@example.com", "password": password})


def test_signup_verification_login_logout_and_protected_routes(account_client, database):
    client, mail = account_client
    assert client.get("/api/v1/organizations").status_code == 401
    assert signup(client).status_code == 202
    assert len(mail) == 1 and mail[0][2] == "verify"
    assert login(client).status_code == 401
    token = mail[0][1]
    with database() as db:
        credential = db.scalar(
            select(PasswordCredential).where(PasswordCredential.email == "person@example.com")
        )
        assert credential.password_hash.startswith("scrypt-v1$") and PASSWORD not in credential.password_hash
        assert db.get(EmailToken, auth._hash(token)) is not None
        assert db.get(EmailToken, token) is None
    assert client.post("/auth/verify-email", json={"token": token, "password": PASSWORD}).status_code == 200
    assert client.post("/auth/verify-email", json={"token": token, "password": PASSWORD}).status_code == 400
    response = login(client)
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/v1/organizations").status_code == 200
    assert client.post("/auth/logout").status_code == 403
    assert (
        client.post("/auth/logout", headers={"X-CSRF-Token": response.json()["csrf_token"]}).status_code
        == 204
    )
    assert client.get("/api/v1/organizations").status_code == 401


def test_reset_generic_single_use_and_revokes_sessions(account_client, database):
    client, mail = verified(account_client)
    assert login(client).status_code == 200
    known = client.post("/auth/forgot-password", json={"email": "person@example.com"})
    token = mail[-1][1]
    unknown = client.post("/auth/forgot-password", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    assert len(mail) == 2
    reset = {"token": token, "password": NEW_PASSWORD}
    assert client.post("/auth/reset-password", json=reset).status_code == 200
    assert client.get("/auth/session").json()["user"] is None
    assert client.post("/auth/reset-password", json=reset).status_code == 400
    assert login(client).status_code == 401
    assert login(client, NEW_PASSWORD).status_code == 200
    with database() as db:
        assert (
            db.scalar(select(func.count()).select_from(Session).where(Session.revoked_at.is_not(None))) >= 1
        )


def test_invalid_expired_and_superseded_reset_tokens(account_client, database):
    client, mail = verified(account_client)
    for _ in range(2):
        assert client.post("/auth/forgot-password", json={"email": "person@example.com"}).status_code == 202
    assert (
        client.post("/auth/reset-password", json={"token": mail[-2][1], "password": NEW_PASSWORD}).status_code
        == 400
    )
    with database() as db:
        db.execute(update(EmailToken).values(expires_at=auth._now() - timedelta(minutes=1)))
        db.commit()
    assert (
        client.post("/auth/reset-password", json={"token": mail[-1][1], "password": NEW_PASSWORD}).status_code
        == 400
    )
    assert (
        client.post("/auth/reset-password", json={"token": "x" * 43, "password": NEW_PASSWORD}).status_code
        == 400
    )


def test_duplicate_signup_and_validation(account_client, database):
    client, mail = account_client
    response = signup(client)
    assert signup(client, "PERSON@example.com").json() == response.json()
    assert len(mail) == 1
    with database() as db:
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.email == "person@example.com")) == 1
        )
    assert (
        client.post(
            "/auth/signup", json={"email": "bad", "password": PASSWORD, "display_name": "A"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/auth/signup",
            json={
                "email": "a@example.com",
                "password": "short",  # pragma: allowlist secret -- deliberately invalid test input
                "display_name": "A",
            },  # pragma: allowlist secret
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/auth/email-login",
            json={"email": "person@example.com", "password": PASSWORD},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )


def test_email_owner_selects_final_password_and_resend(account_client):
    client, mail = account_client
    signup(client)
    first = mail[-1][1]
    assert client.post("/auth/resend-verification", json={"email": "person@example.com"}).status_code == 202
    assert client.post("/auth/verify-email", json={"token": first, "password": PASSWORD}).status_code == 400
    assert (
        client.post("/auth/verify-email", json={"token": mail[-1][1], "password": NEW_PASSWORD}).status_code
        == 200
    )
    assert login(client).status_code == 401
    assert login(client, NEW_PASSWORD).status_code == 200


def test_password_rate_limit_and_disabled_user(account_client, database):
    client, _ = verified(account_client)
    with database() as db:
        db.execute(update(User).values(disabled=True))
        db.commit()
    assert login(client).status_code == 401
    for _ in range(4):
        assert login(client, "wrong").status_code == 401
    assert login(client).status_code == 429


def test_missing_email_configuration_fails_closed(account_client, monkeypatch):
    client, mail = account_client
    monkeypatch.setattr(auth_mail, "settings", replace(auth_mail.settings, resend_api_key=""))
    assert signup(client).status_code == 503
    assert not mail


@pytest.fixture
def google_provider(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update(kid="test-key", alg="RS256", use="sig")
    state = {
        "nonce": "",
        "email": "google@example.com",
        "sub": "google-person",
        "failure": None,
        "claims": {},
    }
    original = httpx.Client
    calls = []

    def handle(request):
        calls.append(request)
        if str(request.url) == "https://oauth2.googleapis.com/token":
            if state["failure"]:
                return httpx.Response(400, json={"error": "invalid_grant"})
            now = auth._now()
            claims = {
                "iss": "https://accounts.google.com",
                "aud": "test-google",
                "sub": state["sub"],
                "exp": now + timedelta(minutes=5),
                "iat": now,
                "nonce": state["nonce"],
                "email": state["email"],
                "email_verified": True,
                "name": "Google Person",
                **state["claims"],
            }
            signing = (
                rsa.generate_private_key(public_exponent=65537, key_size=2048)
                if state.get("bad_signature")
                else private
            )
            encoded = jwt.encode(claims, signing, algorithm="RS256", headers={"kid": "test-key"})
            return httpx.Response(200, json={"id_token": encoded})
        assert str(request.url) == "https://www.googleapis.com/oauth2/v3/certs"
        return httpx.Response(200, json={"keys": [public]})

    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs)
    )
    return state, calls


def begin_google(client, provider):
    response = client.get("/auth/google/login", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert urlsplit(response.headers["location"]).netloc == "accounts.google.com"
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [ORIGIN + "/auth/google/callback"]
    provider["nonce"] = query["nonce"][0]
    return query["state"][0]


def test_google_signup_login_and_replay(account_client, google_provider, database):
    client, _ = account_client
    provider, calls = google_provider
    ids = []
    for _ in range(2):
        state = begin_google(client, provider)
        path = f"/auth/google/callback?state={state}&code=good"
        assert client.get(path, follow_redirects=False).status_code == 303
        ids.append(client.get("/auth/session").json()["user"]["id"])
        assert client.get(path).status_code == 400
    assert ids[0] == ids[1] and len(calls) == 4
    body = parse_qs(calls[0].content.decode())
    assert body["code_verifier"] and body["grant_type"] == ["authorization_code"]
    with database() as db:
        assert (
            db.scalar(select(Identity).where(Identity.user_id == ids[0])).issuer
            == "https://accounts.google.com"
        )


@pytest.mark.parametrize(
    "claims",
    [
        {"nonce": "wrong"},
        {"aud": "wrong"},
        {"iss": "https://evil.example"},
        {"email_verified": False},
        {"exp": 1},
        {"sub": ""},
    ],
)
def test_google_rejects_invalid_claims(account_client, google_provider, claims):
    client, _ = account_client
    provider, _ = google_provider
    state = begin_google(client, provider)
    provider["claims"] = claims
    assert client.get(f"/auth/google/callback?state={state}&code=bad").status_code == 400


def test_google_cancel_state_browser_expiry_and_provider_error(account_client, google_provider, database):
    client, _ = account_client
    provider, calls = google_provider
    assert client.get("/auth/google/callback?code=bad").status_code == 400
    state = begin_google(client, provider)
    assert client.get(f"/auth/google/callback?state={state}&error=access_denied").status_code == 400
    assert not calls
    state = begin_google(client, provider)
    with database() as db:
        db.execute(update(OIDCFlow).values(expires_at=auth._now() - timedelta(minutes=1)))
        db.commit()
    assert client.get(f"/auth/google/callback?state={state}&code=good").status_code == 400
    state = begin_google(client, provider)
    provider["failure"] = True
    assert client.get(f"/auth/google/callback?state={state}&code=good").status_code == 503
    assert client.get(f"/auth/google/callback?state={state}&code=good").status_code == 400
    state = begin_google(client, provider)
    client.cookies.clear()
    assert client.get(f"/auth/google/callback?state={state}&code=good").status_code == 400


def test_explicit_linking_reuses_existing_account(account_client, google_provider, database):
    client, _ = verified(account_client)
    session = login(client).json()
    provider, _ = google_provider
    provider["email"] = "person@example.com"
    state = begin_google(client, provider)
    assert (
        client.get(f"/auth/google/callback?state={state}&code=good", follow_redirects=False).status_code
        == 409
    )
    assert client.post("/auth/link/google").status_code == 403
    response = client.post("/auth/link/google", headers={"X-CSRF-Token": session["csrf_token"]})
    assert response.status_code == 200
    query = parse_qs(urlsplit(response.json()["url"]).query)
    provider["nonce"] = query["nonce"][0]
    assert (
        client.get(
            f"/auth/google/callback?state={query['state'][0]}&code=good", follow_redirects=False
        ).status_code
        == 303
    )
    assert client.get("/auth/session").json()["user"]["id"] == session["user"]["id"]
    with database() as db:
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.email == "person@example.com")) == 1
        )


def test_link_rejects_swapped_session_and_old_login(account_client, google_provider, database):
    client, _ = verified(account_client)
    session = login(client).json()
    result = client.post("/auth/link/google", headers={"X-CSRF-Token": session["csrf_token"]})
    query = parse_qs(urlsplit(result.json()["url"]).query)
    google_provider[0]["nonce"] = query["nonce"][0]
    client.cookies.delete(auth._cookie_name())
    assert client.get(f"/auth/google/callback?state={query['state'][0]}&code=good").status_code == 403
    session = login(client).json()
    with database() as db:
        db.execute(update(Session).values(created_at=auth._now() - timedelta(minutes=6)))
        db.commit()
    assert (
        client.post("/auth/link/google", headers={"X-CSRF-Token": session["csrf_token"]}).status_code == 403
    )


def test_browser_callback_error_returns_safe_login_url(account_client):
    client, _ = account_client
    response = client.get(
        "/auth/google/callback?error=access_denied", headers={"Accept": "text/html"}, follow_redirects=False
    )
    assert response.status_code == 303 and response.headers["location"] == "/#auth-error=retry"


def test_google_rejects_bad_signature_and_cross_provider_state(account_client, google_provider):
    client, _ = account_client
    provider, calls = google_provider
    state = begin_google(client, provider)
    assert client.get(f"/auth/callback?state={state}&code=wrong-provider").status_code == 400
    assert not calls
    state = begin_google(client, provider)
    provider["bad_signature"] = True
    assert client.get(f"/auth/google/callback?state={state}&code=bad-signature").status_code == 400


def test_provider_already_connected_to_another_account_cannot_be_taken_over(account_client, google_provider):
    client, _ = account_client
    provider, _ = google_provider
    state = begin_google(client, provider)
    assert (
        client.get(f"/auth/google/callback?state={state}&code=good", follow_redirects=False).status_code
        == 303
    )
    verified(account_client)
    session = login(client).json()
    response = client.post("/auth/link/google", headers={"X-CSRF-Token": session["csrf_token"]})
    query = parse_qs(urlsplit(response.json()["url"]).query)
    provider["nonce"] = query["nonce"][0]
    assert (
        client.get(
            f"/auth/google/callback?state={query['state'][0]}&code=good", follow_redirects=False
        ).status_code
        == 409
    )


def test_mail_adapter_uses_fragment_and_redacts_failures(monkeypatch, caplog):
    config = replace(
        auth_mail.settings,
        app_origin=ORIGIN,
        resend_api_key="unit-test-key",  # pragma: allowlist secret -- synthetic fixture
        email_from="sender@example.com",
    )  # pragma: allowlist secret
    monkeypatch.setattr(auth_mail, "settings", config)
    original = httpx.Client
    captured = []

    def handle(request):
        assert str(request.url) == "https://api.resend.com/emails"
        captured.append(json.loads(request.content))
        return httpx.Response(500, text="provider error including token-do-not-log")

    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs)
    )
    auth_mail.send_auth_email("person@example.com", "token-do-not-log", "reset")
    assert ORIGIN + "/#reset-password=token-do-not-log" in captured[0]["text"]
    assert "Authentication email delivery failed" in caplog.text
    assert "token-do-not-log" not in caplog.text and "unit-test-key" not in caplog.text


def test_google_only_configuration_does_not_require_oidc_or_github(account_client, monkeypatch):
    client, _ = account_client
    monkeypatch.setattr(
        auth,
        "settings",
        replace(auth.settings, github_client_id="", github_client_secret="", email_auth_enabled=False),
    )
    result = client.get("/auth/session").json()
    assert result["providers"] == ["google"] and result["auth_mode"] == "configured"
