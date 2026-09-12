from __future__ import annotations

import json

import pytest

import trading.server_ip as server_ip
from trading.server_ip import PublicIPClient, PublicIPError


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_resolve_returns_normalized_public_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, float]] = []

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        calls.append((request.full_url, timeout))  # type: ignore[attr-defined]
        return FakeResponse(json.dumps({"ip": " 203.0.113.10 "}).encode())

    monkeypatch.setattr(server_ip, "urlopen", fake_urlopen)

    result = PublicIPClient(url="https://example.test/ip", timeout_seconds=7.0).resolve()

    assert result.ip == "203.0.113.10"
    assert result.source == "https://example.test/ip"
    assert calls == [("https://example.test/ip", 7.0)]


def test_rejects_non_https_endpoint() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        PublicIPClient(url="http://example.test/ip")


def test_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="positive"):
        PublicIPClient(timeout_seconds=0)


def test_normalizes_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args: object, **kwargs: object) -> None:
        raise OSError("network failure")

    monkeypatch.setattr(server_ip, "urlopen", fake_urlopen)

    with pytest.raises(PublicIPError, match="lookup failed"):
        PublicIPClient().resolve()


@pytest.mark.parametrize(
    "payload",
    [b"not-json", b"{}", b'{"ip": null}', b'{"ip": "   "}'],
)
def test_rejects_malformed_or_invalid_ip_response(
    monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> None:
    monkeypatch.setattr(server_ip, "urlopen", lambda *args, **kwargs: FakeResponse(payload))

    with pytest.raises(PublicIPError):
        PublicIPClient().resolve()
