import pandas as pd
import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services import technical_analysis


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_technical_cache(monkeypatch):
    monkeypatch.setattr(
        settings,
        "alpha_vantage_api_key",
        "",
    )

    technical_analysis.clear_technical_cache()

    yield

    technical_analysis.clear_technical_cache()



def test_technical_analysis_uses_real_yahoo_fallback_without_api_key(
    client,
    monkeypatch,
):
    from app.services import technical_analysis

    monkeypatch.setattr(
        technical_analysis.settings,
        "alpha_vantage_api_key",
        "",
    )

    dates = pd.date_range(
        end="2026-10-13",
        periods=80,
        freq="B",
    )

    closes = [
        100.0 + index * 0.75 + (index % 5) * 0.2
        for index in range(80)
    ]

    history = pd.DataFrame(
        {"Close": closes},
        index=dates,
    )

    class FakeTicker:
        def history(self, **kwargs):
            return history

    monkeypatch.setattr(
        technical_analysis.yf,
        "Ticker",
        lambda symbol: FakeTicker(),
    )

    technical_analysis.clear_technical_cache()

    response = client.get("/api/v1/market/technical/AAPL")

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["symbol"] == "AAPL"
    assert data["latest_close"] == closes[-1]
    assert data["sma_20"] is not None
    assert data["sma_50"] is not None
    assert 0 <= data["rsi_14"] <= 100
    assert data["momentum_20d_percent"] is not None
    assert data["daily_volatility_percent"] >= 0
    assert data["is_demo"] is False
    assert data["source"] == "Yahoo Finance via yfinance history"
    assert data["latest_trading_day"] == dates[-1].date().isoformat()

def test_technical_analysis_rejects_invalid_symbol(client):
    response = client.get(
        "/api/v1/market/technical/AAPL%21"
    )

    assert response.status_code == 422


def test_unsupported_symbol_returns_503(client, monkeypatch):
    from app.services import historical_prices

    historical_prices.clear_historical_cache()
    monkeypatch.setattr(
        historical_prices,
        "_fetch_yahoo_history_sync",
        lambda symbol: [],
    )

    response = client.get(
        "/api/v1/market/technical/UNKNOWNXYZ"
    )

    assert response.status_code == 503


def test_technical_analysis_supports_unlisted_valid_symbol(client, monkeypatch):
    """Verify arbitrary valid symbol outside presets is analyzed when history is available."""
    dates = pd.date_range(end="2026-10-13", periods=80, freq="B")
    closes = [20.0 + i * 0.1 for i in range(80)]
    history = pd.DataFrame({"Close": closes}, index=dates)

    class FakeTicker:
        def history(self, **kwargs):
            return history

    monkeypatch.setattr(technical_analysis.yf, "Ticker", lambda symbol: FakeTicker())
    technical_analysis.clear_technical_cache()

    response = client.get("/api/v1/market/technical/INTC")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "INTC"
    assert data["latest_close"] == closes[-1]
    assert data["sma_20"] is not None
    assert data["technical_bias"] in ("bullish", "bearish", "neutral", "insufficient_data")


def test_technical_analysis_insufficient_history_sets_insufficient_data(client, monkeypatch):
    """When fewer than 50 observations exist, bias is strictly insufficient_data without fabricating points."""
    dates = pd.date_range(end="2026-10-13", periods=25, freq="B")
    closes = [100.0 + i * 0.5 for i in range(25)]
    history = pd.DataFrame({"Close": closes}, index=dates)

    class FakeTicker:
        def history(self, **kwargs):
            return history

    monkeypatch.setattr(technical_analysis.yf, "Ticker", lambda symbol: FakeTicker())
    technical_analysis.clear_technical_cache()

    response = client.get("/api/v1/market/technical/SHORT_HIST")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "SHORT_HIST"
    assert data["sma_20"] is not None
    assert data["sma_50"] is None  # Not enough periods for 50-day SMA
    assert data["technical_bias"] == "insufficient_data"
