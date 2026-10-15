import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import market_data


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client



def test_market_quote_uses_real_yahoo_fallback_without_api_key(
    client,
    monkeypatch,
):
    from app.services import market_data

    monkeypatch.setattr(
        market_data.settings,
        "alpha_vantage_api_key",
        "",
    )

    dates = pd.date_range(
        end="2026-10-13",
        periods=3,
        freq="B",
    )

    history = pd.DataFrame(
        {
            "Open": [98.0, 99.0, 100.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [97.0, 98.0, 99.0],
            "Close": [99.0, 100.0, 102.0],
            "Volume": [1000, 1100, 1200],
        },
        index=dates,
    )

    class FakeTicker:
        def history(self, **kwargs):
            return history

    monkeypatch.setattr(
        market_data.yf,
        "Ticker",
        lambda symbol: FakeTicker(),
    )

    market_data.clear_market_cache()

    response = client.get("/api/v1/market/quote/AAPL")

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["symbol"] == "AAPL"
    assert data["price"] == 102.0
    assert data["source"] == "Yahoo Finance via yfinance history"
    assert data["is_demo"] is False
    assert "SYNTHETIC" not in data["data_note"]

def test_market_quote_rejects_invalid_symbol_format(client):
    response = client.get(
        "/api/v1/market/quote/AAPL%21"
    )

    assert response.status_code == 422


def test_unsupported_demo_symbol_returns_unavailable(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        market_data.settings,
        "alpha_vantage_api_key",
        "",
    )
    monkeypatch.setattr(
        "app.services.historical_prices._fetch_yahoo_history_sync",
        lambda symbol: [],
    )

    market_data.clear_market_cache()

    response = client.get(
        "/api/v1/market/quote/UNKNOWNXYZ"
    )

    assert response.status_code == 503


def test_unlisted_valid_symbol_is_supported_by_fallback(client, monkeypatch):
    """Verify arbitrary valid ticker (e.g. AMD, INTC, SPY) is not blocked by a 5-symbol whitelist."""
    monkeypatch.setattr(
        market_data.settings,
        "alpha_vantage_api_key",
        "",
    )

    dates = pd.date_range(end="2026-10-13", periods=3, freq="B")
    history = pd.DataFrame(
        {
            "Open": [150.0, 152.0, 155.0],
            "High": [153.0, 156.0, 158.0],
            "Low": [149.0, 151.0, 153.0],
            "Close": [151.0, 154.0, 157.0],
            "Volume": [2000, 2100, 2200],
        },
        index=dates,
    )

    class FakeTicker:
        def history(self, **kwargs):
            return history

    monkeypatch.setattr(market_data.yf, "Ticker", lambda symbol: FakeTicker())
    market_data.clear_market_cache()

    # AMD is NOT in the presets (AAPL, MSFT, NVDA, GOOGL, TSLA)
    response = client.get("/api/v1/market/quote/AMD")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AMD"
    assert data["price"] == 157.0
    assert data["source"] == "Yahoo Finance via yfinance history"
    assert data["is_demo"] is False
