import sqlite3

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


def test_paper_sqlite_ledger_restores_orders_positions_and_idempotency(tmp_path):
    path = tmp_path / "paper.sqlite"
    first = PaperBroker(str(path))
    order = first.submit("BTCUSDT", "buy", 1, 100, client_order_id="persist-1")

    restored = PaperBroker(str(path))
    assert restored.order_by_client_id("persist-1").id == order.id
    assert restored.position("BTCUSDT").quantity == 1
    assert restored.submit("BTCUSDT", "buy", 1, 100, client_order_id="persist-1") is restored.order_by_client_id("persist-1")
    assert len(restored.orders) == 1


def test_paper_sqlite_ledger_rejects_corrupt_sell(tmp_path):
    path = tmp_path / "paper.sqlite"
    broker = PaperBroker(str(path))
    broker._connection.execute(
        "INSERT INTO paper_orders (id, symbol, side, quantity, price, client_order_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("bad", "BTCUSDT", "sell", 1, 100, None, "FILLED"),
    )
    broker._connection.commit()

    with pytest.raises(ValueError, match="invalid sell"):
        PaperBroker(str(path))


def test_paper_sqlite_ledger_normalizes_restored_symbol_and_side(tmp_path):
    path = tmp_path / "paper.sqlite"
    broker = PaperBroker(str(path))
    broker._connection.execute(
        "INSERT INTO paper_orders (id, symbol, side, quantity, price, client_order_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("seed", "btcusdt", "buy", 1, 100, None, "FILLED"),
    )
    broker._connection.commit()

    restored = PaperBroker(str(path))
    assert restored.position("BTCUSDT").quantity == 1
    assert restored.orders[0].symbol == "BTCUSDT"
    assert restored.orders[0].side == "buy"


def test_paper_sqlite_ledger_rejects_non_filled_status(tmp_path):
    path = tmp_path / "paper.sqlite"
    broker = PaperBroker(str(path))
    broker._connection.execute(
        "INSERT INTO paper_orders (id, symbol, side, quantity, price, client_order_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("pending", "BTCUSDT", "buy", 1, 100, None, "NEW"),
    )
    broker._connection.commit()

    with pytest.raises(ValueError, match="unsupported order status"):
        PaperBroker(str(path))


def test_paper_sqlite_submit_is_atomic_on_insert_failure(tmp_path):
    path = tmp_path / "paper.sqlite"
    broker = PaperBroker(str(path))
    broker.submit("BTCUSDT", "buy", 1, 100, client_order_id="atomic-1")
    broker._connection.execute(
        "CREATE TRIGGER reject_paper_insert "
        "BEFORE INSERT ON paper_orders "
        "BEGIN SELECT RAISE(ABORT, 'injected insert failure'); END"
    )
    broker._connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="injected insert failure"):
        broker.submit("BTCUSDT", "buy", 2, 200, client_order_id="atomic-2")

    assert len(broker.orders) == 1
    assert broker.order_by_client_id("atomic-2") is None
    assert broker.position("BTCUSDT").quantity == 1

    broker._connection.execute("DROP TRIGGER reject_paper_insert")
    broker._connection.commit()

    restored = PaperBroker(str(path))
    assert len(restored.orders) == 1
    assert restored.order_by_client_id("atomic-2") is None
    assert restored.position("BTCUSDT").quantity == 1


def test_paper_sqlite_second_broker_refreshes_committed_orders(tmp_path):
    path = tmp_path / "paper.sqlite"
    first = PaperBroker(str(path))
    second = PaperBroker(str(path))

    first.submit("BTCUSDT", "buy", 1, 100, client_order_id="shared-1")
    order = second.submit("BTCUSDT", "buy", 2, 200, client_order_id="shared-2")

    assert order.client_order_id == "shared-2"
    assert second.position("BTCUSDT").quantity == 3
    assert first.position("BTCUSDT").quantity == 1

    first.submit("BTCUSDT", "buy", 3, 300, client_order_id="shared-3")
    second.refresh()
    assert second.position("BTCUSDT").quantity == 6
    assert second.order_by_client_id("shared-3") is not None


def test_paper_reconciliation_matches_filled_order_ledger():
    broker = PaperBroker()
    broker.submit("BTCUSDT", "buy", 2, 100)
    broker.submit("BTCUSDT", "buy", 1, 200)
    broker.submit("BTCUSDT", "sell", 0.5, 150)

    result = broker.reconcile()
    assert result.valid
    assert result.order_count == 3
    assert result.position_count == 1
    assert result.errors == ()


def test_paper_reconciliation_detects_position_drift():
    broker = PaperBroker()
    broker.submit("BTCUSDT", "buy", 1, 100)
    broker._positions["BTCUSDT"] = broker._positions["BTCUSDT"].__class__(
        "BTCUSDT", 2, 100
    )

    result = broker.reconcile(refresh=False)
    assert not result.valid
    assert "positions do not match the filled-order ledger" in result.errors
