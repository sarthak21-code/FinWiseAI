import asyncio
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.services.evaluation import (
    get_evaluation_metrics,
    record_analysis_session,
    record_signal_evaluation,
    seed_historical_evaluations,
    update_matured_evaluations,
)
from app.models.evaluation import SignalEvaluation
from app.services.historical_prices import HistoricalBar


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def test_record_analysis_session(in_memory_db):
    session = record_analysis_session(
        db=in_memory_db,
        symbol="AAPL",
        overall_classification="bullish",
        total_latency_ms=125.4,
        rag_latency_ms=34.2,
        agents_data=[{"agent_name": "Technical Agent", "status": "bullish", "latency_ms": 50.0}],
        disagreements_data=[],
        signals_data=[],
        citations_data=[],
        reasoning_trace=[],
    )
    assert session.id is not None
    assert session.symbol == "AAPL"
    assert session.total_latency_ms == 125.4


def test_record_analysis_session_preserves_analysis_identifier(in_memory_db):
    expected_id = "analysis-session-test-id"

    session = record_analysis_session(
        db=in_memory_db,
        session_id=expected_id,
        symbol="AAPL",
        overall_classification="bullish",
        total_latency_ms=20.0,
        rag_latency_ms=2.0,
        agents_data=[],
        disagreements_data=[],
        signals_data=[],
        citations_data=[],
        reasoning_trace=[],
    )

    evaluation = record_signal_evaluation(
        db=in_memory_db,
        symbol="AAPL",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100.0,
        signal_timestamp=datetime.now(timezone.utc),
        session_id=expected_id,
    )

    assert session.id == expected_id
    assert evaluation.session_id == session.id
    assert in_memory_db.get(type(session), evaluation.session_id) is session


def test_signal_evaluation_outcomes(in_memory_db):
    now = datetime.now(timezone.utc) - timedelta(days=31)

    # Completed accurate bullish: entry 100 -> exit 110 (+10%)
    e1 = record_signal_evaluation(
        db=in_memory_db,
        symbol="NVDA",
        signal_classification="bullish",
        signal_dimension="technical",
        entry_price=100.0,
        signal_timestamp=now,
        evaluation_horizon_days=30,
        exit_price=110.0,
    )
    assert e1.outcome == "accurate"
    assert e1.actual_return_percent == 10.0

    # Incomplete/pending window: exit price None
    e2 = record_signal_evaluation(
        db=in_memory_db,
        symbol="MSFT",
        signal_classification="bullish",
        signal_dimension="fundamental",
        entry_price=400.0,
        signal_timestamp=now,
        evaluation_horizon_days=30,
        exit_price=None,
    )
    assert e2.outcome == "pending_window"
    assert e2.actual_return_percent is None


def test_get_evaluation_metrics_aggregation(in_memory_db):
    seed_historical_evaluations(in_memory_db)
    metrics = get_evaluation_metrics(in_memory_db)

    assert metrics["total_signals_evaluated"] >= 10
    assert metrics["completed_windows_count"] == 0
    assert metrics["pending_windows_count"] == 0
    assert metrics["synthetic_completed_windows_count"] >= 5
    assert metrics["synthetic_pending_windows_count"] >= 2
    assert all(item["is_synthetic"] for item in metrics["evaluation_history"])
    assert "accuracy_rate_percent" in metrics


def test_not_yet_matured_prediction_remains_pending(in_memory_db):
    now = datetime.now(timezone.utc)
    record = record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=now,
        evaluation_horizon_days=30,
    )

    assert record.target_date > now.date().isoformat()
    assert record.outcome == "pending_window"
    assert record.exit_price is None


def test_available_price_does_not_finalize_before_window_matures(in_memory_db):
    now = datetime.now(timezone.utc)
    record = record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=now,
        evaluation_horizon_days=30,
        exit_price=110,
    )

    assert record.outcome == "pending_window"
    assert record.exit_price is None
    assert record.actual_return_percent is None


def test_matured_prediction_with_available_exit_is_classified(in_memory_db):
    signal_time = datetime.now(timezone.utc) - timedelta(days=31)
    record = record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=signal_time,
        evaluation_horizon_days=30,
        exit_price=105,
    )

    assert record.target_date <= datetime.now(timezone.utc).date().isoformat()
    assert record.actual_return_percent == 5.0
    assert record.outcome == "accurate"


