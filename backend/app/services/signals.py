import math
from datetime import datetime, timezone
from typing import Optional

from app.schemas.signals import (
    SignalClassification,
    SignalDimension,
    StructuredSignal,
)


def classify_price_momentum(
    symbol: str,
    technical: any,
) -> StructuredSignal:
    """Classify price momentum and trend from technical analysis."""
    if technical is None:
        return StructuredSignal(
            symbol=symbol,
            dimension=SignalDimension.PRICE_MOMENTUM,
            classification=SignalClassification.UNAVAILABLE,
            confidence=0.0,
            confidence_method="Unavailable because the technical analysis agent did not return a result.",
            source="Unavailable",
            evidence=[],
            limitations=["Technical provider or calculation failed; no price-momentum evidence is available."],
            data_status="unavailable",
            metrics={},
        )

    if technical.technical_bias == "insufficient_data":
        return StructuredSignal(
            symbol=symbol,
            dimension=SignalDimension.PRICE_MOMENTUM,
            classification=SignalClassification.INSUFFICIENT_DATA,
            confidence=0.0,
            confidence_method="Zero confidence due to insufficient historical observations (<20 bars).",
            source=getattr(technical, "source", "Unknown"),
            evidence=["Insufficient historical price observations to compute momentum or trend indicators."],
            limitations=["Minimum 20 trading days required for SMA 20 and momentum lookback."],
            data_status="insufficient_data",
            metrics={},
        )

    latest_close = getattr(technical, "latest_close", None)
    sma_20 = getattr(technical, "sma_20", None)
    sma_50 = getattr(technical, "sma_50", None)
    rsi = getattr(technical, "rsi_14", None)
    mom = getattr(technical, "momentum_20d_percent", None)

    if latest_close is None:
        # Fall back to technical_bias directly if full indicators were mocked
        bias = getattr(technical, "technical_bias", "neutral")
        cls_map = {
            "bullish": SignalClassification.BULLISH,
            "bearish": SignalClassification.BEARISH,
            "neutral": SignalClassification.NEUTRAL,
        }
        cls_val = cls_map.get(bias, SignalClassification.INSUFFICIENT_DATA)
        return StructuredSignal(
            symbol=symbol,
            dimension=SignalDimension.PRICE_MOMENTUM,
            classification=cls_val,
            confidence=0.75 if cls_val in (SignalClassification.BULLISH, SignalClassification.BEARISH) else 0.50,
            confidence_method=f"Derived from validated technical bias '{bias}'.",
            source=getattr(technical, "source", "Historical Market Data"),
            evidence=list(getattr(technical, "evidence", [])),
            limitations=["Historical indicator observations were not fully serialized."],
            data_status="demo" if getattr(technical, "is_demo", False) else "valid",
            metrics={},
        )

    evidence: list[str] = []
    bull_points = 0
    bear_points = 0
    total_checks = 0

    if sma_20 is not None:
        total_checks += 1
        if latest_close > sma_20:
            evidence.append(f"Price (${latest_close:.2f}) is above 20-day SMA (${sma_20:.2f}).")
            bull_points += 1
        else:
            evidence.append(f"Price (${latest_close:.2f}) is below 20-day SMA (${sma_20:.2f}).")
            bear_points += 1

    if sma_50 is not None:
        total_checks += 1
        if latest_close > sma_50:
            evidence.append(f"Price (${latest_close:.2f}) is above 50-day SMA (${sma_50:.2f}).")
            bull_points += 1
        else:
            evidence.append(f"Price (${latest_close:.2f}) is below 50-day SMA (${sma_50:.2f}).")
            bear_points += 1

    if sma_20 is not None and sma_50 is not None:
        total_checks += 1
        if sma_20 > sma_50:
            evidence.append(f"SMA 20 (${sma_20:.2f}) is above SMA 50 (${sma_50:.2f}) - golden trend alignment.")
            bull_points += 1
        else:
            evidence.append(f"SMA 20 (${sma_20:.2f}) is below SMA 50 (${sma_50:.2f}) - death cross/downward trend.")
            bear_points += 1

    if rsi is not None:
        total_checks += 1
        if 45.0 <= rsi <= 70.0:
            evidence.append(f"14-day RSI is healthy at {rsi:.1f} (in bullish expansion zone).")
            bull_points += 1
        elif rsi > 70.0:
            evidence.append(f"14-day RSI is elevated at {rsi:.1f} (overbought threshold).")
            bear_points += 0.5
        elif rsi < 40.0:
            evidence.append(f"14-day RSI is depressed at {rsi:.1f} (bearish momentum zone).")
            bear_points += 1
        else:
            evidence.append(f"14-day RSI is neutral at {rsi:.1f}.")

    if mom is not None:
        total_checks += 1
        if mom > 2.0:
            evidence.append(f"20-day momentum is positive (+{mom:.2f}%).")
            bull_points += 1
        elif mom < -2.0:
            evidence.append(f"20-day momentum is negative ({mom:.2f}%).")
            bear_points += 1

    if total_checks == 0:
        classification = SignalClassification.INSUFFICIENT_DATA
        confidence = 0.0
    elif bull_points >= 3 and bull_points > bear_points:
        classification = SignalClassification.BULLISH
        confidence = round(min(0.90, bull_points / max(1, total_checks)), 2)
    elif bear_points >= 3 and bear_points > bull_points:
        classification = SignalClassification.BEARISH
        confidence = round(min(0.90, bear_points / max(1, total_checks)), 2)
    else:
        classification = SignalClassification.NEUTRAL
        confidence = round(0.50, 2)

    confidence_method = (
        f"Rule-based indicator consensus: {bull_points} bullish vs {bear_points} bearish signals "
        f"across {total_checks} technical checks."
    )

    limitations = [
        "Historical indicators reflect past price action and cannot predict forward regime changes.",
        "Moving averages lag price inflections during high-volatility events.",
    ]
    if technical.is_demo:
        limitations.append("Synthetic demonstration data in use; do not use for live market decisions.")

    return StructuredSignal(
        symbol=symbol,
        dimension=SignalDimension.PRICE_MOMENTUM,
        classification=classification,
        confidence=confidence,
        confidence_method=confidence_method,
        source=technical.source,
        evidence=evidence,
        limitations=limitations,
        data_status="demo" if technical.is_demo else "valid",
        metrics={
            "latest_close": latest_close,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "rsi_14": rsi,
            "momentum_20d_percent": mom,
            "volatility_daily": technical.daily_volatility_percent,
        },
    )


