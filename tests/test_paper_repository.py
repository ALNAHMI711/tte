import sqlite3

import pytest

from trading.paper_repository import SQLitePaperLedgerRepository
from trading.paper_types import PaperOrderRecord


def _order(order_id: str, client_id: str | None = None) -> PaperOrderRecord:
    return PaperOrderRecord(
        id=order_id,
        symbol="BTCUSDT",
        side="buy",
        quantity=1.0,
        price=100.0,
        client_order_id=client_id,
        status="FILLED",
    )


def test_sqlite_repository_round_trips_orders(tmp_path):
    repository = SQLitePaperLedgerRepository.open(str(tmp_path / "paper.sqlite"))
    repository.insert_order(_order("one", "client-one"))
    with repository.transaction():
        pass

    assert repository.load_orders() == (_order("one", "client-one"),)
    repository.close()


def test_sqlite_repository_transaction_rolls_back_insert(tmp_path):
    repository = SQLitePaperLedgerRepository.open(str(tmp_path / "paper.sqlite"))
    repository.insert_order(_order("one"))
    repository.connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        with repository.transaction():
            repository.insert_order(_order("two", "duplicate"))
            repository.insert_order(_order("three", "duplicate"))

    assert repository.load_orders() == (_order("one"),)
    repository.close()


def test_sqlite_repository_enforces_client_order_id_uniqueness(tmp_path):
    repository = SQLitePaperLedgerRepository.open(str(tmp_path / "paper.sqlite"))

    with repository.transaction():
        repository.insert_order(_order("one", "same"))

    with pytest.raises(sqlite3.IntegrityError):
        with repository.transaction():
            repository.insert_order(_order("two", "same"))

    assert repository.load_orders() == (_order("one", "same"),)
    repository.close()


def test_paper_broker_accepts_repository_injection(tmp_path):
    from trading.paper import PaperBroker

    repository = SQLitePaperLedgerRepository.open(str(tmp_path / "paper.sqlite"))
    broker = PaperBroker(repository=repository)
    order = broker.submit("BTCUSDT", "buy", 1, 100, client_order_id="injected")
    assert broker.order_by_client_id("injected") is order
    assert broker.position("BTCUSDT").quantity == 1
    broker.close()


def test_paper_broker_rejects_path_and_repository_together(tmp_path):
    repository = SQLitePaperLedgerRepository.open(str(tmp_path / "repository.sqlite"))

    with pytest.raises(ValueError, match="either persistence_path or repository"):
        from trading.paper import PaperBroker
        PaperBroker(str(tmp_path / "paper.sqlite"), repository=repository)

    repository.close()


def test_postgres_repository_fails_clearly_without_driver(monkeypatch):
    from trading.paper_repository import PostgresPaperLedgerRepository

    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name == "psycopg":
            raise ImportError("driver unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked_import)
    with pytest.raises(RuntimeError, match="requires the postgres dependency"):
        PostgresPaperLedgerRepository.open("postgresql://invalid")