def test_matured_prediction_without_outcome_data_stays_pending(in_memory_db):
    signal_time = datetime.now(timezone.utc) - timedelta(days=31)
    record = record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=signal_time,
        evaluation_horizon_days=30,
    )

    metrics = get_evaluation_metrics(in_memory_db)
    assert record.target_date <= datetime.now(timezone.utc).date().isoformat()
    assert record.outcome == "pending_window"
    assert metrics["pending_windows_count"] == 1
    assert metrics["completed_windows_count"] == 0


def test_finalized_outcome_is_not_changed_by_metrics_read(in_memory_db):
    record = record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=datetime.now(timezone.utc) - timedelta(days=31),
        evaluation_horizon_days=30,
        exit_price=95,
    )

    assert record.outcome == "inaccurate"
    get_evaluation_metrics(in_memory_db)
    in_memory_db.refresh(record)
    assert record.outcome == "inaccurate"
    assert record.actual_return_percent == -5.0


def test_duplicate_session_signal_recording_is_idempotent(in_memory_db):
    timestamp = datetime.now(timezone.utc) - timedelta(days=31)
    first = record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=timestamp,
        session_id="session-retry-test",
        exit_price=110,
    )
    retry = record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=timestamp,
        session_id="session-retry-test",
        exit_price=120,
    )

    rows = in_memory_db.execute(select(SignalEvaluation)).scalars().all()
    assert retry.id == first.id
    assert retry.actual_return_percent == 10.0
    assert len(rows) == 1


def test_synthetic_outcomes_are_excluded_from_real_accuracy(in_memory_db):
    now = datetime.now(timezone.utc) - timedelta(days=31)
    record_signal_evaluation(
        db=in_memory_db,
        symbol="REAL",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=now,
        exit_price=110,
    )
    record_signal_evaluation(
        db=in_memory_db,
        symbol="DEMO",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=now,
        exit_price=110,
        is_synthetic=True,
        data_source="Synthetic test fixture",
    )

    metrics = get_evaluation_metrics(in_memory_db)
    assert metrics["completed_windows_count"] == 1
    assert metrics["accurate_signals_count"] == 1
    assert metrics["synthetic_completed_windows_count"] == 1
    assert metrics["accuracy_rate_percent"] == 100.0


def test_demo_evaluation_seeding_is_idempotent(in_memory_db):
    first_count = seed_historical_evaluations(in_memory_db)
    second_count = seed_historical_evaluations(in_memory_db)

    rows = in_memory_db.execute(select(SignalEvaluation)).scalars().all()
    assert first_count == second_count == len(rows) == 10


def test_session_latency_metrics_aggregate_persisted_sessions(in_memory_db):
    for symbol, total_latency, rag_latency, agent_latency in (
        ("AAA", 100.0, 10.0, 40.0),
        ("BBB", 300.0, 20.0, 60.0),
    ):
        record_analysis_session(
            db=in_memory_db,
            symbol=symbol,
            overall_classification="neutral",
            total_latency_ms=total_latency,
            rag_latency_ms=rag_latency,
            agents_data=[{"agent_name": "Technical Agent", "latency_ms": agent_latency}],
            disagreements_data=[],
            signals_data=[],
            citations_data=[],
            reasoning_trace=[],
        )

    metrics = get_evaluation_metrics(in_memory_db)
    assert metrics["total_sessions"] == 2
    assert metrics["average_total_latency_ms"] == 200.0
    assert metrics["average_rag_latency_ms"] == 15.0
    assert metrics["agent_latencies"] == {"Technical Agent": 50.0}


