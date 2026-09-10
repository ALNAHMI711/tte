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
