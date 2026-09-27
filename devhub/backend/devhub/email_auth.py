"""Email credentials share DevHub users, sessions and authorization boundaries."""

from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DatabaseSession

from devhub import auth, auth_mail
from devhub.auth_models import AuthThrottle, EmailToken, PasswordCredential, Session
from devhub.config import settings
from devhub.db import get_db
from devhub.models import User
from devhub.passwords import hash_password, validate_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])
GENERIC = {
    "detail": "If this address is eligible, an email will arrive shortly. Check your inbox and spam folder."
}


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=254)


class LoginInput(EmailInput):
    password: str = Field(min_length=1, max_length=128)


class SignupInput(LoginInput):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    first_name: str | None = Field(default=None, min_length=1, max_length=49)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    confirm_password: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def signup_fields(self):
        if self.first_name is not None or self.last_name is not None:
            if not (self.first_name or "").strip() or not (self.last_name or "").strip():
                raise ValueError("First and last name are required")
            self.display_name = f"{self.first_name.strip()} {self.last_name.strip()}"
        if not self.display_name:
            raise ValueError("Name is required")
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @field_validator("password")
    @classmethod
    def strong_password(cls, value):
        return validate_password(value)

    @field_validator("display_name")
    @classmethod
    def name(cls, value):
        if value is None or not value.strip():
            raise ValueError("Name is required")
        return value.strip()


class TokenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=1, max_length=128)
    confirm_password: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def confirmation(self):
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class ChangePasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=15, max_length=128)
    confirm_password: str = Field(min_length=15, max_length=128)

    @model_validator(mode="after")
    def strong_confirmed_password(self):
        validate_password(self.password)
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


def lock_email(db, email):
    # Serialize all account creation paths, including OAuth, without changing existing users.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(auth._hash(email)[:15], 16)})


def throttle(db, action, subject=""):
    now = auth._now()
    db.execute(delete(AuthThrottle).where(AuthThrottle.expires_at <= now))
    counts = []
    for bucket, limit, seconds in (("global", 30, 60), (subject, 5, 900)):
        key = auth._hash(action + ":" + bucket)
        statement = insert(AuthThrottle).values(key=key, count=1, expires_at=now + timedelta(seconds=seconds))
        count = db.scalar(
            statement.on_conflict_do_update(
                index_elements=[AuthThrottle.key], set_={"count": AuthThrottle.count + 1}
            ).returning(AuthThrottle.count)
        )
        counts.append((count, limit))
    # Preserve abuse counters on authentication failures and password resets.
    db.commit()
    if any(count > limit for count, limit in counts):
        raise HTTPException(429, "Too many attempts. Please try again later", headers={"Retry-After": "900"})


def guard(request, db, action, subject, mail=False):
    auth._check_origin(request)
    if not settings.email_auth_enabled:
        raise HTTPException(503, "Email authentication is not configured")
    if mail and not auth_mail.configured():
        raise HTTPException(503, "Email delivery is not configured")
    throttle(db, action, subject)


def issue_token(db, user_id, email, purpose, background):
    db.execute(delete(EmailToken).where(EmailToken.user_id == user_id, EmailToken.purpose == purpose))
    token = auth.secrets.token_urlsafe(32)
    db.add(
        EmailToken(
            token_hash=auth._hash(token),
            user_id=user_id,
            purpose=purpose,
            expires_at=auth._now() + timedelta(minutes=30),
        )
    )
    db.commit()
    background.add_task(auth_mail.send_auth_email, email, token, purpose)


@router.post("/signup", status_code=202)
def signup(
    payload: SignupInput, request: Request, background: BackgroundTasks, db: DatabaseSession = Depends(get_db)
):
    email = str(payload.email).casefold()
    guard(request, db, "signup", email, mail=True)
    encoded = hash_password(payload.password)
    lock_email(db, email)
    if db.scalar(select(User.id).where(func.lower(User.email) == email).limit(1)):
        return GENERIC
    user = User(
        id=str(uuid4()),
        email=email,
        display_name=payload.display_name,
        disabled=False,
        created_at=auth._now(),
    )
    db.add(user)
    db.flush()
    db.add(PasswordCredential(user_id=user.id, email=email, password_hash=encoded, verified=False))
    issue_token(db, user.id, email, "verify", background)
    return GENERIC


@router.post("/email-login", response_model=auth.SessionView)
def login(payload: LoginInput, request: Request, response: Response, db: DatabaseSession = Depends(get_db)):
    email = str(payload.email).casefold()
    guard(request, db, "login", email)
    credential = db.scalar(
        select(PasswordCredential).where(PasswordCredential.email == email).with_for_update()
    )
    valid = verify_password(payload.password, credential.password_hash if credential else None)
    user = db.get(User, credential.user_id) if credential else None
    if not valid or not credential.verified or not user or user.disabled:
        raise HTTPException(401, "Invalid email or password, or email not verified")
    return auth._session_view(user, auth._new_session(request, response, db, user))


