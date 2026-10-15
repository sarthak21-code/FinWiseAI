import asyncio
import math
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import yfinance as yf

from app.core.config import settings
from app.schemas.market import MarketQuote
from app.services.historical_prices import HistoricalDataUnavailable, clear_historical_cache, get_historical_prices


ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"

# Cache market responses to reduce provider requests.
CACHE_TTL_SECONDS = 900

_cache: dict[str, tuple[float, MarketQuote]] = {}


class InvalidMarketSymbol(ValueError):
    """Raised when a ticker symbol has an invalid format."""


class MarketDataUnavailable(RuntimeError):
    """Raised when neither a provider quote nor demo data is available."""


# These values are synthetic examples, NOT current market prices.
# They exist only to keep development and demonstrations functional.
DEMO_QUOTES: dict[str, dict[str, float | int]] = {
    "AAPL": {
        "price": 190.00,
        "open": 188.50,
        "high": 191.20,
        "low": 187.80,
        "previous_close": 189.00,
        "volume": 1250000,
    },
    "MSFT": {
        "price": 420.00,
        "open": 417.00,
        "high": 423.00,
        "low": 415.50,
        "previous_close": 418.00,
        "volume": 950000,
    },
    "NVDA": {
        "price": 125.00,
        "open": 123.00,
        "high": 127.00,
        "low": 122.00,
        "previous_close": 124.00,
        "volume": 2500000,
    },
    "TSLA": {
        "price": 240.00,
        "open": 238.00,
        "high": 244.00,
        "low": 235.00,
        "previous_close": 242.00,
        "volume": 1800000,
    },
    "RELIANCE.BSE": {
        "price": 1400.00,
        "open": 1390.00,
        "high": 1415.00,
        "low": 1382.00,
        "previous_close": 1395.00,
        "volume": 750000,
    },
    "TCS.BSE": {
        "price": 3500.00,
        "open": 3480.00,
        "high": 3530.00,
        "low": 3460.00,
        "previous_close": 3490.00,
        "volume": 180000,
    },
}


def clear_market_cache() -> None:
    """Clear quote and shared historical-data caches."""
    _cache.clear()
    clear_historical_cache()


def _normalize_symbol(raw_symbol: str) -> str:
    symbol = raw_symbol.strip().upper()

    if not re.fullmatch(r"[A-Z0-9.^=_-]{1,24}", symbol):
        raise InvalidMarketSymbol(
            "Invalid ticker format. Use 1-24 letters, digits, "
            "or supported ticker punctuation."
        )

    return symbol


def _get_currency(symbol: str) -> str | None:
    suffix = symbol.rsplit(".", 1)[-1] if "." in symbol else ""

    currencies = {
        "BSE": "INR",
        "NSE": "INR",
        "LON": "GBP",
        "DEX": "EUR",
        "TRT": "CAD",
        "TRV": "CAD",
        "SHH": "CNY",
        "SHZ": "CNY",
    }

    if suffix:
        return currencies.get(suffix)

    # A bare ticker is assumed to be a US-listed symbol.
    # Do not make this assumption for unknown exchange suffixes.
    return "USD"


def _number(
    data: dict[str, Any],
    key: str,
) -> float | None:
    try:
        value = float(data[key])

        if not math.isfinite(value):
            return None

        return value

    except (KeyError, TypeError, ValueError):
        return None


def _demo_quote(symbol: str, reason: str) -> MarketQuote:
    sample = DEMO_QUOTES.get(symbol)

    if sample is None:
        raise MarketDataUnavailable(
            f"No market data is currently available for {symbol}. "
            "Configure a market data API key or use a supported demo ticker."
        )

    price = float(sample["price"])
    previous_close = float(sample["previous_close"])

    change = price - previous_close
    change_percent = (
        (change / previous_close) * 100
        if previous_close
        else 0.0
    )

    currency = _get_currency(symbol)

    return MarketQuote(
        symbol=symbol,
        price=price,
        change=change,
        change_percent=change_percent,
        open=float(sample["open"]),
        high=float(sample["high"]),
        low=float(sample["low"]),
        previous_close=previous_close,
        volume=int(sample["volume"]),
        currency=currency,
        latest_trading_day="SYNTHETIC SAMPLE",
        fetched_at_utc=datetime.now(timezone.utc),
        source="SYNTHETIC DEMO",
        is_demo=True,
        data_note=(
            "SYNTHETIC DEMONSTRATION DATA. This is not a real market quote "
            "and must not be used for investment decisions. "
            f"Reason: {reason}"
        ),
    )


