"""Versioned scrypt password hashing; no plaintext password persistence."""

import hashlib
import hmac
import secrets
from threading import BoundedSemaphore

from fastapi import HTTPException

_slots = BoundedSemaphore(2)
COMMON = {"passwordpassword", "password1234567", "123456789012345", "qwertyuiopasdfgh"}


def validate_password(password: str) -> str:
    if not 15 <= len(password) <= 128 or password.casefold() in COMMON or len(set(password)) < 5:
        raise ValueError("Use 15–128 characters and avoid common or repetitive passwords")
    return password


def _derive(password: str, salt: bytes) -> bytes:
    if not _slots.acquire(timeout=2):
        raise HTTPException(429, "Please try again shortly", headers={"Retry-After": "5"})
    try:
        return hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=3, maxmem=64 * 1024 * 1024)
    finally:
        _slots.release()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt-v1${salt.hex()}${_derive(password, salt).hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if encoded is None:
        _derive(password, b"devhub-dummy-salt")
        return False
    try:
        version, salt, digest = encoded.split("$")
        if version != "scrypt-v1" or len(salt) != 32 or len(digest) != 128:
            return False
        return hmac.compare_digest(_derive(password, bytes.fromhex(salt)), bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False
