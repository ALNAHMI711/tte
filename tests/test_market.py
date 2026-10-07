import json

from trading.market import BinanceMarketData


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _opener_for(payload):
    def opener(request, timeout):
        assert request.full_url.startswith("https://testnet.binance.vision/")
        assert timeout == 3
        return _Response(payload)
    return opener


def test_binance_testnet_klines_are_normalized():
    client = BinanceMarketData(timeout=3, opener=_opener_for([
        [1700000000000, "100", "110", "90", "105", "12", "ignored"]
    ]))
    candles = client.klines("btcusdt", "1m", limit=1)
    assert candles[0].symbol == "BTCUSDT"
    assert candles[0].close == 105
    assert candles[0].volume == 12


def test_binance_testnet_order_book_is_normalized():
    client = BinanceMarketData(timeout=3, opener=_opener_for({
        "bids": [["100", "1.5"]],
        "asks": [["101", "2"]],
    }))
    book = client.order_book("BTCUSDT", limit=1)
    assert book.bids == ((100.0, 1.5),)
    assert book.asks == ((101.0, 2.0),)


def test_binance_testnet_rejects_non_testnet_endpoint():
    try:
        BinanceMarketData(base_url="https://api.binance.com")
    except ValueError as exc:
        assert "Spot Testnet" in str(exc)
    else:
        raise AssertionError("non-testnet endpoint was accepted")