@router.post("/forgot-password", status_code=202)
def forgot(
    payload: EmailInput, request: Request, background: BackgroundTasks, db: DatabaseSession = Depends(get_db)
):
    email = str(payload.email).casefold()
    guard(request, db, "email-send", email, mail=True)
    credential = db.scalar(
        select(PasswordCredential)
        .join(User)
        .where(
            PasswordCredential.email == email, PasswordCredential.verified.is_(True), User.disabled.is_(False)
        )
        .with_for_update()
    )
    if credential:
        issue_token(db, credential.user_id, email, "reset", background)
    return GENERIC


@router.post("/resend-verification", status_code=202)
def resend(
    payload: EmailInput, request: Request, background: BackgroundTasks, db: DatabaseSession = Depends(get_db)
):
    email = str(payload.email).casefold()
    guard(request, db, "email-send", email, mail=True)
    credential = db.scalar(
        select(PasswordCredential)
        .join(User)
        .where(
            PasswordCredential.email == email,
            PasswordCredential.verified.is_(False),
            User.disabled.is_(False),
        )
        .with_for_update()
    )
    if credential:
        issue_token(db, credential.user_id, email, "verify", background)
    return GENERIC


def consume(payload, request, db, purpose):
    guard(request, db, "token", auth._hash(payload.token))
    record = db.scalar(
        select(EmailToken).where(
            EmailToken.token_hash == auth._hash(payload.token),
            EmailToken.purpose == purpose,
            EmailToken.expires_at > auth._now(),
        )
    )
    if not record:
        raise HTTPException(400, "This link is invalid, expired, or already used. Request a new email")
    credential = db.get(PasswordCredential, record.user_id, with_for_update=True)
    # All issuance/consumption paths lock credential first, avoiding reset/forgot deadlocks.
    record = db.scalar(
        select(EmailToken)
        .where(
            EmailToken.token_hash == auth._hash(payload.token),
            EmailToken.purpose == purpose,
            EmailToken.expires_at > auth._now(),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not record:
        raise HTTPException(400, "This link is invalid, expired, or already used. Request a new email")
    user = db.get(User, record.user_id)
    if not credential or not user or user.disabled:
        raise HTTPException(400, "This link is unavailable")
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    # Email ownership chooses the final password; an attacker cannot pre-register a known password.
    credential.password_hash = hash_password(payload.password)
    if purpose == "reset":
        if not credential.verified:
            raise HTTPException(400, "This link is unavailable")
        db.execute(update(Session).where(Session.user_id == user.id).values(revoked_at=auth._now()))
    else:
        credential.verified = True
    db.execute(delete(EmailToken).where(EmailToken.user_id == user.id))
    return {
        "detail": "Email verified. You can now sign in"
        if purpose == "verify"
        else "Password updated. Sign in with your new password"
    }


@router.post("/verify-email")
def verify(payload: TokenInput, request: Request, db: DatabaseSession = Depends(get_db)):
    return consume(payload, request, db, "verify")


@router.post("/reset-password")
def reset(payload: TokenInput, request: Request, db: DatabaseSession = Depends(get_db)):
    return consume(payload, request, db, "reset")


@router.post("/change-password")
def change_password(
    payload: ChangePasswordInput,
    request: Request,
    response: Response,
    db: DatabaseSession = Depends(get_db),
    user: User = Depends(auth.require_user),
):
    guard(request, db, "change-password", user.id)
    credential = db.get(PasswordCredential, user.id, with_for_update=True)
    valid = verify_password(payload.current_password, credential.password_hash if credential else None)
    if not valid or not credential or not credential.verified:
        raise HTTPException(400, "Unable to change password. Check your current password")
    # A reset/another change may have revoked this session while waiting for the lock.
    db.refresh(request.state.auth_session)
    if request.state.auth_session.revoked_at is not None:
        raise HTTPException(401, "Authentication required")
    credential.password_hash = hash_password(payload.password)
    db.execute(update(Session).where(Session.user_id == user.id).values(revoked_at=auth._now()))
    db.execute(delete(EmailToken).where(EmailToken.user_id == user.id))
    response.delete_cookie(
        auth._cookie_name(), path="/", secure=auth._secure_cookie(), httponly=True, samesite="lax"
    )
    return {"detail": "Password changed. Sign in again on all devices"}