def test_session_evaluation_counts_separate_every_outcome_status(in_memory_db):
    session = record_analysis_session(
        db=in_memory_db,
        session_id="session-status-counts",
        symbol="TEST",
        overall_classification="neutral",
        total_latency_ms=120,
        rag_latency_ms=10,
        agents_data=[],
        disagreements_data=[],
        signals_data=[],
        citations_data=[],
        reasoning_trace=[],
    )
    old_timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="evaluated",
        entry_price=100,
        signal_timestamp=old_timestamp,
        evaluation_horizon_days=30,
        session_id=session.id,
        exit_price=105,
    )
    record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="pending",
        entry_price=100,
        signal_timestamp=datetime.now(timezone.utc),
        evaluation_horizon_days=30,
        session_id=session.id,
    )
    record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="unavailable",
        entry_price=100,
        signal_timestamp=old_timestamp,
        evaluation_horizon_days=30,
        session_id=session.id,
    )
    record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthetic",
        entry_price=100,
        signal_timestamp=old_timestamp,
        evaluation_horizon_days=30,
        session_id=session.id,
        exit_price=105,
        is_synthetic=True,
        data_source="Synthetic example",
    )

    async def no_prices(_symbol):
        return price_history()

    asyncio.run(update_matured_evaluations(
        in_memory_db,
        now=datetime(2025, 2, 10, tzinfo=timezone.utc),
        history_provider=no_prices,
    ))
    metrics = get_evaluation_metrics(in_memory_db)
    recent = next(item for item in metrics["recent_sessions"] if item["id"] == session.id)
    assert recent["evaluation_status_counts"] == {
        "evaluated": 1,
        "pending": 1,
        "unavailable": 1,
        "excluded": 1,
    }
    assert metrics["inaccurate_signals_count"] == 0


def test_session_summary_marks_partial_agent_analysis(in_memory_db):
    session = record_analysis_session(
        db=in_memory_db,
        session_id="partial-session-completeness",
        symbol="TEST",
        overall_classification="bullish",
        total_latency_ms=80,
        rag_latency_ms=5,
        agents_data=[
            {"agent_name": "Technical Agent", "status": "bullish", "is_demo": False},
            {"agent_name": "Fundamental Agent", "status": "unavailable", "is_demo": False},
            {"agent_name": "News Sentiment Agent", "status": "bearish", "is_demo": False},
        ],
        disagreements_data=[],
        signals_data=[],
        citations_data=[],
        reasoning_trace=[],
    )

    metrics = get_evaluation_metrics(in_memory_db)
    recent = next(item for item in metrics["recent_sessions"] if item["id"] == session.id)
    assert recent["analysis_completeness"] == "partial"
    assert recent["evaluation_status_counts"] == {
        "evaluated": 0,
        "pending": 0,
        "unavailable": 0,
        "excluded": 0,
    }


def make_matured_record(db, *, session_id="matured-session", dimension="synthesis", synthetic=False):
    return record_signal_evaluation(
        db=db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension=dimension,
        entry_price=100,
        signal_timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        evaluation_horizon_days=30,
        session_id=session_id,
        is_synthetic=synthetic,
        data_source="Test historical market fixture",
    )


def price_history(*bars, source="Yahoo Finance via yfinance history"):
    return SimpleNamespace(source=source, bars=tuple(bars))


def bar(day, close):
    return HistoricalBar(day, None, None, None, close, None)


def test_updater_leaves_unmatured_pending_without_provider_call(in_memory_db):
    record = record_signal_evaluation(
        db=in_memory_db,
        symbol="TEST",
        signal_classification="bullish",
        signal_dimension="synthesis",
        entry_price=100,
        signal_timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
        evaluation_horizon_days=30,
        session_id="future-session",
    )
    calls = []

    async def provider(symbol):
        calls.append(symbol)
        return price_history(bar("2026-07-05", 105))

    result = asyncio.run(update_matured_evaluations(
        in_memory_db,
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
        history_provider=provider,
    ))

    assert result == {
        "attempted": 0,
        "evaluated": 0,
        "unavailable": 0,
        "not_matured": 1,
        "deferred": 0,
    }
    assert calls == []
    assert record.outcome == "pending_window"


