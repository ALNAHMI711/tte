"""Secret storage primitives with authenticated encryption and safe masking."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


class SecretStoreError(ValueError):
    """Raised when secret-store configuration or ciphertext is invalid."""


def derive_fernet_key(master_key: str) -> bytes:
    """Derive a stable Fernet key from a configured master secret."""
    if not isinstance(master_key, str) or len(master_key) < 32:
        raise SecretStoreError("master key must contain at least 32 characters")
    digest = hashlib.sha256(master_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def mask_secret(value: str, visible: int = 4) -> str:
    """Return a non-sensitive representation suitable for UI/audit output."""
    if not isinstance(value, str) or not value:
        return ""
    if visible < 0:
        raise ValueError("visible must not be negative")
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}{'*' * max(8, len(value) - visible * 2)}{value[-visible:]}"


def secret_fingerprint(value: str) -> str:
    """Return a one-way identifier; never use this as a credential."""
    if not isinstance(value, str):
        raise ValueError("secret must be a string")
    return hmac.new(b"tte-secret-fingerprint-v1", value.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


@dataclass
class EncryptedSecretStore:
    """Small persistence-agnostic encrypted secret store.

    Values are encrypted before being kept in memory. Production persistence can
    store the ciphertexts, while the master key must come from a secret manager
    or protected environment and must never be committed.
    """

    master_key: str

    def __post_init__(self) -> None:
        try:
            self._fernet = Fernet(derive_fernet_key(self.master_key))
        except Exception as exc:
            if isinstance(exc, SecretStoreError):
                raise
            raise SecretStoreError("invalid secret-store master key") from exc
        self._values: dict[str, bytes] = {}

    def put(self, name: str, value: str) -> None:
        if not name or not isinstance(name, str):
            raise SecretStoreError("secret name is required")
        if not isinstance(value, str) or not value:
            raise SecretStoreError("secret value is required")
        self._values[name] = self._fernet.encrypt(value.encode("utf-8"))

    def get(self, name: str) -> str | None:
        token = self._values.get(name)
        if token is None:
            return None
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise SecretStoreError("secret ciphertext could not be decrypted") from exc

    def delete(self, name: str) -> bool:
        return self._values.pop(name, None) is not None

    def masked(self, name: str, visible: int = 4) -> str | None:
        value = self.get(name)
        return None if value is None else mask_secret(value, visible)

    def ciphertext(self, name: str) -> bytes | None:
        """Expose ciphertext for a persistence adapter, never plaintext."""
        return self._values.get(name)

    def load_ciphertext(self, name: str, token: bytes) -> None:
        if not name or not isinstance(token, bytes) or not token:
            raise SecretStoreError("invalid encrypted secret")
        self._values[name] = token


def master_key_from_env(name: str = "SECRET_MASTER_KEY") -> str:
    value = os.getenv(name, "")
    if len(value) < 32:
        raise SecretStoreError(f"{name} must be configured with at least 32 characters")
    return value
