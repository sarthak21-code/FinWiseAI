import asyncio
import math
import re
import statistics
import time

from datetime import datetime, timezone

import httpx
import yfinance as yf

from app.core.config import settings
from app.schemas.technical import TechnicalAnalysis
from app.services.historical_prices import HistoricalDataUnavailable, clear_historical_cache, get_historical_prices
from app.services.market_data import (
    ALPHA_VANTAGE_URL,
    DEMO_QUOTES,
    MarketDataUnavailable,
)


CACHE_TTL_SECONDS = 900

_history_cache: dict[
    str,
    tuple[float, TechnicalAnalysis],
] = {}


def clear_technical_cache() -> None:
    """Clear technical and shared historical-data caches."""
    _history_cache.clear()
    clear_historical_cache()


def _normalize_symbol(raw_symbol: str) -> str:
    symbol = raw_symbol.strip().upper()

    if not re.fullmatch(r"[A-Z0-9.^=_-]{1,24}", symbol):
        raise ValueError(
            "Invalid ticker format."
        )

    return symbol


def _calculate_rsi(
    closes: list[float],
    period: int = 14,
) -> float | None:
    if len(closes) < period + 1:
        return None

    recent = closes[-(period + 1):]

    changes = [
        recent[index] - recent[index - 1]
        for index in range(1, len(recent))
    ]

    gains = [
        change if change > 0 else 0.0
        for change in changes
    ]

    losses = [
        -change if change < 0 else 0.0
        for change in changes
    ]

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0

    relative_strength = average_gain / average_loss

    return 100 - (100 / (1 + relative_strength))


def _calculate_sma(
    closes: list[float],
    period: int,
) -> float | None:
    if len(closes) < period:
        return None

    return sum(closes[-period:]) / period


async def get_technical_analysis(
    raw_symbol: str,
) -> TechnicalAnalysis:
    """Calculate indicators using the shared validated price history."""

    symbol = _normalize_symbol(raw_symbol)

    cached = _history_cache.get(symbol)

    if cached is not None:
        timestamp, result = cached

        if time.monotonic() - timestamp < CACHE_TTL_SECONDS:
            return result

        _history_cache.pop(symbol, None)

    try:
        history = await get_historical_prices(symbol)
    except HistoricalDataUnavailable as exc:
        raise MarketDataUnavailable(str(exc)) from exc

    if not history.bars:
        raise MarketDataUnavailable(
            f"No valid historical prices are available for {symbol}."
        )

    closes = [bar.close for bar in history.bars]
    latest_trading_day = history.bars[-1].trading_day
    source = history.source
    is_demo = False
    data_note = history.data_note
    latest_close = closes[-1]

    sma_20 = _calculate_sma(closes, 20)
    sma_50 = _calculate_sma(closes, 50)
    rsi_14 = _calculate_rsi(closes, 14)

    momentum_20d_percent = None

    if len(closes) >= 21 and closes[-21] > 0:
        momentum_20d_percent = (
            (closes[-1] / closes[-21]) - 1
        ) * 100

    daily_volatility_percent = None

    if len(closes) >= 3:
        returns = [
            closes[index] / closes[index - 1] - 1
            for index in range(1, len(closes))
            if closes[index - 1] > 0
        ]

        # Standard deviation of the most recent 20 daily returns.
        recent_returns = returns[-20:]

        if len(recent_returns) >= 2:
            daily_volatility_percent = (
                statistics.pstdev(recent_returns) * 100
            )

    evidence: list[str] = []

    if sma_20 is not None:
        difference = (
            (latest_close / sma_20) - 1
        ) * 100

        direction = (
            "above" if difference >= 0 else "below"
        )

        evidence.append(
            f"Latest close is {abs(difference):.2f}% "
            f"{direction} the 20-observation moving average."
        )

    if sma_50 is not None:
        direction = (
            "above" if latest_close >= sma_50 else "below"
        )

        evidence.append(
            f"Latest close is {direction} the 50-observation "
            "moving average."
        )

    if rsi_14 is not None:
        evidence.append(
            f"RSI(14) is {rsi_14:.2f}."
        )

    if momentum_20d_percent is not None:
        evidence.append(
            f"20-observation price momentum is "
            f"{momentum_20d_percent:+.2f}%."
        )

    if daily_volatility_percent is not None:
        evidence.append(
            f"Recent daily-return volatility is "
            f"{daily_volatility_percent:.2f}%."
        )

    if len(closes) < 50:
        technical_bias = "insufficient_data"

        evidence.append(
            "At least 50 valid closing-price observations are "
            "required for this engine's bias classification."
        )

    elif (
        latest_close > sma_20
        and rsi_14 is not None
        and rsi_14 >= 55
        and momentum_20d_percent is not None
        and momentum_20d_percent > 0
    ):
        technical_bias = "bullish"

        evidence.append(
            "Rule-based classification: price is above SMA20, "
            "RSI is at least 55, and 20-observation momentum is positive."
        )

    elif (
        latest_close < sma_20
        and rsi_14 is not None
        and rsi_14 <= 45
        and momentum_20d_percent is not None
        and momentum_20d_percent < 0
    ):
        technical_bias = "bearish"

        evidence.append(
            "Rule-based classification: price is below SMA20, "
            "RSI is at most 45, and 20-observation momentum is negative."
        )

    else:
        technical_bias = "neutral"

        evidence.append(
            "The configured bullish or bearish conditions "
            "are not all satisfied."
        )


    result = TechnicalAnalysis(
        symbol=symbol,
        latest_close=latest_close,
        latest_trading_day=latest_trading_day,
        calculated_at_utc=datetime.now(timezone.utc),
        sma_20=sma_20,
        sma_50=sma_50,
        rsi_14=rsi_14,
        momentum_20d_percent=momentum_20d_percent,
        daily_volatility_percent=daily_volatility_percent,
        technical_bias=technical_bias,
        evidence=evidence,
        source=source,
        is_demo=is_demo,
        data_note=data_note,
    )

    _history_cache[symbol] = (
        time.monotonic(),
        result,
    )

    return result