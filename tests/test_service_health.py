from trading.health import HealthChecker
from trading.service_health import build_health_checker


class StubPaper:
    def healthcheck(self) -> None:
        return None


class StubEngine:
    def __init__(self) -> None:
        self.paper = StubPaper()


def test_service_health_registers_paper_store():
    report = build_health_checker(StubEngine()).readiness()
    assert report.status == "ok"
    assert report.to_dict()["checks"] == [
        {"name": "paper-store", "ok": True, "detail": "ok"}
    ]


def test_service_health_propagates_paper_store_failure_safely():
    class BrokenPaper:
        def healthcheck(self) -> None:
            raise RuntimeError("password=secret")

    class BrokenEngine:
        paper = BrokenPaper()

    checker = build_health_checker(BrokenEngine())
    report = checker.readiness()
    assert report.status == "not_ready"
    assert report.to_dict()["checks"] == [
        {"name": "paper-store", "ok": False, "detail": "check failed"}
    ]
    assert "password=secret" not in str(report.to_dict())


def test_health_checker_can_be_used_directly():
    checker = HealthChecker()
    checker.register("ok", lambda: True)
    assert checker.readiness().status == "ok"
