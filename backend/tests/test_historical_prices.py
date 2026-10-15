import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.services import historical_prices as hp


@pytest.fixture(autouse=True)
def clean_history_cache():
    hp.clear_historical_cache()
    yield
    hp.clear_historical_cache()


def alpha_payload(days=60):
    series = {}

    for day in pd.bdate_range(end="2026-10-13", periods=days):
        date = day.strftime("%Y-%m-%d")
        close = 100 + len(series)
        series[date] = {
            "1. open": str(close - 1),
            "2. high": str(close + 1),
            "3. low": str(close - 2),
            "4. close": str(close),
            "5. volume": "100000",
        }

    return {"Time Series (Daily)": series}


def yahoo_frame(days=60):
    index = pd.bdate_range(end="2026-10-13", periods=days)
    closes = [100.0 + i for i in range(days)]

    return pd.DataFrame(
        {
            "Open": [value - 1 for value in closes],
            "High": [value + 1 for value in closes],
            "Low": [value - 2 for value in closes],
            "Close": closes,
            "Volume": [100000] * days,
        },
        index=index,
    )


def test_alpha_parser_returns_sorted_valid_bars():
    bars = hp._parse_alpha_history(alpha_payload(5))

    assert len(bars) == 5
    assert [bar.trading_day for bar in bars] == sorted(
        bar.trading_day for bar in bars
    )
    assert all(bar.close > 0 for bar in bars)
    assert all(bar.volume == 100000 for bar in bars)


def test_alpha_parser_rejects_invalid_and_non_finite_closes():
    payload = {
        "Time Series (Daily)": {
            "2026-10-10": {
                "1. open": "10",
                "2. high": "12",
                "3. low": "9",
                "4. close": "nan",
                "5. volume": "100",
            },
            "2026-10-11": {
                "1. open": "10",
                "2. high": "12",
                "3. low": "9",
                "4. close": "-1",
                "5. volume": "100",
            },
            "not-a-date": {
                "1. open": "10",
                "2. high": "12",
                "3. low": "9",
                "4. close": "11",
                "5. volume": "100",
            },
        }
    }

    assert hp._parse_alpha_history(payload) == []


def test_yahoo_parser_returns_unique_sorted_bars():
    frame = yahoo_frame(5)
    bars = hp._parse_yahoo_history(frame)

    assert len(bars) == 5
    assert [bar.trading_day for bar in bars] == sorted(
        bar.trading_day for bar in bars
    )


def test_yahoo_parser_handles_empty_history():
    assert hp._parse_yahoo_history(pd.DataFrame()) == []


def test_cached_history_is_reused_within_ttl():
    payload = alpha_payload(60)
    from unittest.mock import MagicMock
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None

    async def fake_get(*args, **kwargs):
        return response

    async def scenario():
        with patch.object(hp.settings, "alpha_vantage_api_key", "test-key"), \
             patch("app.services.historical_prices.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get = fake_get

            first = await hp.get_historical_prices("AAPL")
            second = await hp.get_historical_prices("AAPL")

        assert first is second
        assert first.source == "Alpha Vantage daily OHLCV"

    asyncio.run(scenario())


def test_expired_cache_is_refetched():
    payload = alpha_payload(60)
    from unittest.mock import MagicMock
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None

    async def fake_get(*args, **kwargs):
        return response

    async def scenario():
        with patch.object(hp.settings, "alpha_vantage_api_key", "test-key"), \
             patch("app.services.historical_prices.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get = fake_get

            first = await hp.get_historical_prices("AAPL")

            hp._cache["AAPL"] = (
                time.monotonic() - hp.CACHE_TTL_SECONDS - 1,
                first,
            )

            second = await hp.get_historical_prices("AAPL")

        assert second is not first
        assert second.source == "Alpha Vantage daily OHLCV"

    asyncio.run(scenario())


def test_yahoo_is_used_when_alpha_vantage_has_insufficient_history():
    async def fake_get(*args, **kwargs):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return alpha_payload(5)

        return Response()

    async def scenario():
        with patch.object(hp.settings, "alpha_vantage_api_key", "test-key"), \
             patch("app.services.historical_prices.httpx.AsyncClient") as client, \
             patch(
                 "app.services.historical_prices._fetch_yahoo_history_sync",
                 return_value=hp._parse_yahoo_history(yahoo_frame(60)),
             ):
            client.return_value.__aenter__.return_value.get = fake_get

            history = await hp.get_historical_prices("MSFT")

        assert history.source == "Yahoo Finance via yfinance history"
        assert len(history.bars) == 60
        assert "Alpha Vantage" in history.data_note

    asyncio.run(scenario())


def test_partial_alpha_history_is_preserved_if_yahoo_fails():
    async def fake_get(*args, **kwargs):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return alpha_payload(5)

        return Response()

    async def scenario():
        with patch.object(hp.settings, "alpha_vantage_api_key", "test-key"), \
             patch("app.services.historical_prices.httpx.AsyncClient") as client, \
             patch(
                 "app.services.historical_prices._fetch_yahoo_history_sync",
                 side_effect=RuntimeError("provider unavailable"),
             ):
            client.return_value.__aenter__.return_value.get = fake_get

            history = await hp.get_historical_prices("NVDA")

        assert len(history.bars) == 5
        assert history.source == "Alpha Vantage daily OHLCV"
        assert "insufficient" in history.data_note.lower()

    asyncio.run(scenario())


def test_no_history_raises_instead_of_fabricating_prices():
    async def fake_get(*args, **kwargs):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"Note": "API rate limit reached"}

        return Response()

    async def scenario():
        with patch.object(hp.settings, "alpha_vantage_api_key", "test-key"), \
             patch("app.services.historical_prices.httpx.AsyncClient") as client, \
             patch(
                 "app.services.historical_prices._fetch_yahoo_history_sync",
                 return_value=[],
             ):
            client.return_value.__aenter__.return_value.get = fake_get

            with pytest.raises(hp.HistoricalDataUnavailable):
                await hp.get_historical_prices("TSLA")

    asyncio.run(scenario())


def test_provider_error_text_is_not_exposed_in_history_error():
    secret_marker = "SENSITIVE_PROVIDER_TOKEN_SENTINEL"

    async def fake_get(*args, **kwargs):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"Information": f"Invalid API key {secret_marker}"}

        return Response()

    async def scenario():
        with patch.object(hp.settings, "alpha_vantage_api_key", "test-key"), \
             patch("app.services.historical_prices.httpx.AsyncClient") as client, \
             patch(
                 "app.services.historical_prices._fetch_yahoo_history_sync",
                 return_value=[],
             ):
            client.return_value.__aenter__.return_value.get = fake_get

            with pytest.raises(hp.HistoricalDataUnavailable) as exc_info:
                await hp.get_historical_prices("TSLA")

        assert secret_marker not in str(exc_info.value)
        assert "provider notice or error" in str(exc_info.value)

    asyncio.run(scenario())
