"""Security-first authentication primitives."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


class StepUpGrant:
    """Short-lived privilege elevation bound to one authenticated session."""

    def __init__(self, session_id: str, ttl_seconds: int = 300) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._session_digest = hashlib.sha256(session_id.encode()).digest()
        self.expires_at = time.time() + ttl_seconds
        self.nonce = secrets.token_urlsafe(24)

    def valid_for(self, session_id: str, now: float | None = None) -> bool:
        if not session_id:
            return False
        current = time.time() if now is None else now
        candidate = hashlib.sha256(session_id.encode()).digest()
        return current < self.expires_at and hmac.compare_digest(candidate, self._session_digest)
