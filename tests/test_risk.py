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


def test_risk_rejects_non_finite_limits_and_context():
    import math
    import pytest

    with pytest.raises(ValueError, match="finite"):
        RiskLimits(max_order_notional=math.inf)
    with pytest.raises(ValueError, match="finite"):
        RiskLimits(risk_per_trade_pct=math.nan)
    with pytest.raises(ValueError, match="finite"):
        RiskContext(open_exposure=math.inf)
    with pytest.raises(ValueError, match="non-negative"):
        RiskContext(daily_loss=-1)


def test_risk_rejects_non_finite_order_values():
    import math
    import pytest

    with pytest.raises(RiskRejected, match="notional"):
        validate_order(math.inf, RiskLimits(), RiskContext())
    with pytest.raises(RiskRejected, match="equity"):
        validate_order(10, RiskLimits(), RiskContext(), account_equity=math.inf)


def test_risk_checks_stop_direction_without_equity():
    import pytest

    with pytest.raises(RiskRejected, match="long stop"):
        validate_order(
            10, RiskLimits(), RiskContext(),
            entry_price=100, stop_loss_price=110, quantity=0.1, side="buy",
        )


def test_risk_rejects_signal_below_minimum():
    import pytest
    with pytest.raises(RiskRejected, match="signal score"):
        validate_order(10, RiskLimits(), RiskContext(), signal_score=84)


def test_risk_rejects_reward_risk_below_minimum():
    import pytest
    with pytest.raises(RiskRejected, match="reward-risk"):
        validate_order(10, RiskLimits(), RiskContext(), reward_risk_ratio=1.99)


def test_risk_rejects_max_open_positions_for_new_exposure():
    import pytest
    with pytest.raises(RiskRejected, match="open positions"):
        validate_order(
            10, RiskLimits(max_open_positions=5),
            RiskContext(open_positions=5),
            exposure_delta=10,
        )


def test_risk_allows_exposure_reduction_at_position_limit():
    validate_order(
        10, RiskLimits(max_open_positions=5),
        RiskContext(open_positions=5, open_exposure=20),
        side="sell",
        exposure_delta=-10,
    )


def test_risk_rejects_invalid_position_limit():
    import pytest
    with pytest.raises(ValueError, match="max_open_positions"):
        RiskLimits(max_open_positions=0)
