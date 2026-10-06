import pytest

from trading.config import Settings


def test_safe_defaults_are_paper_only():
    settings = Settings(live_trading=False, paper_trading=True, session_secret="")
    settings.validate()


def test_live_requires_session_secret():
    settings = Settings(live_trading=True, paper_trading=False, session_secret="")
    with pytest.raises(ValueError, match="SESSION_SECRET"):
        settings.validate()


def test_live_and_paper_cannot_both_be_enabled():
    settings = Settings(live_trading=True, paper_trading=True, session_secret="x")
    with pytest.raises(ValueError, match="cannot both be enabled"):
        settings.validate()


def test_postgresql_paper_backend_requires_dsn():
    settings = Settings(paper_store_backend="postgresql", paper_store_path="", paper_store_dsn="")
    with pytest.raises(ValueError, match="PAPER_STORE_DSN"):
        settings.validate()


def test_sqlite_paper_backend_rejects_postgresql_dsn():
    settings = Settings(paper_store_backend="sqlite", paper_store_path="", paper_store_dsn="postgresql://db")
    with pytest.raises(ValueError, match="only valid"):
        settings.validate()


def test_unknown_paper_backend_is_rejected():
    settings = Settings(paper_store_backend="mysql")
    with pytest.raises(ValueError, match="PAPER_STORE_BACKEND"):
        settings.validate()
