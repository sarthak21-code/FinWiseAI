import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from app.schemas.intelligence import AgentAssessment
from app.schemas.news import NewsArticleSummary, NewsSentimentResult
from app.schemas.technical import TechnicalAnalysis
from app.services import intelligence
from app.services.fundamental_analysis import FundamentalDataUnavailable
from app.services import evaluation


def make_assessment(
    agent_name: str,
    status: str,
    is_demo: bool = False,
) -> AgentAssessment:
    return AgentAssessment(
        agent_name=agent_name,
        status=status,
        summary=f"{agent_name} assessment is {status}.",
        evidence=["Deterministic test evidence."],
        limitations=[],
        source="Test source",
        is_demo=is_demo,
    )


def make_technical_result(status: str = "bullish"):
    if status == "invalid":
        return SimpleNamespace(
            symbol="TEST",
            technical_bias=status,
            is_demo=False,
            source="Test market data",
            evidence=["Malformed technical fixture."],
        )
    return TechnicalAnalysis(
        symbol="TEST",
        latest_close=100.0,
        latest_trading_day="2026-10-14",
        calculated_at_utc=datetime.now(timezone.utc),
        sma_20=98.0,
        sma_50=95.0,
        rsi_14=60.0,
        momentum_20d_percent=5.0,
        daily_volatility_percent=1.2,
        technical_bias=status,
        evidence=["Test technical indicator evidence."],
        source="Test market data",
        is_demo=False,
        data_note="Deterministic test fixture.",
    )


def make_news_result(status: str = "insufficient_data"):
    sentiment_score = {"bullish": 0.5, "bearish": -0.5, "neutral": 0.0}.get(status)
    articles = (
        [
            NewsArticleSummary(
                title="Deterministic TEST fixture headline",
                published_at_utc=datetime.now(timezone.utc),
                sentiment_score=sentiment_score,
                sentiment_label="positive" if status == "bullish" else "negative" if status == "bearish" else "neutral",
                relevance_score=0.9,
                related_tickers=["TEST"],
            )
        ]
        if sentiment_score is not None
        else []
    )

    return SimpleNamespace(
        symbol="TEST",
        status=status,
        summary=f"News assessment is {status}.",
        evidence=["Test news evidence"],
        limitations=["Synthetic test fixture; not real market data"],
        source="Test fixture",
        is_demo=False,
        data_warnings=[],
        sentiment_score=sentiment_score,
        fetched_at_utc=datetime.now(timezone.utc),
        articles=articles,
    )


async def run_analysis(
    monkeypatch,
    technical_status: str,
    fundamental_status: str,
    news_status: str,
    agent_error: str | None = None,
    persistence_spy: dict[str, list[dict]] | None = None,
    synthetic_technical: bool = False,
):
    technical_result = make_technical_result(technical_status)
    technical_result.is_demo = synthetic_technical
    news_result = make_news_result(news_status)

    monkeypatch.setattr(
        intelligence,
        "get_technical_analysis",
        AsyncMock(return_value=technical_result),
    )
    monkeypatch.setattr(
        intelligence,
        "fetch_fundamental_metrics",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        intelligence,
        "interpret_fundamentals",
        lambda _: make_assessment(
            "Fundamental Agent",
            fundamental_status,
        ),
    )
    monkeypatch.setattr(
        intelligence,
        "analyze_news_sentiment",
        AsyncMock(return_value=news_result),
    )
    monkeypatch.setattr(
        intelligence,
        "get_historical_prices",
        AsyncMock(return_value=SimpleNamespace(bars=())),
    )
    if agent_error == "technical":
        monkeypatch.setattr(
            intelligence,
            "get_technical_analysis",
            AsyncMock(side_effect=RuntimeError("technical fixture failure")),
        )
    elif agent_error == "fundamental":
        monkeypatch.setattr(
            intelligence,
            "fetch_fundamental_metrics",
            AsyncMock(side_effect=RuntimeError("fundamental fixture failure")),
        )
    elif agent_error == "news":
        monkeypatch.setattr(
            intelligence,
            "analyze_news_sentiment",
            AsyncMock(side_effect=RuntimeError("news fixture failure")),
        )
    monkeypatch.setattr(intelligence, "ground_agent_claims", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        evaluation,
        "record_analysis_session",
        lambda **kwargs: persistence_spy["sessions"].append(kwargs)
        if persistence_spy is not None
        else None,
    )
    monkeypatch.setattr(
        evaluation,
        "record_signal_evaluation",
        lambda **kwargs: persistence_spy["evaluations"].append(kwargs)
        if persistence_spy is not None
        else None,
    )

    return await intelligence.analyze_symbol("TEST", db=object())