def test_updater_uses_first_completed_close_after_target_date(in_memory_db):
    record = make_matured_record(in_memory_db)
    calls = []

    async def provider(symbol):
        calls.append(symbol)
        return price_history(
            bar("2025-01-30", 900),  # before the 2025-01-31 target
            bar("2025-01-31", 900),  # same-day close is not timestamped precisely enough
            bar("2025-02-03", 106),
            bar("2025-02-04", 120),
        )

    result = asyncio.run(update_matured_evaluations(
        in_memory_db,
        now=datetime(2025, 2, 10, tzinfo=timezone.utc),
        history_provider=provider,
    ))

    in_memory_db.refresh(record)
    assert result["evaluated"] == 1
    assert calls == ["TEST"]
    assert record.outcome == "accurate"
    assert record.exit_price == 106
    assert record.actual_return_percent == 6


def test_unavailable_outcome_is_retryable_and_not_counted_as_incorrect(in_memory_db):
    record = make_matured_record(in_memory_db, session_id="retryable-session")

    async def unavailable(_symbol):
        raise TimeoutError("provider detail must not be persisted")

    first = asyncio.run(update_matured_evaluations(
        in_memory_db,
        now=datetime(2025, 2, 10, tzinfo=timezone.utc),
        history_provider=unavailable,
    ))
    in_memory_db.refresh(record)
    assert first["unavailable"] == 1
    assert record.outcome == "unavailable"
    assert "TimeoutError" in record.data_source
    assert "provider detail" not in record.data_source

    async def later_available(_symbol):
        return price_history(bar("2025-02-03", 104))

    retry = asyncio.run(update_matured_evaluations(
        in_memory_db,
        now=datetime(2025, 2, 10, tzinfo=timezone.utc),
        history_provider=later_available,
    ))
    in_memory_db.refresh(record)
    metrics = get_evaluation_metrics(in_memory_db)
    assert retry["evaluated"] == 1
    assert record.outcome == "accurate"
    assert metrics["unavailable_windows_count"] == 0
    assert metrics["inaccurate_signals_count"] == 0


def test_updater_rejects_incomplete_or_synthetic_source_data(in_memory_db):
    incomplete = make_matured_record(in_memory_db, session_id="incomplete-session")
    synthetic = make_matured_record(
        in_memory_db,
        session_id="synthetic-session",
        dimension="technical",
        synthetic=True,
    )
    calls = []

    async def provider(symbol):
        calls.append(symbol)
        return price_history(
            bar("bad-date", 105),
            bar("2025-01-30", 105),
            bar("2025-02-03", float("nan")),
        )

    result = asyncio.run(update_matured_evaluations(
        in_memory_db,
        now=datetime(2025, 2, 10, tzinfo=timezone.utc),
        history_provider=provider,
    ))
    in_memory_db.refresh(incomplete)
    in_memory_db.refresh(synthetic)
    metrics = get_evaluation_metrics(in_memory_db)
    assert result["unavailable"] == 1
    assert incomplete.outcome == "unavailable"
    assert synthetic.outcome == "pending_window"
    assert calls == ["TEST"]
    assert metrics["unavailable_windows_count"] == 1
    assert metrics["excluded_windows_count"] == 1
    assert metrics["inaccurate_signals_count"] == 0
    statuses = {item["id"]: item["status"] for item in metrics["evaluation_history"]}
    assert statuses[incomplete.id] == "unavailable"
    assert statuses[synthetic.id] == "excluded"


def test_updater_rejects_a_synthetic_price_provider_source(in_memory_db):
    record = make_matured_record(in_memory_db, session_id="synthetic-provider-session")

    async def provider(_symbol):
        return price_history(
            bar("2025-01-31", 150),
            source="Synthetic demonstration data",
        )

    result = asyncio.run(update_matured_evaluations(
        in_memory_db,
        now=datetime(2025, 2, 10, tzinfo=timezone.utc),
        history_provider=provider,
    ))
    in_memory_db.refresh(record)
    assert result["unavailable"] == 1
    assert record.outcome == "unavailable"
    assert record.exit_price is None
    assert "not eligible" in record.data_source


def test_repeated_updater_run_does_not_reprocess_finalized_outcome(in_memory_db):
    record = make_matured_record(in_memory_db)
    calls = []

    async def provider(symbol):
        calls.append(symbol)
        return price_history(bar("2025-02-03", 106))

    for _ in range(2):
        asyncio.run(update_matured_evaluations(
            in_memory_db,
            now=datetime(2025, 2, 10, tzinfo=timezone.utc),
            history_provider=provider,
        ))
    in_memory_db.refresh(record)
    assert calls == ["TEST"]
    assert record.outcome == "accurate"
    assert record.exit_price == 106


