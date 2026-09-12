"""Read-only public outbound IP discovery for Binance trusted-IP setup."""
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_PUBLIC_IP_URL = "https://api.ipify.org?format=json"


class PublicIPError(RuntimeError):
    """Raised when the public outbound IP cannot be determined safely."""


@dataclass(frozen=True)
class PublicIPResult:
    ip: str
    source: str


@dataclass(frozen=True)
class PublicIPClient:
    """Small read-only resolver; it never sends credentials or trading data."""

    url: str = DEFAULT_PUBLIC_IP_URL
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.url.startswith("https://"):
            raise ValueError("public IP endpoint must use HTTPS")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def resolve(self) -> PublicIPResult:
        request = Request(
            self.url,
            headers={"Accept": "application/json", "User-Agent": "tte-ip-check/0.1"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise PublicIPError("public outbound IP lookup failed") from exc

        try:
            data = json.loads(raw.decode("utf-8"))
            ip = data["ip"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise PublicIPError("public outbound IP response is malformed") from exc

        if not isinstance(ip, str) or not ip.strip():
            raise PublicIPError("public outbound IP response is invalid")
        return PublicIPResult(ip=ip.strip(), source=self.url)
