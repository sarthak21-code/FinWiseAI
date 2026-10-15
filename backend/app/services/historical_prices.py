import asyncio
import math
import re
import time

from dataclasses import dataclass
from datetime import datetime, timezone, time as datetime_time
from typing import Any

import httpx
import yfinance as yf

from app.core.config import settings


ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
CACHE_TTL_SECONDS = 900
PREFERRED_MIN_OBSERVATIONS = 50


class HistoricalDataUnavailable(RuntimeError):
    """Raised when neither provider supplies usable historical prices."""


@dataclass(frozen=True)
class HistoricalBar:
    trading_day: str
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: int | None


@dataclass(frozen=True)
class HistoricalPriceHistory:
    symbol: str
    bars: tuple[HistoricalBar, ...]
    source: str
    fetched_at_utc: datetime
    data_note: str


_cache: dict[
    str,
    tuple[float, HistoricalPriceHistory],
] = {}


def clear_historical_cache() -> None:
    """Clear shared history cache for tests and development."""
    _cache.clear()


def _normalize_symbol(raw_symbol: str) -> str:
    symbol = raw_symbol.strip().upper()

    if not re.fullmatch(r"[A-Z0-9.^=_-]{1,24}", symbol):
        raise ValueError("Invalid ticker format.")

    return symbol


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def _optional_positive(value: Any) -> float | None:
    number = _finite_number(value)

    if number is None or number <= 0:
        return None

    return number


def _parse_alpha_history(
    payload: dict[str, Any],
) -> list[HistoricalBar]:
    series = payload.get("Time Series (Daily)")

    if not isinstance(series, dict):
        return []

    bars: list[HistoricalBar] = []

    for trading_day, row in sorted(series.items()):
        if not isinstance(row, dict):
            continue

        try:
            datetime.strptime(trading_day, "%Y-%m-%d")
        except (TypeError, ValueError):
            continue

        close = _optional_positive(row.get("4. close"))

        if close is None:
            continue

        raw_volume = _finite_number(row.get("5. volume"))

        bars.append(
            HistoricalBar(
                trading_day=trading_day,
                open=_optional_positive(row.get("1. open")),
                high=_optional_positive(row.get("2. high")),
                low=_optional_positive(row.get("3. low")),
                close=close,
                volume=(
                    int(raw_volume)
                    if raw_volume is not None and raw_volume >= 0
                    else None
                ),
            )
        )

    return bars


def _parse_yahoo_history(history: Any) -> list[HistoricalBar]:
    if history is None or history.empty or "Close" not in history.columns:
        return []

    bars: list[HistoricalBar] = []

    for timestamp, row in history.sort_index().iterrows():
        close = _optional_positive(row.get("Close"))

        if close is None:
            continue

        try:
            trading_day = timestamp.date().isoformat()
        except (AttributeError, ValueError):
            continue

        raw_volume = _finite_number(row.get("Volume"))

        bars.append(
            HistoricalBar(
                trading_day=trading_day,
                open=_optional_positive(row.get("Open")),
                high=_optional_positive(row.get("High")),
                low=_optional_positive(row.get("Low")),
                close=close,
                volume=(
                    int(raw_volume)
                    if raw_volume is not None and raw_volume >= 0
                    else None
                ),
            )
        )

    # A provider should not return duplicate daily observations.
    unique: dict[str, HistoricalBar] = {
        bar.trading_day: bar for bar in bars
    }

    return [unique[day] for day in sorted(unique)]


def _fetch_yahoo_history_sync(symbol: str) -> list[HistoricalBar]:
    """Fetch completed daily bars from Yahoo Finance.

    When the US regular trading session is open, exclude its current
    daily candle because the final closing price is not yet available.
    """

    history = yf.Ticker(symbol).history(
        period="6mo",
        interval="1d",
        auto_adjust=False,
    )

    if history is None or history.empty:
        return []

    # yfinance normally returns an exchange-timezone-aware index.
    # Use its timezone rather than assuming the computer's timezone.
    index_timezone = getattr(history.index, "tz", None)

    if index_timezone is not None:
        market_now = datetime.now(index_timezone)
        market_time = market_now.time().replace(tzinfo=None)

        market_is_open = (
            market_now.weekday() < 5
            and datetime_time(9, 30)
            <= market_time
            < datetime_time(16, 0)
        )

        if market_is_open:
            history = history.loc[
                [
                    timestamp.date() < market_now.date()
                    for timestamp in history.index
                ]
            ]

    return _parse_yahoo_history(history)


