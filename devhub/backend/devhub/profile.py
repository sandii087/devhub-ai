"""Self-service profiles and bounded, sanitized avatars persisted in PostgreSQL."""

from io import BytesIO
import hashlib
from threading import BoundedSemaphore

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from devhub import auth
from devhub.auth_models import PasswordCredential, Identity
from devhub.db import get_db
from devhub.models import User

router = APIRouter(prefix="/api/v1/me", tags=["profile"])
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
_slots = BoundedSemaphore(2)


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=100)


def view(user, db):
    credential = db.get(PasswordCredential, user.id)
    issuers = db.scalars(select(Identity.issuer).where(Identity.user_id == user.id)).all()
    return {
        **auth._session_view(user).user.model_dump(),
        # Identity rows do not store their verified email: do not guess for OAuth-only users.
        "email_verified": bool(
            credential and credential.verified and credential.email.casefold() == user.email.casefold()
        ),
        "password_enabled": bool(credential and credential.verified),
        "connected_providers": [
            name
            for issuer, name in [("https://github.com", "GitHub"), ("https://accounts.google.com", "Google")]
            if issuer in issuers
        ],
    }


@router.get("")
def get_profile(user: User = Depends(auth.require_user), db: Session = Depends(get_db)):
    return view(user, db)


@router.patch("")
def update_profile(
    payload: ProfileInput, user: User = Depends(auth.require_user), db: Session = Depends(get_db)
):
    user.display_name = payload.display_name
    db.flush()
    return view(user, db)


def sanitize_image(data, mime):
    if mime not in FORMATS:
        raise HTTPException(415, "Choose a JPEG, PNG or WebP image")
    if not data or len(data) > 1_048_576:
        raise HTTPException(413, "Choose an image no larger than 1 MiB")
    if not _slots.acquire(timeout=1):
        raise HTTPException(429, "Image processing is busy. Try again shortly")
    try:
        with Image.open(BytesIO(data), formats=list(FORMATS.values())) as image:
            if image.format != FORMATS[mime] or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Image format mismatch or animation")
            if image.width * image.height > 8_000_000:
                raise ValueError("Image dimensions too large")
            image.load()
            oriented = ImageOps.exif_transpose(image)
            oriented.thumbnail((256, 256))
            # Copy pixels into a new image so EXIF/GPS, profiles and appended payloads are discarded.
            clean = Image.new("RGB", oriented.size, "white")
            if "A" in oriented.getbands():
                clean.paste(oriented, mask=oriented.getchannel("A"))
            else:
                clean.paste(oriented.convert("RGB"))
            output = BytesIO()
            clean.save(output, "JPEG", quality=85)
            encoded = output.getvalue()
            if len(encoded) > 100_000:
                raise ValueError("Encoded image too large")
            return encoded
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, "Invalid image. Use a still JPEG, PNG or WebP up to 8 megapixels") from None
    finally:
        _slots.release()


@router.put("/avatar")
def upload_avatar(
    request: Request,
    data: bytes = Body(media_type="application/octet-stream"),
    user: User = Depends(auth.require_user),
    db: Session = Depends(get_db),
):
    encoded = sanitize_image(data, request.headers.get("content-type", "").split(";")[0].lower())
    user.avatar_data = encoded
    user.avatar_version = hashlib.sha256(encoded).hexdigest()
    db.flush()
    return view(user, db)


@router.delete("/avatar")
def remove_avatar(user: User = Depends(auth.require_user), db: Session = Depends(get_db)):
    user.avatar_data = None
    user.avatar_version = None
    db.flush()
    return view(user, db)


@router.get("/avatar")
def avatar(user: User = Depends(auth.require_user)):
    if not user.avatar_data:
        raise HTTPException(404, "No profile picture")
    return Response(
        user.avatar_data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
