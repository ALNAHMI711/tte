from trading.paper import PaperBroker
from trading.portfolio_risk import portfolio_exposure, risk_context_from_portfolio


def test_portfolio_exposure_uses_authoritative_positions():
    broker = PaperBroker()
    broker.submit("BTCUSDT", "buy", 0.01, 1000)
    broker.submit("ETHUSDT", "buy", 0.02, 2000)

    exposure = portfolio_exposure(
        broker,
        {"BTCUSDT": 1100, "ETHUSDT": 1900},
    )

    assert exposure.gross_notional == 49
    assert exposure.symbols == ("BTCUSDT", "ETHUSDT")


def test_risk_context_derives_open_exposure_from_portfolio():
    broker = PaperBroker()
    broker.submit("BTCUSDT", "buy", 0.05, 1000)

    ctx = risk_context_from_portfolio(broker, {"BTCUSDT": 1200})

    assert ctx.open_exposure == 60
    assert ctx.daily_loss == 0
    assert ctx.weekly_loss == 0


def test_missing_market_price_is_not_guessed():
    broker = PaperBroker()
    broker.submit("BTCUSDT", "buy", 0.05, 1000)

    exposure = portfolio_exposure(broker, {})

    assert exposure.gross_notional == 0
    assert exposure.symbols == ()
