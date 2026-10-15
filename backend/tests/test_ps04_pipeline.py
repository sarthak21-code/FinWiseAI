import asyncio
import json
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register every ORM table with Base
from app.db.session import Base
from app.models.evaluation import SignalEvaluation
from app.models.session import AnalysisSession
from app.schemas.fundamental import FundamentalMetrics
from app.schemas.news import NewsArticleSummary, NewsSentimentResult
from app.services import intelligence, technical_analysis
from app.services.evaluation import get_evaluation_metrics
from app.services.historical_prices import (
    HistoricalBar,
    HistoricalPriceHistory,
)
from app.services.investors import seed_default_investor_profiles
from app.services.rag import seed_demonstration_corpus


def test_reproducible_ps04_pipeline_to_persisted_response(monkeypatch):
    """Exercise fixture market input through RAG, agents, personalization and persistence without network or file DB."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    technical_analysis.clear_technical_cache()

    try:
        profiles = seed_default_investor_profiles(db)
        seed_demonstration_corpus(db)
        conservative = next(
            profile for profile in profiles
            if profile.id == "demo_profile_conservative"
        )

        dates = pd.bdate_range(end="2026-10-14", periods=70)
        bars = tuple(
            HistoricalBar(
                trading_day=day.date().isoformat(),
                open=100.0 + index * 0.5,
                high=101.0 + index * 0.5,
                low=99.0 + index * 0.5,
                close=100.0 + index * 0.5,
                volume=1_000_000 if index < 69 else 1_500_000,
            )
            for index, day in enumerate(dates)
        )
        fixture_history = HistoricalPriceHistory(
            symbol="MSFT",
            bars=bars,
            source="Deterministic isolated test fixture",
            fetched_at_utc=datetime.now(timezone.utc),
            data_note="Deterministic prices for a test only; not market data.",
        )

        async def history_for_fixture(_symbol):
            return fixture_history

        async def fundamentals_for_fixture(_symbol):
            return FundamentalMetrics(
                symbol="MSFT",
                revenue_growth_percent=18.0,
                net_margin_percent=22.0,
                return_on_equity_percent=28.0,
                current_ratio=1.7,
                pe_ratio=32.0,
                source="Deterministic isolated test fixture",
                fetched_at_utc=datetime.now(timezone.utc),
                data_warnings=["Test fixture; not provider data."],
            )

        async def news_for_fixture(_symbol):
            return NewsSentimentResult(
                symbol="MSFT",
                status="bullish",
                summary="A fixture claim deliberately contradicting retrieved context.",
                evidence=["Azure cloud revenue collapsed after enterprise migration stopped."],
                limitations=["Deterministic fixture, not actual news."],
                source="Deterministic isolated test fixture",
                fetched_at_utc=datetime.now(timezone.utc),
                sentiment_score=0.55,
                articles=[
                    NewsArticleSummary(
                        title="Azure cloud revenue collapsed after enterprise migration stopped.",
                        publisher="Synthetic test fixture",
                        published_at_utc=datetime.now(timezone.utc),
                        sentiment_score=0.55,
                        sentiment_label="positive",
                        relevance_score=0.9,
                        related_tickers=["MSFT"],
                    )
                ],
                data_warnings=["Test fixture; not provider news."],
            )

        monkeypatch.setattr(technical_analysis, "get_historical_prices", history_for_fixture)
        monkeypatch.setattr(intelligence, "get_historical_prices", history_for_fixture)
        monkeypatch.setattr(intelligence, "fetch_fundamental_metrics", fundamentals_for_fixture)
        monkeypatch.setattr(intelligence, "analyze_news_sentiment", news_for_fixture)

        response = asyncio.run(
            intelligence.analyze_symbol(
                "MSFT",
                profile_id=conservative.id,
                db=db,
            )
        )

        assert response.symbol == "MSFT"
        assert response.session_id
        assert {signal.dimension.value for signal in response.signals} == {
            "price_momentum",
            "volume_anomaly",
            "news_sentiment",
            "fundamental_health",
        }
        assert {assessment.agent_name for assessment in response.assessments} == {
            "Technical Agent",
            "Fundamental Agent",
            "News Sentiment Agent",
        }
        assert response.personalized_interpretation is not None
        assert response.personalized_interpretation.profile_id == conservative.id
        assert response.citations
        assert all(citation.synthetic for citation in response.citations)
        assert all(citation.document_id and citation.chunk_id for citation in response.citations)
        # The claim remains in the synthesized response despite conflicting lexical context.
        # This is an explicit regression guard: retrieval has not verified support.
        assert any(
            "collapsed after enterprise migration stopped" in citation.claim
            and citation.claim_type == "context"
            for citation in response.citations
        )
        assert 0 < response.evidence_coverage_percent <= 100
        assert response.evidence_cited_claims_count <= response.evidence_claims_count

        saved_session = db.get(AnalysisSession, response.session_id)
        assert saved_session is not None
        assert saved_session.total_latency_ms >= 0
        assert saved_session.rag_latency_ms >= 0
        stored_agents = json.loads(saved_session.agents_data)
        assert all(agent["latency_ms"] >= 0 for agent in stored_agents)
        stored_rag_step = next(
            step for step in json.loads(saved_session.reasoning_trace)
            if step["title"] == "Financial Document Retrieval (RAG)"
        )
        assert stored_rag_step["metadata"]["evidence_coverage_percent"] == response.evidence_coverage_percent
        assert stored_rag_step["metadata"]["evidence_coverage_definition"]

        evaluation = db.execute(
            select(SignalEvaluation).where(
                SignalEvaluation.session_id == response.session_id
            )
        ).scalar_one()
        assert evaluation.outcome == "pending_window"
        assert evaluation.is_synthetic is False

        metrics = get_evaluation_metrics(db)
        assert metrics["total_sessions"] == 1
        assert metrics["pending_windows_count"] == 1
        assert metrics["completed_windows_count"] == 0
        assert db.execute(select(func.count(AnalysisSession.id))).scalar_one() == 1
    finally:
        technical_analysis.clear_technical_cache()
        db.close()
        engine.dispose()