def classify_volume_anomaly(
    symbol: str,
    bars: list[any],
    source: str = "Market Data Feed",
) -> StructuredSignal:
    """Classify volume anomalies and directional volume context."""
    if not bars or len(bars) < 5:
        return StructuredSignal(
            symbol=symbol,
            dimension=SignalDimension.VOLUME_ANOMALY,
            classification=SignalClassification.INSUFFICIENT_DATA,
            confidence=0.0,
            confidence_method="Zero confidence due to insufficient historical volume bars (<5 bars).",
            source=source,
            evidence=["Insufficient historical volume bars to establish a baseline."],
            limitations=["At least 5 volume observations are required to calculate baseline volume."],
            data_status="insufficient_data",
            metrics={},
        )

    # Valid volumes
    volumes = [bar.volume for bar in bars if hasattr(bar, "volume") and bar.volume is not None and bar.volume > 0]
    if len(volumes) < 5:
        return StructuredSignal(
            symbol=symbol,
            dimension=SignalDimension.VOLUME_ANOMALY,
            classification=SignalClassification.INSUFFICIENT_DATA,
            confidence=0.0,
            confidence_method="Zero confidence due to missing or zero volume data from provider.",
            source=source,
            evidence=["Volume data is omitted or zero across available bars."],
            limitations=["Provider does not supply reliable volume figures for this instrument."],
            data_status="unavailable",
            metrics={},
        )

    latest_bar = bars[-1]
    latest_volume = latest_bar.volume or 0
    prev_close = bars[-2].close if len(bars) >= 2 else latest_bar.open
    price_change_pct = ((latest_bar.close - prev_close) / prev_close * 100.0) if prev_close else 0.0

    lookback_window = min(20, len(volumes) - 1)
    if lookback_window >= 1:
        avg_volume = sum(volumes[-(lookback_window + 1):-1]) / lookback_window
    else:
        avg_volume = volumes[0]

    relative_volume = (latest_volume / avg_volume) if avg_volume > 0 else 1.0

    # Classify anomaly level
    if relative_volume >= 2.0:
        anomaly_label = "SURGE"
    elif relative_volume >= 1.3:
        anomaly_label = "ELEVATED"
    elif relative_volume <= 0.7:
        anomaly_label = "LOW"
    else:
        anomaly_label = "NORMAL"

    evidence: list[str] = [
        f"Latest session volume of {latest_volume:,.0f} is {relative_volume:.2f}x the {lookback_window}-day average ({avg_volume:,.0f}).",
        f"Volume activity classified as {anomaly_label}.",
    ]

    # Directional interpretation: high volume co-occurs with the price move;
    # volume alone does not identify the participants or confirm the trend.
    if anomaly_label in ("SURGE", "ELEVATED"):
        if price_change_pct > 0.5:
            classification = SignalClassification.BULLISH
            evidence.append(f"High volume coincided with an advancing session (+{price_change_pct:.2f}%).")
            confidence = min(0.85, 0.50 + (relative_volume - 1.0) * 0.2)
        elif price_change_pct < -0.5:
            classification = SignalClassification.BEARISH
            evidence.append(f"High volume coincided with a declining session ({price_change_pct:.2f}%).")
            confidence = min(0.85, 0.50 + (relative_volume - 1.0) * 0.2)
        else:
            classification = SignalClassification.NEUTRAL
            evidence.append(f"Volume surge occurred with minimal price change ({price_change_pct:+.2f}%), indicating high turnover without directional consensus.")
            confidence = 0.50
    else:
        classification = SignalClassification.NEUTRAL
        evidence.append(f"Session volume is within normal ranges ({relative_volume:.2f}x average), providing no abnormal volume signal.")
        confidence = 0.60

    limitations = [
        "Volume spikes alone do not determine price trend without accompanying price action.",
        "Off-exchange or dark pool volume may not be fully represented in consolidated tape.",
    ]

    confidence_method = (
        f"Relative volume multiplier ({relative_volume:.2f}x) combined with session return ({price_change_pct:+.2f}%)."
    )

    return StructuredSignal(
        symbol=symbol,
        dimension=SignalDimension.VOLUME_ANOMALY,
        classification=classification,
        confidence=round(confidence, 2),
        confidence_method=confidence_method,
        source=source,
        evidence=evidence,
        limitations=limitations,
        data_status="valid",
        metrics={
            "latest_volume": latest_volume,
            "average_volume_20d": avg_volume,
            "relative_volume": round(relative_volume, 2),
            "anomaly_label": anomaly_label,
            "price_change_percent": round(price_change_pct, 2),
        },
    )


