"""Authentication primitives and control-plane authentication service."""
from __future__ import annotations

from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .audit import AuditEvent
from .session import LoginThrottle, Session, SessionStore

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


@dataclass(frozen=True)
class UserCredential:
    """Stored credential record; only the password hash is retained."""
    user_id: str
    password_hash: str
    active: bool = True


@dataclass(frozen=True)
class AuthenticationResult:
    authenticated: bool
    session: Session | None = None
    audit_event: AuditEvent | None = None


class AuthenticationService:
    """Authenticate users without exposing credentials to HTTP handlers."""

    def __init__(self, credentials: dict[str, UserCredential], sessions: SessionStore | None = None) -> None:
        self._credentials = dict(credentials)
        self.sessions = sessions or SessionStore()
        self._throttles: dict[str, LoginThrottle] = {}

    def authenticate(self, user_id: str, password: str, *, request_id: str = "", now: float | None = None) -> AuthenticationResult:
        throttle = self._throttles.setdefault(user_id, LoginThrottle())
        if not throttle.allowed(now):
            return AuthenticationResult(False, audit_event=AuditEvent.create(
                "login", user_id or "unknown", "blocked", request_id=request_id,
                details={"reason": "login_throttled"}))
        credential = self._credentials.get(user_id)
        valid = bool(credential and credential.active and verify_password(password, credential.password_hash))
        if not valid:
            throttle.failure(now)
            return AuthenticationResult(False, audit_event=AuditEvent.create(
                "login", user_id or "unknown", "failed", request_id=request_id,
                details={"reason": "invalid_credentials"}))
        throttle.success()
        session = self.sessions.create(user_id, now)
        return AuthenticationResult(True, session=session, audit_event=AuditEvent.create(
            "login", user_id, "success", request_id=request_id))

    def step_up(self, token: str, password: str, *, request_id: str = "", now: float | None = None) -> AuthenticationResult:
        session = self.sessions.get(token, now)
        if session is None:
            return AuthenticationResult(False, audit_event=AuditEvent.create(
                "step_up", "unknown", "failed", request_id=request_id,
                details={"reason": "invalid_session"}))
        credential = self._credentials.get(session.user_id)
        if credential is None or not credential.active or not verify_password(password, credential.password_hash):
            return AuthenticationResult(False, audit_event=AuditEvent.create(
                "step_up", session.user_id, "failed", request_id=request_id,
                details={"reason": "invalid_credentials"}))
        elevated = self.sessions.elevate(token, now)
        return AuthenticationResult(True, session=elevated, audit_event=AuditEvent.create(
            "step_up", session.user_id, "success", request_id=request_id))

    def logout(self, token: str) -> bool:
        """Revoke the credential even when its session has already expired."""
        return self.sessions.revoke(token)


def credential_from_password(user_id: str, password: str) -> UserCredential:
    """Create a credential record; callers should persist only this record."""
    return UserCredential(user_id=user_id, password_hash=hash_password(password))
