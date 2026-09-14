from trading.binance_connectivity import BinanceConnectivityResult
from trading.binance_readiness import compose_binance_readiness
from trading.live_gate import LiveGateInputs
from trading.server_ip import PublicIPResult


def inputs(connectivity=None):
    return LiveGateInputs(
        live_requested=True,
        api_key_configured=True,
        trading_permission=True,
        withdrawal_permission=False,
        trusted_ips_only=True,
        server_ip_configured=True,
        risk_configured=True,
        dry_run_passed=True,
        connectivity=connectivity,
    )


def test_unified_readiness_requires_all_signals():
    connectivity = BinanceConnectivityResult(
        reachable=True,
        environment="testnet",
        checks=("environment=testnet", "public_api=reachable", "orders=not_supported"),
    )
    server_ip = PublicIPResult(ip="203.0.113.10", source="https://example.test/ip")

    status = compose_binance_readiness(inputs=inputs(connectivity), server_ip=server_ip)

    assert status.ready is True
    payload = status.to_dict()
    assert payload["ready"] is True
    assert payload["live_enabled"] is False
    assert payload["server_ip"] == {"ip": "203.0.113.10", "source": "https://example.test/ip"}


def test_unified_readiness_fails_without_server_ip():
    connectivity = BinanceConnectivityResult(
        reachable=True,
        environment="testnet",
        checks=("environment=testnet", "public_api=reachable", "orders=not_supported"),
    )

    status = compose_binance_readiness(inputs=inputs(connectivity))

    assert status.ready is False
    assert status.to_dict()["server_ip"] is None


def test_unified_readiness_fails_without_testnet_connectivity():
    server_ip = PublicIPResult(ip="203.0.113.10", source="https://example.test/ip")

    status = compose_binance_readiness(inputs=inputs(), server_ip=server_ip)

    assert status.ready is False
    assert status.to_dict()["connectivity"] is None


def test_unified_readiness_fails_closed_for_mainnet_connectivity():
    connectivity = BinanceConnectivityResult(
        reachable=True,
        environment="mainnet",
        checks=("environment=mainnet", "public_api=reachable", "orders=not_supported"),
    )
    server_ip = PublicIPResult(ip="203.0.113.10", source="https://example.test/ip")

    status = compose_binance_readiness(inputs=inputs(connectivity), server_ip=server_ip)

    assert status.ready is False
