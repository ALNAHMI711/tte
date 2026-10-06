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


def test_risk_limits_reject_invalid_configuration() -> None:
    import pytest
    with pytest.raises(ValueError, match="max_order_notional"):
        RiskLimits(max_order_notional=0)
    with pytest.raises(ValueError, match="risk_per_trade_pct"):
        RiskLimits(risk_per_trade_pct=0)


def test_risk_rejects_wrong_long_stop_direction() -> None:
    import pytest
    with pytest.raises(RiskRejected, match="long stop"):
        validate_order(
            10, RiskLimits(), RiskContext(),
            account_equity=1000, entry_price=100, stop_loss_price=110,
            quantity=0.1, side="buy",
        )


def test_risk_accepts_correct_long_stop_direction() -> None:
    validate_order(
        10, RiskLimits(), RiskContext(),
        account_equity=1000, entry_price=100, stop_loss_price=95,
        quantity=0.1, side="buy",
    )
