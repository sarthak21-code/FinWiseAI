
import asyncio
import math
from app.schemas.intelligence import AgentAssessment
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from app.schemas.fundamental import FundamentalMetrics


class FundamentalDataUnavailable(RuntimeError):
    """Raised when verified company fundamentals cannot be retrieved."""


def _finite_number(value: Any) -> float | None:
    """Convert a value to a finite float without inventing data."""
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def _read_info_value(info: dict[str, Any], key: str) -> float | None:
    return _finite_number(info.get(key))


def _fetch_sync(symbol: str) -> FundamentalMetrics:
    """Fetch and normalize fundamentals from Yahoo Finance."""

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.get_info()
    except Exception as exc:
        raise FundamentalDataUnavailable(
            "Yahoo Finance could not provide company fundamentals."
        ) from exc

    if not isinstance(info, dict) or not info:
        raise FundamentalDataUnavailable(
            f"No company overview is available for {symbol}."
        )

    returned_symbol = str(info.get("symbol", "")).strip().upper()

    if returned_symbol != symbol:
        raise FundamentalDataUnavailable(
            "The provider did not verify the requested ticker symbol."
        )

    warnings = [
        "Yahoo Finance is an unofficial data interface; availability "
        "and data coverage may change.",
        "Financial metrics can refer to different reporting periods.",
        "This assessment is informational, not personalized investment advice.",
    ]

    profit_margin = _read_info_value(info, "profitMargins")
    revenue_growth = _read_info_value(info, "revenueGrowth")
    return_on_equity = _read_info_value(info, "returnOnEquity")

    # Yahoo Finance generally reports these three metrics as fractions.
    net_margin_percent = (
        profit_margin * 100 if profit_margin is not None else None
    )
    revenue_growth_percent = (
        revenue_growth * 100 if revenue_growth is not None else None
    )
    return_on_equity_percent = (
        return_on_equity * 100 if return_on_equity is not None else None
    )

    return FundamentalMetrics(
        symbol=symbol,
        company_name=info.get("shortName") or info.get("longName"),
        currency=info.get("currency"),
        fiscal_year=None,
        fiscal_period=None,
        revenue=_read_info_value(info, "totalRevenue"),
        revenue_growth_percent=revenue_growth_percent,
        net_income=_read_info_value(info, "netIncomeToCommon"),
        net_margin_percent=net_margin_percent,
        return_on_equity_percent=return_on_equity_percent,
        debt_to_equity=_read_info_value(info, "debtToEquity"),
        current_ratio=_read_info_value(info, "currentRatio"),
        pe_ratio=_read_info_value(info, "trailingPE"),
        eps=_read_info_value(info, "trailingEps"),
        source="Yahoo Finance via yfinance",
        fetched_at_utc=datetime.now(timezone.utc),
        is_demo=False,
        data_warnings=warnings,
    )


async def fetch_fundamental_metrics(
    raw_symbol: str,
) -> FundamentalMetrics:
    """Asynchronously fetch verified fundamentals."""

    symbol = raw_symbol.strip().upper()

    if not symbol or len(symbol) > 24:
        raise ValueError("Provide a valid ticker symbol.")

    if not all(char.isalnum() or char in ".-^=" for char in symbol):
        raise ValueError("Ticker symbol contains invalid characters.")

    return await asyncio.to_thread(_fetch_sync, symbol)

def interpret_fundamentals(
    metrics: FundamentalMetrics,
) -> AgentAssessment:
    """Interpret available fundamental metrics using transparent rules."""

    evidence: list[str] = []
    limitations = list(metrics.data_warnings)
    positive_signals = 0
    negative_signals = 0

    margin = metrics.net_margin_percent
    growth = metrics.revenue_growth_percent
    roe = metrics.return_on_equity_percent
    current_ratio = metrics.current_ratio
    pe_ratio = metrics.pe_ratio

    if margin is not None:
        evidence.append(f"Net profit margin: {margin:.2f}%.")

        if margin >= 15:
            positive_signals += 1
        elif margin < 0:
            negative_signals += 1
    else:
        limitations.append("Net profit margin is unavailable.")

    if growth is not None:
        evidence.append(f"Revenue growth: {growth:+.2f}%.")

        if growth >= 5:
            positive_signals += 1
        elif growth < 0:
            negative_signals += 1
    else:
        limitations.append("Revenue growth is unavailable.")

    if roe is not None:
        evidence.append(f"Return on equity: {roe:.2f}%.")

        if 0 < roe <= 100:
            positive_signals += 1
        elif roe < 0:
            negative_signals += 1
        elif roe > 100:
            limitations.append(
                "Return on equity exceeds 100%; interpret cautiously "
                "because leverage or a small equity base may distort it."
            )
    else:
        limitations.append("Return on equity is unavailable.")

    if current_ratio is not None:
        evidence.append(f"Current ratio: {current_ratio:.2f}.")

        if current_ratio >= 1.5:
            positive_signals += 1
        elif current_ratio < 1:
            negative_signals += 1
    else:
        limitations.append("Current ratio is unavailable.")

    if pe_ratio is not None:
        evidence.append(f"Trailing P/E ratio: {pe_ratio:.2f}.")

        if pe_ratio <= 0:
            limitations.append(
                "A non-positive P/E ratio is not useful for ordinary "
                "positive-earnings valuation comparisons."
            )
        elif pe_ratio > 40:
            negative_signals += 1
        elif pe_ratio < 25:
            positive_signals += 1
    else:
        limitations.append("Trailing P/E ratio is unavailable.")

    available_metrics = sum(
        value is not None
        for value in (margin, growth, roe, current_ratio, pe_ratio)
    )

    if available_metrics < 3:
        status = "insufficient_data"
        summary = (
            "Too few fundamental metrics are available for a defensible "
            "directional assessment."
        )
    elif positive_signals > negative_signals:
        status = "bullish"
        summary = (
            "More available fundamental indicators meet the configured "
            "positive criteria than the negative criteria."
        )
    elif negative_signals > positive_signals:
        status = "bearish"
        summary = (
            "More available fundamental indicators meet the configured "
            "negative criteria than the positive criteria."
        )
    else:
        status = "neutral"
        summary = (
            "The available fundamental indicators do not produce a "
            "dominant direction under the configured rules."
        )

    if status == "insufficient_data":
        confidence = 0.0
    elif status == "neutral":
        confidence = round(0.5 * available_metrics / 5, 2)
    else:
        confidence = round(
            max(positive_signals, negative_signals) / available_metrics,
            2,
        )

    limitations.append(
        "These thresholds are transparent prototype heuristics, not a "
        "validated investment strategy. Valuation depends on sector, "
        "business model, and growth expectations."
    )

    return AgentAssessment(
        agent_name="Fundamental Agent",
        status=status,
        summary=summary,
        evidence=evidence,
        limitations=limitations,
        source=metrics.source,
        is_demo=metrics.is_demo,
        confidence=confidence,
        confidence_method=(
            "Heuristic rule concordance: dominant configured positive/negative "
            "checks divided by available metrics; neutral confidence is half "
            "the available-metric coverage. This is not a calibrated probability."
        ),
    )



