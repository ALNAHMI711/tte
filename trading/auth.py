"""Authentication primitives: Argon2id password hashing and constant-time checks."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2id password hash; plaintext is never persisted."""
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without exposing hash internals to callers."""
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Indicate whether a stored hash should be upgraded to current parameters."""
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except (VerificationError, InvalidHashError):
        return False
