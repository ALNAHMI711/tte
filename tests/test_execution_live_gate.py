import pytest

from trading.binance_preflight import PreflightStatus, run_binance_preflight
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


def test_live_execution_requires_completed_preflight(monkeypatch):
    monkeypatch.setattr("trading.execution.settings.live_trading", True)
    monkeypatch.setattr("trading.execution.settings.paper_trading", False)

    engine = ExecutionEngine()

    with pytest.raises(RuntimeError, match="completed Binance preflight"):
        engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())


def test_live_execution_rejects_failed_preflight(monkeypatch):
    monkeypatch.setattr("trading.execution.settings.live_trading", True)
    monkeypatch.setattr("trading.execution.settings.paper_trading", False)

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
    monkeypatch.setattr("trading.execution.settings.live_trading", True)
    monkeypatch.setattr("trading.execution.settings.paper_trading", False)

    engine = ExecutionEngine(live_preflight=passing_preflight())

    with pytest.raises(RuntimeError, match="live execution is not implemented"):
        engine.submit(OrderRequest("BTC/USDT", "buy", 0.01, 1000), RiskContext())
