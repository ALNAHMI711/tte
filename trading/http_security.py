"""Framework-neutral HTTP security helpers for the trading control plane."""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from secrets import token_urlsafe


@dataclass(frozen=True)
class CookiePolicy:
    """Safe defaults for an authenticated browser session."""

    name: str = "tte_session"
    secure: bool = True
    httponly: bool = True
    samesite: str = "lax"
    path: str = "/"


@dataclass(frozen=True)
class CsrfToken:
    value: str

    @classmethod
    def generate(cls) -> "CsrfToken":
        return cls(token_urlsafe(32))


def constant_time_token_match(expected: str, supplied: str) -> bool:
    """Compare CSRF/session-bound values without timing leaks."""
    import hmac

    if not isinstance(expected, str) or not isinstance(supplied, str):
        return False
    return hmac.compare_digest(expected, supplied)


def client_ip_allowed(client_ip: str, trusted_networks: tuple[str, ...]) -> bool:
    """Allow only explicitly trusted proxy/client networks when configured."""
    try:
        address = ip_address(client_ip)
    except ValueError:
        return False
    if not trusted_networks:
        return False
    for network in trusted_networks:
        try:
            if address in ip_network(network, strict=False):
                return True
        except ValueError:
            continue
    return False