def test_classification_failure_is_safely_recorded_as_unavailable(in_memory_db):
    record = make_matured_record(in_memory_db)
    record.signal_classification = "invalid-legacy-value"
    in_memory_db.commit()

    async def provider(_symbol):
        return price_history(bar("2025-02-03", 106))

    result = asyncio.run(update_matured_evaluations(
        in_memory_db,
        now=datetime(2025, 2, 10, tzinfo=timezone.utc),
        history_provider=provider,
    ))
    in_memory_db.refresh(record)
    assert result["unavailable"] == 1
    assert record.outcome == "unavailable"
    assert record.exit_price is None
    assert "classification failed" in record.data_source


def test_signal_dimensions_remain_distinct_within_a_session(in_memory_db):
    synthesis = make_matured_record(in_memory_db, session_id="multi-dimension", dimension="synthesis")
    technical = make_matured_record(in_memory_db, session_id="multi-dimension", dimension="technical")
    assert synthesis.id != technical.id
    assert len(in_memory_db.execute(select(SignalEvaluation)).scalars().all()) == 2


def test_concurrent_session_dimension_retries_have_database_conflict_protection(tmp_path, monkeypatch):
    from app.services import evaluation

    database_path = Path(tmp_path) / "concurrent-evaluation-test.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"timeout": 10})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    query_barrier = Barrier(2)
    original_find = evaluation._find_existing_evaluation
    lookup_count = 0

    def synchronized_find(db, session_id, dimension):
        nonlocal lookup_count
        existing = original_find(db, session_id, dimension)
        if session_id == "concurrent-session" and lookup_count < 2:
            lookup_count += 1
            query_barrier.wait(timeout=5)
        return existing

    monkeypatch.setattr(evaluation, "_find_existing_evaluation", synchronized_find)
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def create_attempt():
        with factory() as db:
            return record_signal_evaluation(
                db=db,
                symbol="TEST",
                signal_classification="bullish",
                signal_dimension="synthesis",
                entry_price=100,
                signal_timestamp=timestamp,
                session_id="concurrent-session",
            ).id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            record_ids = list(pool.map(lambda _index: create_attempt(), range(2)))
        with factory() as db:
            rows = db.execute(
                select(SignalEvaluation).where(
                    SignalEvaluation.session_id == "concurrent-session",
                    SignalEvaluation.signal_dimension == "synthesis",
                )
            ).scalars().all()
        assert len(rows) == 1
        assert record_ids == [rows[0].id, rows[0].id]
    finally:
        engine.dispose()


def test_concurrent_outcome_updates_finalize_once_without_overwriting(tmp_path):
    database_path = Path(tmp_path) / "concurrent-outcome-test.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"timeout": 10})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        record = record_signal_evaluation(
            db=db,
            symbol="TEST",
            signal_classification="bullish",
            signal_dimension="synthesis",
            entry_price=100,
            signal_timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            evaluation_horizon_days=30,
            session_id="concurrent-update-session",
        )
        record_id = record.id

    provider_barrier = Barrier(2)

    def update_attempt(close_price):
        async def provider(_symbol):
            provider_barrier.wait(timeout=5)
            return price_history(bar("2025-02-03", close_price))

        with factory() as db:
            return asyncio.run(
                update_matured_evaluations(
                    db,
                    now=datetime(2025, 2, 10, tzinfo=timezone.utc),
                    history_provider=provider,
                )
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update_attempt, (106, 108)))
        with factory() as db:
            final = db.get(SignalEvaluation, record_id)
            rows = db.execute(
                select(SignalEvaluation).where(
                    SignalEvaluation.session_id == "concurrent-update-session"
                )
            ).scalars().all()
        assert len(rows) == 1
        assert final.outcome == "accurate"
        assert final.exit_price in {106, 108}
        assert final.actual_return_percent in {6, 8}
        assert sum(item["evaluated"] for item in results) == 1
    finally:
        engine.dispose()
