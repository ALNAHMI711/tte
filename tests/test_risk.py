from trading.risk import RiskContext, RiskLimits, RiskRejected, validate_order


def test_risk_accepts_small_order() -> None:
    validate_order(10, RiskLimits(), RiskContext())


def test_risk_rejects_emergency_stop() -> None:
    try:
        validate_order(10, RiskLimits(), RiskContext(emergency_stop=True))
    except RiskRejected:
        return
    raise AssertionError("expected RiskRejected")


def test_risk_rejects_excessive_notional() -> None:
    try:
        validate_order(101, RiskLimits(), RiskContext())
    except RiskRejected:
        return
    raise AssertionError("expected RiskRejected")
