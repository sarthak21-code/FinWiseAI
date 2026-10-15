from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas.signals import SignalClassification, SignalDimension
from app.schemas.fundamental import FundamentalMetrics
from app.services.signals import (
    classify_fundamental_health_signal,
    classify_news_sentiment_signal,
    classify_price_momentum,
    classify_volume_anomaly,
)
from app.services.fundamental_analysis import interpret_fundamentals


def test_classify_price_momentum_bullish():
    tech = SimpleNamespace(
        symbol="AAPL",
        technical_bias="bullish",
        latest_close=220.0,
        sma_20=210.0,
        sma_50=200.0,
        rsi_14=58.0,
        momentum_20d_percent=5.2,
        daily_volatility_percent=1.4,
        source="Test Provider",
        is_demo=False,
        evidence=["Price is above SMA 20."],
    )
    sig = classify_price_momentum("AAPL", tech)
    assert sig.dimension == SignalDimension.PRICE_MOMENTUM
    assert sig.classification == SignalClassification.BULLISH
    assert sig.confidence >= 0.60
    assert len(sig.evidence) > 0


def test_classify_price_momentum_insufficient_data():
    tech = SimpleNamespace(
        symbol="XYZ",
        technical_bias="insufficient_data",
        source="Test Provider",
        is_demo=False,
    )
    sig = classify_price_momentum("XYZ", tech)
    assert sig.classification == SignalClassification.INSUFFICIENT_DATA
    assert sig.confidence == 0.0


def test_classify_price_momentum_marks_agent_failure_unavailable():
    sig = classify_price_momentum("XYZ", None)
    assert sig.classification == SignalClassification.UNAVAILABLE
    assert sig.data_status == "unavailable"
    assert sig.confidence == 0.0


def test_classify_volume_anomaly_surge_and_normal():
    # 20 bars of normal volume (1M) then 2.5M surge
    bars = [
        SimpleNamespace(open=100.0, high=101.0, low=99.0, close=100.0, volume=1_000_000)
        for _ in range(20)
    ]
    # Surge on up day (+2%)
    bars.append(SimpleNamespace(open=100.0, high=103.0, low=100.0, close=102.0, volume=2_500_000))

    sig = classify_volume_anomaly("AAPL", bars)
    assert sig.dimension == SignalDimension.VOLUME_ANOMALY
    assert sig.classification == SignalClassification.BULLISH
    assert sig.metrics["anomaly_label"] == "SURGE"
    assert sig.metrics["relative_volume"] >= 2.0
    assert any("coincided with an advancing session" in item for item in sig.evidence)
    assert not any("institutional" in item.lower() for item in sig.evidence)


def test_classify_volume_anomaly_does_not_infer_institutional_selling():
    bars = [
        SimpleNamespace(open=100.0, high=101.0, low=99.0, close=100.0, volume=1_000_000)
        for _ in range(20)
    ]
    bars.append(SimpleNamespace(open=100.0, high=100.0, low=97.0, close=98.0, volume=2_500_000))

    sig = classify_volume_anomaly("AAPL", bars)

    assert sig.classification == SignalClassification.BEARISH
    assert any("coincided with a declining session" in item for item in sig.evidence)
    assert not any("institutional" in item.lower() for item in sig.evidence)


def test_classify_volume_anomaly_insufficient_bars():
    bars = [SimpleNamespace(close=100.0, volume=1000)]
    sig = classify_volume_anomaly("AAPL", bars)
    assert sig.classification == SignalClassification.INSUFFICIENT_DATA
    assert sig.confidence == 0.0


def test_classify_fundamental_health_signal():
    fund = SimpleNamespace(
        quarterly_revenue_growth_yoy=0.15,
        profit_margin=0.22,
        return_on_equity_ttm=0.30,
        trailing_pe=28.0,
        source="SEC EDGAR",
    )
    sig = classify_fundamental_health_signal("AAPL", fund)
    assert sig.dimension == SignalDimension.FUNDAMENTAL_HEALTH
    assert sig.classification == SignalClassification.BULLISH
    assert sig.confidence > 0.50


def test_classify_fundamental_health_uses_provider_metric_fields():
    fund = FundamentalMetrics(
        symbol="AAPL",
        revenue_growth_percent=16.4,
        net_margin_percent=27.62,
        return_on_equity_percent=148.75,
        pe_ratio=39.33,
        source="Yahoo Finance via yfinance",
        fetched_at_utc=datetime.now(timezone.utc),
    )

    signal = classify_fundamental_health_signal("AAPL", fund)

    assert signal.classification == SignalClassification.BULLISH
    assert signal.confidence > 0.50
    assert "0 positive vs 0 negative" not in signal.confidence_method
    assert len(signal.evidence) == 3


def test_fundamental_agent_reports_heuristic_confidence_and_method():
    metrics = FundamentalMetrics(
        symbol="AAPL",
        revenue_growth_percent=18.0,
        net_margin_percent=22.0,
        return_on_equity_percent=24.0,
        current_ratio=1.8,
        pe_ratio=20.0,
        source="Test provider",
        fetched_at_utc=datetime.now(timezone.utc),
    )
    assessment = interpret_fundamentals(metrics)

    assert assessment.confidence > 0.0
    assert "not a calibrated probability" in assessment.confidence_method.lower()


def test_classify_fundamental_health_unavailable():
    sig = classify_fundamental_health_signal("UNKNOWN", None)
    assert sig.classification == SignalClassification.UNAVAILABLE
    assert sig.confidence == 0.0
