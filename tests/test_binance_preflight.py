from trading.binance_preflight import PreflightStatus, run_binance_preflight


def test_preflight_passes_only_when_every_gate_is_satisfied():
    report = run_binance_preflight(
        live_requested=True,
        api_key_configured=True,
        trading_permission=True,
        withdrawal_permission=False,
        trusted_ips_only=True,
        server_ip_configured=True,
        risk_configured=True,
        dry_run_passed=True,
    )
    assert report.passed is True
    assert all(check.status is PreflightStatus.PASS for check in report.checks)


def test_preflight_fails_closed_when_withdrawal_is_enabled():
    report = run_binance_preflight(
        live_requested=True,
        api_key_configured=True,
        trading_permission=True,
        withdrawal_permission=True,
        trusted_ips_only=True,
        server_ip_configured=True,
        risk_configured=True,
        dry_run_passed=True,
    )
    assert report.passed is False
    assert report.to_dict()["checks"][3]["status"] == "fail"


def test_preflight_requires_trusted_ips_and_dry_run():
    report = run_binance_preflight(
        live_requested=True,
        api_key_configured=True,
        trading_permission=True,
        withdrawal_permission=False,
        trusted_ips_only=False,
        server_ip_configured=True,
        risk_configured=True,
        dry_run_passed=False,
    )
    assert report.passed is False
    assert report.to_dict()["checks"][4]["status"] == "fail"
    assert report.to_dict()["checks"][7]["status"] == "fail"
