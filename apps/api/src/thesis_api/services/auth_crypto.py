"""Password and setup-token helpers (Argon2id)."""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def new_setup_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hex). Raw is shown once in logs / setup UI."""
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, digest


def hash_setup_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