def _get_fallback(symbol: str, reason: str) -> MarketQuote:
    return _demo_quote(symbol, reason)


async def _get_yahoo_fallback(
    symbol: str,
    alpha_reason: str,
) -> MarketQuote:
    # Use genuine historical data instead of silently substituting
    # a synthetic quote when Alpha Vantage is unavailable.

    try:
        history = await asyncio.to_thread(
            yf.Ticker(symbol).history,
            period="5d",
            interval="1d",
            auto_adjust=False,
        )

        if (
            history is None
            or history.empty
            or "Close" not in history.columns
        ):
            raise ValueError("No usable daily history was returned.")

        history = history.dropna(subset=["Close"]).sort_index()

        if history.empty:
            raise ValueError("No valid closing prices were returned.")

        latest = history.iloc[-1]
        price = float(latest["Close"])

        if not math.isfinite(price) or price <= 0:
            raise ValueError("The latest closing price is invalid.")

        if len(history) >= 2:
            previous_close = float(history.iloc[-2]["Close"])
        else:
            previous_close = price

        if (
            not math.isfinite(previous_close)
            or previous_close <= 0
        ):
            previous_close = price

        change = price - previous_close
        change_percent = (
            (change / previous_close) * 100
            if previous_close > 0
            else 0.0
        )

        def history_number(column: str) -> float | None:
            try:
                value = float(latest[column])
            except (KeyError, TypeError, ValueError):
                return None

            return value if math.isfinite(value) else None

        raw_volume = history_number("Volume")
        date_index = history.index[-1]
        trading_day = date_index.date().isoformat()

        return MarketQuote(
            symbol=symbol,
            price=price,
            change=change,
            change_percent=change_percent,
            open=history_number("Open"),
            high=history_number("High"),
            low=history_number("Low"),
            previous_close=previous_close,
            volume=(
                int(raw_volume)
                if raw_volume is not None and raw_volume >= 0
                else None
            ),
            currency=_get_currency(symbol),
            latest_trading_day=trading_day,
            fetched_at_utc=datetime.now(timezone.utc),
            source="Yahoo Finance via yfinance history",
            is_demo=False,
            data_note=(
                "Fallback to genuine Yahoo Finance daily data because "
                f"Alpha Vantage was unavailable: {alpha_reason} "
                "This is not a real-time quote."
            ),
        )

    except Exception as exc:
        raise MarketDataUnavailable(
            f"No verified market quote is available for {symbol}. "
            f"Alpha Vantage: {alpha_reason} "
            f"Yahoo Finance: {type(exc).__name__}: {str(exc)[:180]}. "
            "Synthetic quotes were not substituted."
        ) from exc

async def get_market_quote(raw_symbol: str) -> MarketQuote:
    """Build a quote from the shared, validated historical-price service."""

    symbol = _normalize_symbol(raw_symbol)

    try:
        history = await get_historical_prices(symbol)
    except HistoricalDataUnavailable as exc:
        raise MarketDataUnavailable(str(exc)) from exc

    if not history.bars:
        raise MarketDataUnavailable(
            f"No usable historical prices are available for {symbol}."
        )

    latest = history.bars[-1]
    previous = history.bars[-2] if len(history.bars) >= 2 else latest

    price = latest.close
    previous_close = previous.close

    change = price - previous_close
    change_percent = (
        change / previous_close * 100
        if previous_close > 0
        else 0.0
    )

    return MarketQuote(
        symbol=symbol,
        price=price,
        change=change,
        change_percent=change_percent,
        open=latest.open,
        high=latest.high,
        low=latest.low,
        previous_close=previous_close,
        volume=latest.volume,
        currency=_get_currency(symbol),
        latest_trading_day=latest.trading_day,
        fetched_at_utc=history.fetched_at_utc,
        source=history.source,
        is_demo=False,
        data_note=history.data_note,
    )