def _make_history(
    symbol: str,
    bars: list[HistoricalBar],
    source: str,
    note: str,
) -> HistoricalPriceHistory:
    if not bars:
        raise HistoricalDataUnavailable(
            f"No valid historical closing prices were returned for {symbol}."
        )

    return HistoricalPriceHistory(
        symbol=symbol,
        bars=tuple(bars),
        source=source,
        fetched_at_utc=datetime.now(timezone.utc),
        data_note=note,
    )


async def get_historical_prices(
    raw_symbol: str,
) -> HistoricalPriceHistory:
    """Return shared, validated historical prices with provider fallback."""

    symbol = _normalize_symbol(raw_symbol)

    cached = _cache.get(symbol)

    if cached is not None:
        cached_at, cached_history = cached

        if time.monotonic() - cached_at < CACHE_TTL_SECONDS:
            return cached_history

        _cache.pop(symbol, None)

    alpha_problem = "Alpha Vantage API key is not configured."
    partial_alpha: list[HistoricalBar] = []

    # Primary provider: Alpha Vantage.
    if settings.alpha_vantage_api_key:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": settings.alpha_vantage_api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get(
                    ALPHA_VANTAGE_URL,
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()

            if not isinstance(payload, dict):
                alpha_problem = "Alpha Vantage returned an unexpected response."

            else:
                provider_message = (
                    payload.get("Note")
                    or payload.get("Information")
                    or payload.get("Error Message")
                )

                if provider_message:
                    # Provider error bodies may echo request credentials.
                    # Keep client-facing diagnostics generic and never relay
                    # arbitrary upstream response text.
                    alpha_problem = (
                        "Alpha Vantage returned a provider notice or error."
                    )

                else:
                    partial_alpha = _parse_alpha_history(payload)

                    if len(partial_alpha) >= PREFERRED_MIN_OBSERVATIONS:
                        history = _make_history(
                            symbol,
                            partial_alpha,
                            "Alpha Vantage daily OHLCV",
                            (
                                "Validated historical daily OHLCV data "
                                "from Alpha Vantage. Not real-time."
                            ),
                        )

                        _cache[symbol] = (
                            time.monotonic(),
                            history,
                        )

                        return history

                    alpha_problem = (
                        "Alpha Vantage returned "
                        f"{len(partial_alpha)} valid closing prices; "
                        f"{PREFERRED_MIN_OBSERVATIONS} are preferred "
                        "for the full technical analysis."
                    )

        except (httpx.HTTPError, ValueError) as exc:
            alpha_problem = (
                f"Alpha Vantage request failed: {type(exc).__name__}."
            )

    # Secondary provider: Yahoo Finance.
    try:
        yahoo_bars = await asyncio.to_thread(
            _fetch_yahoo_history_sync,
            symbol,
        )

        if yahoo_bars:
            # Prefer the fallback when it contains sufficient history,
            # or when it contains more observations than the partial
            # primary result.
            if (
                len(yahoo_bars) >= PREFERRED_MIN_OBSERVATIONS
                or len(yahoo_bars) >= len(partial_alpha)
            ):
                history = _make_history(
                    symbol,
                    yahoo_bars,
                    "Yahoo Finance via yfinance history",
                    (
                        "Validated historical daily prices from Yahoo Finance. "
                        f"Alpha Vantage was unavailable or provided insufficient "
                        f"history: {alpha_problem} Not real-time."
                    ),
                )

                _cache[symbol] = (
                    time.monotonic(),
                    history,
                )

                return history

    except Exception as exc:
        yahoo_problem = (
            f"{type(exc).__name__}: {str(exc)[:180]}"
        )

    else:
        yahoo_problem = "Yahoo Finance returned no valid historical prices."

    # If neither source produced a full history, retain a real partial
    # history when one exists. The technical agent will explicitly report
    # insufficient history rather than inventing more observations.
    if partial_alpha:
        history = _make_history(
            symbol,
            partial_alpha,
            "Alpha Vantage daily OHLCV",
            (
                f"Only {len(partial_alpha)} valid observations were available. "
                f"Yahoo Finance fallback was unavailable or insufficient: "
                f"{yahoo_problem} Technical analysis may be insufficient."
            ),
        )

        _cache[symbol] = (
            time.monotonic(),
            history,
        )

        return history

    raise HistoricalDataUnavailable(
        f"No verified historical prices are available for {symbol}. "
        f"Alpha Vantage: {alpha_problem} "
        f"Yahoo Finance: {yahoo_problem}. "
        "Synthetic data was not substituted."
    )
