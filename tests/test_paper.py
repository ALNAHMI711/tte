import pytest

from trading.paper import PaperBroker


def test_paper_buy_creates_position_and_averages():
    broker = PaperBroker()
    broker.submit("btcusdt", "buy", 1, 100)
    broker.submit("BTCUSDT", "buy", 3, 200)
    position = broker.position("BTCUSDT")
    assert position is not None
    assert position.quantity == 4
    assert position.average_price == 175


def test_paper_sell_reduces_position_without_changing_average_entry():
    broker = PaperBroker()
    broker.submit("BTCUSDT", "buy", 2, 100)
    broker.submit("BTCUSDT", "sell", 0.5, 120)
    position = broker.position("BTCUSDT")
    assert position is not None
    assert position.quantity == 1.5
    assert position.average_price == 100


def test_paper_sell_cannot_exceed_position():
    broker = PaperBroker()
    broker.submit("BTCUSDT", "buy", 1, 100)
    with pytest.raises(ValueError, match="exceeds current position"):
        broker.submit("BTCUSDT", "sell", 1.1, 100)


def test_paper_client_order_id_is_idempotent():
    broker = PaperBroker()
    first = broker.submit("BTCUSDT", "buy", 1, 100, client_order_id="strategy-1")
    second = broker.submit("BTCUSDT", "buy", 1, 100, client_order_id="strategy-1")
    assert second is first
    assert len(broker.orders) == 1
    assert broker.position("BTCUSDT").quantity == 1


def test_paper_rejects_conflicting_client_order_id_reuse():
    broker = PaperBroker()
    broker.submit("BTCUSDT", "buy", 1, 100, client_order_id="strategy-2")
    with pytest.raises(ValueError, match="different order"):
        broker.submit("BTCUSDT", "buy", 2, 100, client_order_id="strategy-2")


def test_paper_ignores_blank_client_order_id():
    broker = PaperBroker()
    first = broker.submit("BTCUSDT", "buy", 1, 100, client_order_id="   ")
    second = broker.submit("BTCUSDT", "buy", 1, 100, client_order_id="   ")
    assert first is not second
    assert len(broker.orders) == 2


def test_paper_rejects_invalid_side_and_prices():
    broker = PaperBroker()
    with pytest.raises(ValueError, match="side"):
        broker.submit("BTCUSDT", "hold", 1, 100)
    with pytest.raises(ValueError, match="positive"):
        broker.submit("BTCUSDT", "buy", 0, 100)
