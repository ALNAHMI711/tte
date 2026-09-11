import pytest

from trading.binance_testnet import BinanceTestnetConfig, TestnetPreflightError, run_preflight


def config(**overrides):
    values = dict(api_key="test-key", api_secret="test-secret", trusted_ip="203.0.113.10")
    values.update(overrides)
    return BinanceTestnetConfig(**values)


def test_preflight_accepts_safe_testnet_configuration():
    checks = run_preflight(config())
    assert "environment=testnet" in checks
    assert "withdrawals=disabled" in checks
    assert "live_execution=blocked" in checks


def test_live_environment_is_rejected():
    with pytest.raises(TestnetPreflightError, match="Testnet"):
        run_preflight(config(testnet=False))


def test_withdrawal_permission_is_rejected():
    with pytest.raises(TestnetPreflightError, match="withdrawal"):
        run_preflight(config(withdrawal_enabled=True))


def test_missing_credentials_are_rejected():
    with pytest.raises(TestnetPreflightError, match="credentials"):
        run_preflight(config(api_secret=""))


def test_invalid_trusted_ip_is_rejected():
    with pytest.raises(TestnetPreflightError, match="IP"):
        run_preflight(config(trusted_ip="not-an-ip"))
