from trading.binance_connectivity import BinanceConnectivityResult
from trading.binance_preflight import PreflightStatus
from trading.live_gate import LiveGateInputs, evaluate_live_gate


def ready_inputs(connectivity: BinanceConnectivityResult | None = None) -> LiveGateInputs:
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


def test_live_gate_passes_with_all_preflight_checks_and_testnet_connectivity():
    connectivity = BinanceConnectivityResult(
        reachable=True,
        environment="testnet",
        checks=("environment=testnet", "public_api=reachable", "orders=not_supported"),
    )

    report = evaluate_live_gate(ready_inputs(connectivity))

    assert report.passed is True
    assert report.checks[-1].name == "testnet_connectivity"
    assert report.checks[-1].status is PreflightStatus.PASS


def test_live_gate_fails_closed_without_connectivity():
    report = evaluate_live_gate(ready_inputs())

    assert report.passed is False
    assert report.checks[-1].name == "testnet_connectivity"
    assert report.checks[-1].status is PreflightStatus.FAIL


def test_live_gate_rejects_non_testnet_connectivity():
    connectivity = BinanceConnectivityResult(
        reachable=True,
        environment="mainnet",
        checks=("environment=mainnet", "public_api=reachable"),
    )

    report = evaluate_live_gate(ready_inputs(connectivity))

    assert report.passed is False
    assert report.checks[-1].status is PreflightStatus.FAIL


def test_live_gate_rejects_connectivity_without_explicit_order_block():
    connectivity = BinanceConnectivityResult(
        reachable=True,
        environment="testnet",
        checks=("environment=testnet", "public_api=reachable"),
    )

    report = evaluate_live_gate(ready_inputs(connectivity))

    assert report.passed is False
    assert report.checks[-1].status is PreflightStatus.FAIL


def test_live_gate_rejects_unreachable_testnet():
    connectivity = BinanceConnectivityResult(
        reachable=False,
        environment="testnet",
        checks=("environment=testnet", "orders=not_supported"),
    )

    report = evaluate_live_gate(ready_inputs(connectivity))

    assert report.passed is False
    assert report.checks[-1].status is PreflightStatus.FAIL