def classify_news_sentiment_signal(
    symbol: str,
    news_result: any,
) -> StructuredSignal:
    """Classify sentiment signal from news and event stream."""
    if news_result is None or getattr(news_result, "status", "") == "unavailable":
        return StructuredSignal(
            symbol=symbol,
            dimension=SignalDimension.NEWS_SENTIMENT,
            classification=SignalClassification.UNAVAILABLE,
            confidence=0.0,
            confidence_method="Unavailable because the news analysis agent did not return usable data.",
            source=getattr(news_result, "source", "Unavailable"),
            evidence=[],
            limitations=["News provider or processing failed; no sentiment conclusion was generated."],
            data_status="unavailable",
            metrics={"sentiment_score": None, "article_count": 0},
        )

    if getattr(news_result, "status", "") == "insufficient_data":
        return StructuredSignal(
            symbol=symbol,
            dimension=SignalDimension.NEWS_SENTIMENT,
            classification=SignalClassification.INSUFFICIENT_DATA,
            confidence=0.0,
            confidence_method="Zero confidence due to lack of recent relevant articles.",
            source=getattr(news_result, "source", "News Provider"),
            evidence=["No recent news articles met the relevance threshold for this symbol."],
            limitations=["Sentiment cannot be assessed when recent headlines are unavailable."],
            data_status="insufficient_data",
            metrics={"sentiment_score": 0.0, "article_count": 0},
        )

    score = getattr(news_result, "sentiment_score", 0.0)
    raw_status = getattr(news_result, "status", "neutral")
    articles = getattr(news_result, "articles", [])

    if raw_status == "bullish":
        classification = SignalClassification.BULLISH
    elif raw_status == "bearish":
        classification = SignalClassification.BEARISH
    else:
        classification = SignalClassification.NEUTRAL

    article_count = len(articles)
    evidence = list(getattr(news_result, "evidence", []))
    if not evidence and article_count > 0:
        evidence.append(f"Evaluated {article_count} provider-sourced recent headlines; aggregate sentiment score is {score:+.2f}.")

    # Confidence scales with article count and score separation
    confidence = round(min(0.85, 0.40 + min(article_count, 10) * 0.03 + abs(score) * 0.2), 2)
    confidence_method = (
        f"Lexical sentiment score ({score:+.2f}) scaled across {article_count} provider-sourced relevant headlines."
    )

    limitations = list(getattr(news_result, "limitations", []))
    limitations.append("Lexical sentiment analysis is a heuristic approach and does not capture nuanced corporate nuance.")

    return StructuredSignal(
        symbol=symbol,
        dimension=SignalDimension.NEWS_SENTIMENT,
        classification=classification,
        confidence=confidence,
        confidence_method=confidence_method,
        source=getattr(news_result, "source", "News Aggregator"),
        evidence=evidence,
        limitations=limitations,
        data_status="valid" if not getattr(news_result, "is_demo", False) else "demo",
        metrics={
            "sentiment_score": score,
            "article_count": article_count,
        },
    )


