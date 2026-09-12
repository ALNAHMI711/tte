import pytest

from trading.binance_preflight import PreflightStatus, run_binance_preflight
from trading.config import Settings
from trading.execution import ExecutionEngine, OrderRequest
from trading.risk import RiskContext, RiskRejected


def passing_preflight():
    return run_binance_preflight(
        live_requested=True,
        api_key_configured=True,
        trading_permission=True,
        withdrawal_permission=False,
        trusted_ips_only=True,
        server_ip_configured=True,
        risk_configured=True,
        dry_run_passed=True,
    )


def enable_live_mode(monkeypatch):
    monkeypatch.setattr(
        "trading.execution.settings",
        Settings(live_trading=True, paper_trading=False, session_secret="test-secret"),
    )


def test_live_execution_requires_completed_preflight(monkeypatch):
    enable_live_mode(monkeypatch)

    engine = ExecutionEngine()

    with pytest.raises(RuntimeError, match="completed Binance preflight"):
        engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())


def test_live_execution_rejects_failed_preflight(monkeypatch):
    enable_live_mode(monkeypatch)

    failed = run_binance_preflight(
        live_requested=True,
        api_key_configured=True,
        trading_permission=True,
        withdrawal_permission=True,
        trusted_ips_only=True,
        server_ip_configured=True,
        risk_configured=True,
        dry_run_passed=True,
    )
    assert failed.checks[3].status is PreflightStatus.FAIL

    engine = ExecutionEngine(live_preflight=failed)

    with pytest.raises(RiskRejected, match="failed Binance preflight"):
        engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())


def test_live_execution_reaches_exchange_adapter_boundary_only_after_passing_preflight(monkeypatch):
    enable_live_mode(monkeypatch)

    engine = ExecutionEngine(live_preflight=passing_preflight())

    with pytest.raises(RuntimeError, match="live execution is not implemented"):
        engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())
