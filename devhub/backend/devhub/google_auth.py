"""Google authorization-code flow with PKCE and verified signed ID tokens.

No operator OIDC issuer setting: endpoints and issuers are pinned to Google.
"""

import hmac
import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DatabaseSession

from devhub import auth
from devhub.config import settings
from devhub.db import get_db

router = APIRouter(prefix="/auth/google", tags=["authentication"])


def exchange(code, verifier, nonce):
    with httpx.Client(
        timeout=httpx.Timeout(10, connect=3), trust_env=False, follow_redirects=False
    ) as client:
        result = auth._github_json(
            client,
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": settings.app_origin.rstrip("/") + "/auth/google/callback",
            },
        )
        if not isinstance(result, dict) or result.get("error") or not isinstance(result.get("id_token"), str):
            raise ValueError("Invalid Google token response")
        encoded = result["id_token"]
        if len(encoded) > 16384:
            raise ValueError("Invalid Google ID token")
        header = jwt.get_unverified_header(encoded)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise ValueError("Invalid Google signing key")
        keys = auth._github_json(client, "GET", "https://www.googleapis.com/oauth2/v3/certs")
        key = next((key for key in jwt.PyJWKSet.from_dict(keys).keys if key.key_id == header["kid"]), None)
        if key is None:
            raise ValueError("Unknown Google signing key")
        claims = jwt.decode(
            encoded,
            key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=["https://accounts.google.com", "accounts.google.com"],
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
        )
    if not isinstance(claims["nonce"], str) or not hmac.compare_digest(claims["nonce"], nonce):
        raise ValueError("Invalid nonce")
    if claims.get("azp", settings.google_client_id) != settings.google_client_id:
        raise ValueError("Invalid authorized party")
    if (
        claims.get("email_verified") is not True
        or not isinstance(claims["sub"], str)
        or not 1 <= len(claims["sub"]) <= 255
    ):
        raise ValueError("Verified Google identity required")
    email = str(auth._email_adapter.validate_python(claims.get("email")))
    if len(email) > 254:
        raise ValueError("Invalid email")
    name = claims.get("name")
    return {
        "sub": claims["sub"],
        "email": email,
        "name": name[:100] if isinstance(name, str) and name else email[:100],
    }


@router.get("/login")
def login(db: DatabaseSession = Depends(get_db)):
    return auth.begin_oauth(db, "google")


@router.get("/callback")
def callback(request: Request, db: DatabaseSession = Depends(get_db)):
    flow, code = auth.consume_oauth(request, db, "google")
    try:
        claims = exchange(code, flow.code_verifier, flow.nonce.removeprefix("google:"))
    except httpx.HTTPError:
        raise HTTPException(503, "Google is unavailable. Restart sign-in") from None
    except (ValueError, KeyError, TypeError, jwt.PyJWTError):
        raise HTTPException(400, "Invalid Google response. Restart sign-in") from None
    return auth.finish_oauth(request, db, flow, "https://accounts.google.com", claims)