def test_opposing_agents_produce_neutral_overall_status(monkeypatch):
    result = asyncio.run(run_analysis(
        monkeypatch,
        technical_status="bullish",
        fundamental_status="bearish",
        news_status="insufficient_data",
    ))

    assert result.overall_status == "neutral"
    assert len(result.disagreements) == 1
    assert "conflict" in result.analysis_note.lower()
    assert "bullish" in result.analysis_note.lower()
    assert "bearish" in result.analysis_note.lower()


def test_two_bullish_agents_and_insufficient_news_give_partial_support(
    monkeypatch,
):
    result = asyncio.run(run_analysis(
        monkeypatch,
        technical_status="bullish",
        fundamental_status="bullish",
        news_status="insufficient_data",
    ))

    assert result.overall_status == "bullish"
    assert result.disagreements == []
    assert "partial support" in result.analysis_note.lower()
    assert "news sentiment agent" in result.analysis_note.lower()
    assert result.analysis_completeness == "partial"


def test_one_directional_agent_and_one_neutral_agent_are_not_confirmed(
    monkeypatch,
):
    result = asyncio.run(run_analysis(
        monkeypatch,
        technical_status="bullish",
        fundamental_status="neutral",
        news_status="insufficient_data",
    ))

    assert result.overall_status == "neutral"
    assert result.disagreements == []
    assert "multi-agent confirmation" in result.analysis_note.lower()


def test_all_agents_without_direction_return_insufficient_data(
    monkeypatch,
):
    result = asyncio.run(run_analysis(
        monkeypatch,
        technical_status="insufficient_data",
        fundamental_status="unavailable",
        news_status="insufficient_data",
    ))

    assert result.overall_status == "insufficient_data"
    assert result.disagreements == []
    assert result.analysis_completeness == "partial"


def test_all_directional_agents_agree_without_caveats(monkeypatch):
    result = asyncio.run(run_analysis(
        monkeypatch,
        technical_status="bullish",
        fundamental_status="bullish",
        news_status="bullish",
    ))

    assert result.overall_status == "bullish"
    assert result.disagreements == []
    assert "all available agent assessments" in result.analysis_note.lower()
    assert result.analysis_completeness == "complete"


@pytest.mark.parametrize(
    ("failed_agent", "expected_failed_name"),
    [
        ("technical", "Technical Agent"),
        ("fundamental", "Fundamental Agent"),
        ("news", "News Sentiment Agent"),
    ],
)
def test_each_agent_failure_preserves_the_other_two_results(
    monkeypatch,
    failed_agent,
    expected_failed_name,
):
    result = asyncio.run(
        run_analysis(
            monkeypatch,
            technical_status="bullish",
            fundamental_status="bullish",
            news_status="bullish",
            agent_error=failed_agent,
        )
    )

    assessments = {assessment.agent_name: assessment for assessment in result.assessments}
    assert assessments[expected_failed_name].status == "unavailable"
    assert assessments[expected_failed_name].confidence == 0.0
    assert sum(a.status == "bullish" for a in assessments.values()) == 2
    assert "partial support" in result.analysis_note.lower()
    assert result.analysis_completeness == "partial"
    assert any(
        "unavailable" in warning.lower() or "could not complete" in warning.lower()
        for warning in result.data_warnings
    )