def classify_fundamental_health_signal(
    symbol: str,
    fundamental_metrics: any,
) -> StructuredSignal:
    """Classify fundamental financial health from company statement metrics."""
    if fundamental_metrics is None:
        return StructuredSignal(
            symbol=symbol,
            dimension=SignalDimension.FUNDAMENTAL_HEALTH,
            classification=SignalClassification.UNAVAILABLE,
            confidence=0.0,
            confidence_method="Zero confidence due to unavailable fundamental disclosures.",
            source="Unavailable",
            evidence=["Company financial disclosures were not returned by the configured provider."],
            limitations=["Fundamental evaluation requires verified financial filings."],
            data_status="unavailable",
            metrics={},
        )

    evidence: list[str] = []
    bull_pts = 0
    bear_pts = 0
    checks = 0

    rev_growth = getattr(fundamental_metrics, "quarterly_revenue_growth_yoy", None)
    rev_growth_percent = getattr(
        fundamental_metrics,
        "revenue_growth_percent",
        None,
    )
    if rev_growth is not None:
        checks += 1
        growth_pct = rev_growth * 100.0 if abs(rev_growth) < 5 else rev_growth
        if growth_pct > 10.0:
            bull_pts += 1
            evidence.append(f"Strong quarterly YoY revenue growth (+{growth_pct:.1f}%).")
        elif growth_pct < 0.0:
            bear_pts += 1
            evidence.append(f"Contracting quarterly YoY revenue ({growth_pct:.1f}%).")
        else:
            evidence.append(f"Modest quarterly YoY revenue growth (+{growth_pct:.1f}%).")
    elif rev_growth_percent is not None:
        checks += 1
        growth_pct = rev_growth_percent
        if growth_pct > 10.0:
            bull_pts += 1
            evidence.append(f"Strong provider-reported revenue growth (+{growth_pct:.1f}%).")
        elif growth_pct < 0.0:
            bear_pts += 1
            evidence.append(f"Contracting provider-reported revenue ({growth_pct:.1f}%).")
        else:
            evidence.append(f"Modest provider-reported revenue growth (+{growth_pct:.1f}%).")

    profit_margin = getattr(fundamental_metrics, "profit_margin", None)
    net_margin_percent = getattr(
        fundamental_metrics,
        "net_margin_percent",
        None,
    )
    if profit_margin is not None:
        checks += 1
        pm_pct = profit_margin * 100.0 if abs(profit_margin) < 5 else profit_margin
        if pm_pct > 15.0:
            bull_pts += 1
            evidence.append(f"Robust net profit margin ({pm_pct:.1f}%).")
        elif pm_pct < 0.0:
            bear_pts += 1
            evidence.append(f"Negative net profit margin ({pm_pct:.1f}%), company operating at a loss.")
        else:
            evidence.append(f"Healthy net profit margin ({pm_pct:.1f}%).")
    elif net_margin_percent is not None:
        checks += 1
        pm_pct = net_margin_percent
        if pm_pct > 15.0:
            bull_pts += 1
            evidence.append(f"Robust provider-reported net profit margin ({pm_pct:.1f}%).")
        elif pm_pct < 0.0:
            bear_pts += 1
            evidence.append(f"Negative net profit margin ({pm_pct:.1f}%), company operating at a loss.")
        else:
            evidence.append(f"Healthy net profit margin ({pm_pct:.1f}%).")

    roe = getattr(fundamental_metrics, "return_on_equity_ttm", None)
    return_on_equity_percent = getattr(
        fundamental_metrics,
        "return_on_equity_percent",
        None,
    )
    if roe is not None:
        checks += 1
        roe_pct = roe * 100.0 if abs(roe) < 5 else roe
        if roe_pct > 15.0:
            bull_pts += 1
            evidence.append(f"High Return on Equity ({roe_pct:.1f}% TTM).")
        elif roe_pct < 0.0:
            bear_pts += 1
            evidence.append(f"Negative Return on Equity ({roe_pct:.1f}% TTM).")
    elif return_on_equity_percent is not None:
        checks += 1
        roe_pct = return_on_equity_percent
        if roe_pct > 15.0:
            bull_pts += 1
            evidence.append(f"High provider-reported Return on Equity ({roe_pct:.1f}%).")
        elif roe_pct < 0.0:
            bear_pts += 1
            evidence.append(f"Negative Return on Equity ({roe_pct:.1f}%).")

    pe = getattr(fundamental_metrics, "trailing_pe", None)
    pe_ratio = getattr(fundamental_metrics, "pe_ratio", None)
    if pe is None:
        pe = pe_ratio
    if pe is not None and pe > 0:
        checks += 1
        if pe < 25.0:
            bull_pts += 0.5
            evidence.append(f"Reasonable trailing P/E multiple ({pe:.1f}x).")
        elif pe > 60.0:
            bear_pts += 0.5
            evidence.append(f"Rich valuation with elevated trailing P/E multiple ({pe:.1f}x).")

    if checks == 0:
        classification = SignalClassification.INSUFFICIENT_DATA
        confidence = 0.0
    elif bull_pts >= 2 and bull_pts > bear_pts:
        classification = SignalClassification.BULLISH
        confidence = round(min(0.85, 0.50 + bull_pts * 0.1), 2)
    elif bear_pts >= 2 and bear_pts > bull_pts:
        classification = SignalClassification.BEARISH
        confidence = round(min(0.85, 0.50 + bear_pts * 0.1), 2)
    else:
        classification = SignalClassification.NEUTRAL
        confidence = 0.50

    confidence_method = (
        f"Financial ratio balance: {bull_pts} positive vs {bear_pts} negative checks "
        f"across {checks} reported metrics."
    )

    limitations = [
        "Fundamental metrics are backward-looking and use the reporting periods supplied by the data provider.",
        "Accounting policies and one-off non-operating charges can distort GAAP valuation ratios.",
    ]

    return StructuredSignal(
        symbol=symbol,
        dimension=SignalDimension.FUNDAMENTAL_HEALTH,
        classification=classification,
        confidence=confidence,
        confidence_method=confidence_method,
        source=getattr(fundamental_metrics, "source", "Fundamental Data Provider"),
        evidence=evidence,
        limitations=limitations,
        data_status="valid",
        metrics={
            "quarterly_revenue_growth_yoy": rev_growth,
            "profit_margin": profit_margin,
            "return_on_equity_ttm": roe,
            "trailing_pe": pe,
        },
    )
