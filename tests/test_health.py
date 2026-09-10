from trading.health import CheckResult, HealthChecker


def test_liveness_is_independent_of_dependencies():
    checker = HealthChecker()
    assert checker.liveness().to_dict() == {"status": "ok", "checks": []}


def test_readiness_reports_dependency_state_without_exception_details():
    checker = HealthChecker()
    checker.register("database", lambda: True)
    checker.register("exchange", lambda: False)
    checker.register("secret-provider", lambda: (_ for _ in ()).throw(RuntimeError("TOP-SECRET")))
    checker.register("custom", lambda: CheckResult("custom", True, "connected"))

    report = checker.readiness()
    assert report.status == "not_ready"
    assert report.to_dict()["checks"] == [
        {"name": "database", "ok": True, "detail": ""},
        {"name": "exchange", "ok": False, "detail": "check returned false"},
        {"name": "secret-provider", "ok": False, "detail": "check failed"},
        {"name": "custom", "ok": True, "detail": "connected"},
    ]
    assert "TOP-SECRET" not in str(report.to_dict())


def test_invalid_registration_is_rejected():
    checker = HealthChecker()
    try:
        checker.register("", lambda: True)
    except ValueError:
        pass
    else:
        raise AssertionError("empty check names must be rejected")