def test_fundamental_provider_unavailable_recorded_gracefully(monkeypatch):
    """When fundamental provider raises FundamentalDataUnavailable, intelligence gracefully records it as unavailable."""
    from unittest.mock import AsyncMock
    from app.services.fundamental_analysis import FundamentalDataUnavailable
    from app.services import intelligence
    from app.schemas.technical import TechnicalAnalysis

    fake_technical = TechnicalAnalysis(
        symbol="XYZ",
        latest_close=100.0,
        latest_trading_day="2026-10-13",
        calculated_at_utc=datetime.now(timezone.utc),
        sma_20=98.0,
        sma_50=95.0,
        rsi_14=60.0,
        momentum_20d_percent=5.0,
        daily_volatility_percent=1.2,
        technical_bias="bullish",
        evidence=["Price is above SMA 20."],
        source="Test Provider",
        is_demo=False,
        data_note="Test observation.",
    )

    news_result = NewsSentimentResult(
        symbol="XYZ",
        status="neutral",
        summary="Neutral news.",
        source="Test News",
        fetched_at_utc=datetime.now(timezone.utc),
        sentiment_score=0.0,
        articles=[],
        data_warnings=[],
        is_demo=False,
    )

    monkeypatch.setattr(intelligence, "get_technical_analysis", AsyncMock(return_value=fake_technical))
    monkeypatch.setattr(
        intelligence,
        "get_historical_prices",
        AsyncMock(return_value=SimpleNamespace(bars=())),
    )
    monkeypatch.setattr(intelligence, "ground_agent_claims", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(evaluation, "record_analysis_session", lambda **_kwargs: None)
    monkeypatch.setattr(evaluation, "record_signal_evaluation", lambda **_kwargs: None)
    monkeypatch.setattr(
        intelligence,
        "fetch_fundamental_metrics",
        AsyncMock(side_effect=FundamentalDataUnavailable("No company overview is available for XYZ.")),
    )
    monkeypatch.setattr(intelligence, "analyze_news_sentiment", AsyncMock(return_value=news_result))

    result = asyncio.run(intelligence.analyze_symbol("XYZ", db=object()))
    assert result.symbol == "XYZ"
    fund_agent = next((a for a in result.assessments if a.agent_name == "Fundamental Agent"), None)
    assert fund_agent is not None
    assert fund_agent.status == "unavailable"
    assert "unavailable" in result.data_warnings[0].lower()


def test_analysis_session_and_evaluation_share_response_session_id(monkeypatch):
    from types import SimpleNamespace

    from app.services import evaluation

    technical = TechnicalAnalysis(
        symbol="TEST",
        latest_close=100.0,
        latest_trading_day="2026-10-14",
        calculated_at_utc=datetime.now(timezone.utc),
        sma_20=98.0,
        sma_50=95.0,
        rsi_14=60.0,
        momentum_20d_percent=5.0,
        daily_volatility_percent=1.2,
        technical_bias="bullish",
        evidence=["Price is above SMA 20."],
        source="Test Provider",
        is_demo=False,
        data_note="Test observation.",
    )
    persisted: dict[str, dict] = {}

    monkeypatch.setattr(
        intelligence,
        "get_technical_analysis",
        AsyncMock(return_value=technical),
    )
    monkeypatch.setattr(
        intelligence,
        "fetch_fundamental_metrics",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        intelligence,
        "interpret_fundamentals",
        lambda _: make_assessment("Fundamental Agent", "bullish"),
    )
    monkeypatch.setattr(
        intelligence,
        "analyze_news_sentiment",
        AsyncMock(return_value=make_news_result("bullish")),
    )
    monkeypatch.setattr(
        intelligence,
        "get_historical_prices",
        AsyncMock(return_value=SimpleNamespace(bars=())),
    )
    monkeypatch.setattr(intelligence, "ground_agent_claims", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        evaluation,
        "record_analysis_session",
        lambda **kwargs: persisted.setdefault("session", kwargs),
    )
    monkeypatch.setattr(
        evaluation,
        "record_signal_evaluation",
        lambda **kwargs: persisted.setdefault("evaluation", kwargs),
    )

    result = asyncio.run(intelligence.analyze_symbol("TEST", db=object()))

    assert persisted["session"]["session_id"] == result.session_id
    assert persisted["evaluation"]["session_id"] == result.session_id
    assert result.analysis_completeness == "complete"


def test_partial_analysis_is_persisted_without_accuracy_evaluation(monkeypatch):
    persistence_spy: dict[str, list[dict]] = {"sessions": [], "evaluations": []}

    result = asyncio.run(
        run_analysis(
            monkeypatch,
            technical_status="bullish",
            fundamental_status="bullish",
            news_status="insufficient_data",
            persistence_spy=persistence_spy,
        )
    )

    assert result.analysis_completeness == "partial"
    assert len(persistence_spy["sessions"]) == 1
    assert persistence_spy["sessions"][0]["session_id"] == result.session_id
    assert persistence_spy["evaluations"] == []


def test_synthetic_analysis_is_not_added_to_real_accuracy_evaluation(monkeypatch):
    persistence_spy: dict[str, list[dict]] = {"sessions": [], "evaluations": []}

    result = asyncio.run(
        run_analysis(
            monkeypatch,
            technical_status="bullish",
            fundamental_status="bullish",
            news_status="bullish",
            persistence_spy=persistence_spy,
            synthetic_technical=True,
        )
    )

    assert result.analysis_completeness == "partial"
    assert persistence_spy["sessions"]
    assert persistence_spy["evaluations"] == []


def test_three_agent_services_start_concurrently(monkeypatch):
    from app.schemas.fundamental import FundamentalMetrics

    started: set[str] = set()
    all_started = asyncio.Event()
    technical = make_technical_result("bullish")
    fundamentals = FundamentalMetrics(
        symbol="TEST",
        revenue_growth_percent=12.0,
        net_margin_percent=18.0,
        return_on_equity_percent=22.0,
        pe_ratio=20.0,
        source="Deterministic test fixture",
        fetched_at_utc=datetime.now(timezone.utc),
    )

    async def release_when_all_started(name: str, result):
        started.add(name)
        if len(started) == 3:
            all_started.set()
        await asyncio.wait_for(all_started.wait(), timeout=0.5)
        return result

    async def tech_call(_symbol):
        return await release_when_all_started("technical", technical)

    async def fund_call(_symbol):
        return await release_when_all_started("fundamental", fundamentals)

    async def news_call(_symbol):
        return await release_when_all_started("news", make_news_result("bullish"))

    monkeypatch.setattr(intelligence, "get_technical_analysis", tech_call)
    monkeypatch.setattr(intelligence, "fetch_fundamental_metrics", fund_call)
    monkeypatch.setattr(intelligence, "analyze_news_sentiment", news_call)
    monkeypatch.setattr(
        intelligence,
        "get_historical_prices",
        AsyncMock(return_value=SimpleNamespace(bars=())),
    )
    monkeypatch.setattr(evaluation, "record_analysis_session", lambda **_kwargs: None)
    monkeypatch.setattr(evaluation, "record_signal_evaluation", lambda **_kwargs: None)
    monkeypatch.setattr(intelligence, "ground_agent_claims", lambda *_args, **_kwargs: [])

    result = asyncio.run(intelligence.analyze_symbol("TEST", db=object()))

    assert started == {"technical", "fundamental", "news"}
    assert len(result.assessments) == 3
    statuses = {assessment.agent_name: assessment.status for assessment in result.assessments}
    assert statuses == {
        "Technical Agent": "bullish",
        "Fundamental Agent": "bullish",
        "News Sentiment Agent": "bullish",
    }
    assert all(assessment.latency_ms >= 0 for assessment in result.assessments)
    assert all(assessment.confidence_method for assessment in result.assessments)
    assert result.analysis_completeness == "complete"


def test_technical_and_news_failures_leave_explicit_partial_analysis(monkeypatch):
    from app.schemas.fundamental import FundamentalMetrics

    fundamentals = FundamentalMetrics(
        symbol="TEST",
        revenue_growth_percent=12.0,
        net_margin_percent=18.0,
        return_on_equity_percent=22.0,
        pe_ratio=20.0,
        source="Deterministic test fixture",
        fetched_at_utc=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        intelligence,
        "get_technical_analysis",
        AsyncMock(side_effect=RuntimeError("private provider detail")),
    )
    monkeypatch.setattr(
        intelligence,
        "fetch_fundamental_metrics",
        AsyncMock(return_value=fundamentals),
    )
    monkeypatch.setattr(
        intelligence,
        "analyze_news_sentiment",
        AsyncMock(side_effect=RuntimeError("private news provider detail")),
    )
    monkeypatch.setattr(
        intelligence,
        "get_historical_prices",
        AsyncMock(return_value=SimpleNamespace(bars=())),
    )
    monkeypatch.setattr(evaluation, "record_analysis_session", lambda **_kwargs: None)
    monkeypatch.setattr(evaluation, "record_signal_evaluation", lambda **_kwargs: None)
    monkeypatch.setattr(intelligence, "ground_agent_claims", lambda *_args, **_kwargs: [])

    result = asyncio.run(intelligence.analyze_symbol("TEST", db=object()))
    statuses = {assessment.agent_name: assessment.status for assessment in result.assessments}

    assert statuses["Technical Agent"] == "unavailable"
    assert statuses["News Sentiment Agent"] == "unavailable"
    assert statuses["Fundamental Agent"] != "unavailable"
    assert "private provider detail" not in " ".join(result.data_warnings)
    assert "private news provider detail" not in " ".join(result.data_warnings)
    signal_statuses = {signal.dimension.value: signal.classification.value for signal in result.signals}
    assert signal_statuses["price_momentum"] == "unavailable"
    assert signal_statuses["news_sentiment"] == "unavailable"


def test_empty_rag_results_report_zero_lexical_coverage(monkeypatch):
    result = asyncio.run(run_analysis(
        monkeypatch,
        technical_status="bullish",
        fundamental_status="bullish",
        news_status="insufficient_data",
    ))

    assert result.evidence_claims_count > 0
    assert result.evidence_cited_claims_count == 0
    assert result.evidence_coverage_percent == 0.0
    assert result.citations == []
    assert any("no relevant passages" in warning.lower() for warning in result.data_warnings)


def test_all_three_agents_failing_returns_explicit_unavailable_results(monkeypatch):
    monkeypatch.setattr(
        intelligence,
        "get_technical_analysis",
        AsyncMock(side_effect=RuntimeError("technical fixture failure")),
    )
    monkeypatch.setattr(
        intelligence,
        "fetch_fundamental_metrics",
        AsyncMock(side_effect=RuntimeError("fundamental fixture failure")),
    )
    monkeypatch.setattr(
        intelligence,
        "analyze_news_sentiment",
        AsyncMock(side_effect=RuntimeError("news fixture failure")),
    )
    monkeypatch.setattr(
        intelligence,
        "get_historical_prices",
        AsyncMock(side_effect=RuntimeError("history fixture failure")),
    )
    monkeypatch.setattr(intelligence, "ground_agent_claims", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(evaluation, "record_analysis_session", lambda **_kwargs: None)
    monkeypatch.setattr(evaluation, "record_signal_evaluation", lambda **_kwargs: None)

    result = asyncio.run(intelligence.analyze_symbol("TEST", db=object()))

    statuses = {assessment.agent_name: assessment.status for assessment in result.assessments}
    assert statuses == {
        "Technical Agent": "unavailable",
        "Fundamental Agent": "unavailable",
        "News Sentiment Agent": "unavailable",
    }
    assert all(assessment.confidence == 0.0 for assessment in result.assessments)
    assert result.overall_status == "insufficient_data"
    assert result.analysis_completeness == "partial"
    assert len(result.data_warnings) >= 3


@pytest.mark.parametrize(
    "malformed_agent",
    ["technical", "fundamental", "news", "news_incomplete"],
)
def test_malformed_agent_output_becomes_unavailable_without_losing_peers(
    monkeypatch,
    malformed_agent,
):
    technical = make_technical_result("invalid" if malformed_agent == "technical" else "bullish")
    if malformed_agent == "news":
        news = SimpleNamespace(status="bullish")
    elif malformed_agent == "news_incomplete":
        news = NewsSentimentResult(
            symbol="TEST",
            status="bullish",
            summary="Malformed fixture has no score or headline evidence.",
            source="Deterministic synthetic test fixture",
            fetched_at_utc=datetime.now(timezone.utc),
            sentiment_score=None,
            articles=[],
        )
    else:
        news = make_news_result("bullish")
    monkeypatch.setattr(intelligence, "get_technical_analysis", AsyncMock(return_value=technical))
    if malformed_agent == "fundamental":
        malformed_fundamentals = SimpleNamespace(
            revenue_growth_percent=90.0,
            net_margin_percent=50.0,
            return_on_equity_percent=40.0,
            current_ratio=2.0,
            pe_ratio=15.0,
        )
        monkeypatch.setattr(
            intelligence,
            "fetch_fundamental_metrics",
            AsyncMock(return_value=malformed_fundamentals),
        )
    else:
        monkeypatch.setattr(intelligence, "fetch_fundamental_metrics", AsyncMock(return_value=object()))
        monkeypatch.setattr(
            intelligence,
            "interpret_fundamentals",
            lambda _: make_assessment("Fundamental Agent", "bullish"),
        )
    monkeypatch.setattr(intelligence, "analyze_news_sentiment", AsyncMock(return_value=news))
    monkeypatch.setattr(
        intelligence,
        "get_historical_prices",
        AsyncMock(return_value=SimpleNamespace(bars=())),
    )
    monkeypatch.setattr(intelligence, "ground_agent_claims", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(evaluation, "record_analysis_session", lambda **_kwargs: None)
    monkeypatch.setattr(evaluation, "record_signal_evaluation", lambda **_kwargs: None)

    result = asyncio.run(intelligence.analyze_symbol("TEST", db=object()))

    statuses = {assessment.agent_name: assessment.status for assessment in result.assessments}
    malformed_name = {
        "technical": "Technical Agent",
        "fundamental": "Fundamental Agent",
        "news": "News Sentiment Agent",
        "news_incomplete": "News Sentiment Agent",
    }[malformed_agent]
    assert statuses[malformed_name] == "unavailable"
    assert all(
        assessment.confidence == 0.0
        for assessment in result.assessments
        if assessment.status == "unavailable"
    )
    assert any("unavailable" in warning.lower() or "could not complete" in warning.lower()
               for warning in result.data_warnings)
    if malformed_agent == "fundamental":
        fundamental_signal = next(
            signal for signal in result.signals
            if signal.dimension.value == "fundamental_health"
        )
        assert fundamental_signal.classification.value == "unavailable"
        assert fundamental_signal.confidence == 0.0
    if malformed_agent == "news_incomplete":
        news_signal = next(
            signal for signal in result.signals
            if signal.dimension.value == "news_sentiment"
        )
        assert news_signal.classification.value == "unavailable"
        assert news_signal.confidence == 0.0

