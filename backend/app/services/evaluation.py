import asyncio
import json
import logging
import math
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import desc, func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.evaluation import SignalEvaluation
from app.models.session import AnalysisSession

logger = logging.getLogger(__name__)


def _find_existing_evaluation(
    db: Session, session_id: str, signal_dimension: str
) -> Optional[SignalEvaluation]:
    return db.execute(
        select(SignalEvaluation).where(
            SignalEvaluation.session_id == session_id,
            SignalEvaluation.signal_dimension == signal_dimension,
        )
    ).scalars().first()


def record_analysis_session(
    db: Session,
    symbol: str,
    overall_classification: str,
    total_latency_ms: float,
    rag_latency_ms: float,
    agents_data: list[dict[str, Any]],
    disagreements_data: list[dict[str, Any]],
    signals_data: list[dict[str, Any]],
    citations_data: list[dict[str, Any]],
    reasoning_trace: list[dict[str, Any]],
    personalized_interpretation: Optional[dict[str, Any]] = None,
    profile_id: Optional[str] = None,
    status: str = "completed",
    session_id: Optional[str] = None,
) -> AnalysisSession:
    """Persist completed intelligence analysis session for audit trail and evaluation."""
    session = AnalysisSession(
        id=session_id or str(uuid4()),
        symbol=symbol.strip().upper(),
        profile_id=profile_id,
        status=status,
        overall_classification=overall_classification,
        total_latency_ms=round(total_latency_ms, 2),
        rag_latency_ms=round(rag_latency_ms, 2),
        agents_data=json.dumps(agents_data, default=str),
        disagreements_data=json.dumps(disagreements_data, default=str),
        signals_data=json.dumps(signals_data, default=str),
        citations_data=json.dumps(citations_data, default=str),
        reasoning_trace=json.dumps(reasoning_trace, default=str),
        personalized_interpretation=json.dumps(personalized_interpretation or {}, default=str),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def record_signal_evaluation(
    db: Session,
    symbol: str,
    signal_classification: str,
    signal_dimension: str,
    entry_price: float,
    signal_timestamp: datetime,
    evaluation_horizon_days: int = 30,
    session_id: Optional[str] = None,
    exit_price: Optional[float] = None,
    is_synthetic: bool = False,
    data_source: str = "Historical Price Feed",
) -> SignalEvaluation:
    """Record a directional signal for subsequent forward-return evaluation."""
    if session_id is not None:
        existing = _find_existing_evaluation(db, session_id, signal_dimension)
        if existing is not None:
            return existing

    if not math.isfinite(entry_price) or entry_price <= 0:
        raise ValueError("Evaluation entry price must be a finite positive value.")
    if exit_price is not None and (not math.isfinite(exit_price) or exit_price <= 0):
        exit_price = None
    if signal_classification not in {"bullish", "bearish", "neutral"}:
        raise ValueError("Unsupported signal classification for evaluation.")

    normalized_signal_timestamp = signal_timestamp
    if normalized_signal_timestamp.tzinfo is None:
        normalized_signal_timestamp = normalized_signal_timestamp.replace(tzinfo=timezone.utc)
    target_dt = normalized_signal_timestamp + timedelta(days=evaluation_horizon_days)
    target_date_str = target_dt.strftime("%Y-%m-%d")

    actual_return_percent = None
    outcome = "pending_window"
    finalized_exit_price = None

    if (
        exit_price is not None
        and entry_price > 0
        and target_dt <= datetime.now(timezone.utc)
    ):
        finalized_exit_price = exit_price
        actual_return_percent = round(((exit_price - entry_price) / entry_price) * 100.0, 2)
        if signal_classification == "bullish":
            outcome = "accurate" if actual_return_percent > 1.5 else "inaccurate"
        elif signal_classification == "bearish":
            outcome = "accurate" if actual_return_percent < -1.5 else "inaccurate"
        else:
            outcome = "accurate" if abs(actual_return_percent) <= 3.0 else "inconclusive"

    # A deterministic primary key supplies a database-level conflict point for
    # concurrent retries without changing the existing schema. Existing rows
    # are still found by their logical key above, regardless of their old ID.
    record_id = (
        str(uuid5(NAMESPACE_URL, f"vantageai-evaluation:{session_id}:{signal_dimension}"))
        if session_id is not None
        else str(uuid4())
    )
    eval_record = SignalEvaluation(
        id=record_id,
        session_id=session_id,
        symbol=symbol.strip().upper(),
        signal_dimension=signal_dimension,
        signal_classification=signal_classification,
        signal_timestamp=signal_timestamp,
        entry_price=round(entry_price, 2),
        evaluation_horizon_days=evaluation_horizon_days,
        target_date=target_date_str,
        exit_price=round(finalized_exit_price, 2) if finalized_exit_price is not None else None,
        actual_return_percent=actual_return_percent,
        outcome=outcome,
        is_synthetic=is_synthetic,
        data_source=data_source,
    )
    for attempt in range(5):
        db.add(eval_record)
        try:
            db.commit()
            db.refresh(eval_record)
            return eval_record
        except IntegrityError:
            db.rollback()
            if session_id is None:
                raise
            existing = _find_existing_evaluation(db, session_id, signal_dimension)
            if existing is not None:
                return existing
            if attempt == 4:
                raise
        except OperationalError as exc:
            db.rollback()
            if session_id is None or "locked" not in str(exc).casefold() or attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))
            existing = _find_existing_evaluation(db, session_id, signal_dimension)
            if existing is not None:
                return existing
    raise RuntimeError("Unable to persist evaluation after concurrent retries.")


def _evaluation_status(record: SignalEvaluation) -> str:
    if record.is_synthetic:
        return "excluded"
    if record.outcome == "pending_window":
        return "pending"
    if record.outcome == "unavailable":
        return "unavailable"
    if record.outcome in {"accurate", "inaccurate", "inconclusive"}:
        return "evaluated"
    return "excluded"


def _session_analysis_completeness(agents_data: str) -> str:
    required = {"Technical Agent", "Fundamental Agent", "News Sentiment Agent"}
    try:
        assessments = json.loads(agents_data)
    except (TypeError, json.JSONDecodeError):
        return "unknown"
    if not isinstance(assessments, list) or not assessments:
        return "unknown"
    by_name = {
        item.get("agent_name"): item
        for item in assessments
        if isinstance(item, dict) and isinstance(item.get("agent_name"), str)
    }
    if not required.issubset(by_name):
        return "partial"
    if any(
        by_name[name].get("status") not in {"bullish", "bearish", "neutral"}
        or by_name[name].get("is_demo", False)
        for name in required
    ):
        return "partial"
    return "complete"


def _classify_outcome(classification: str, entry: float, exit_price: float) -> tuple[str, float]:
    if not all(math.isfinite(value) and value > 0 for value in (entry, exit_price)):
        raise ValueError("Outcome prices must be finite positive values.")
    change = round(((exit_price - entry) / entry) * 100.0, 2)
    if classification == "bullish":
        outcome = "accurate" if change > 1.5 else "inaccurate"
    elif classification == "bearish":
        outcome = "accurate" if change < -1.5 else "inaccurate"
    elif classification == "neutral":
        outcome = "accurate" if abs(change) <= 3.0 else "inconclusive"
    else:
        raise ValueError("Unsupported signal classification for evaluation.")
    return outcome, change


def _transition_matured_evaluation(
    db: Session, record_id: str, values: dict[str, Any]
) -> bool:
    """Atomically transition only still-retryable records, retrying SQLite locks."""
    for attempt in range(5):
        try:
            changed = db.execute(
                update(SignalEvaluation)
                .where(
                    SignalEvaluation.id == record_id,
                    SignalEvaluation.outcome.in_(("pending_window", "unavailable")),
                    SignalEvaluation.is_synthetic.is_(False),
                )
                .values(**values)
            ).rowcount
            db.commit()
            return bool(changed)
        except OperationalError as exc:
            db.rollback()
            if "locked" not in str(exc).casefold() or attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))
    return False


async def update_matured_evaluations(
    db: Session,
    *,
    now: Optional[datetime] = None,
    history_provider: Optional[Callable[[str], Awaitable[Any]]] = None,
    limit: int = 100,
) -> dict[str, int]:
    """Retry eligible matured evaluations using validated historical closes.

    This is an explicitly invoked operation; the application has no recurring
    scheduler. Synthetic rows are excluded and never sent to a provider.
    """
    if limit < 1 or limit > 500:
        raise ValueError("Evaluation update limit must be between 1 and 500.")
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    if history_provider is None:
        from app.services.historical_prices import get_historical_prices

        history_provider = get_historical_prices

    records = db.execute(
        select(SignalEvaluation)
        .where(
            SignalEvaluation.is_synthetic.is_(False),
            SignalEvaluation.outcome.in_(("pending_window", "unavailable")),
        )
        .order_by(SignalEvaluation.target_date, SignalEvaluation.created_at)
        .limit(limit)
    ).scalars().all()

    result = {
        "attempted": 0,
        "evaluated": 0,
        "unavailable": 0,
        "not_matured": 0,
        "deferred": 0,
    }
    deadline = time.monotonic() + 60.0
    for index, record in enumerate(records):
        if time.monotonic() >= deadline:
            result["deferred"] += len(records) - index
            break
        signal_time = record.signal_timestamp
        if signal_time.tzinfo is None:
            signal_time = signal_time.replace(tzinfo=timezone.utc)
        else:
            signal_time = signal_time.astimezone(timezone.utc)
        target_time = signal_time + timedelta(days=record.evaluation_horizon_days)
        if target_time > now:
            result["not_matured"] += 1
            continue

        result["attempted"] += 1
        failure_detail: Optional[str] = None
        history = None
        try:
            history = await asyncio.wait_for(history_provider(record.symbol), timeout=20.0)
        except Exception as exc:
            failure_detail = f"Unavailable: historical price retrieval failed ({type(exc).__name__})."
            logger.warning(
                "Evaluation price retrieval unavailable for %s (%s)",
                record.symbol,
                type(exc).__name__,
            )

        candidate_bar = None
        source = ""
        if history is not None:
            source = str(getattr(history, "source", ""))
            if not source.strip():
                failure_detail = "Unavailable: historical provider did not identify its source."
            elif any(marker in source.casefold() for marker in ("synthetic", "demo", "fixture", "mock")):
                failure_detail = "Unavailable: historical source is not eligible for real evaluation."
            else:
                target_day = date.fromisoformat(record.target_date)
                valid_bars = []
                for bar in getattr(history, "bars", ()):
                    try:
                        bar_day = date.fromisoformat(bar.trading_day)
                        close = float(bar.close)
                    except (AttributeError, TypeError, ValueError):
                        continue
                    if (
                        target_day < bar_day < now.date()
                        and math.isfinite(close)
                        and close > 0
                    ):
                        valid_bars.append((bar_day, bar))
                if valid_bars:
                    candidate_bar = min(valid_bars, key=lambda item: item[0])[1]
                if candidate_bar is None:
                    failure_detail = "Unavailable: no valid completed close on or after the target date."

        if candidate_bar is None:
            failure_detail = failure_detail or "Unavailable: historical outcome data is not available."
            changed = _transition_matured_evaluation(
                db,
                record.id,
                {"outcome": "unavailable", "data_source": failure_detail[:100]},
            )
            if changed:
                result["unavailable"] += 1
            continue

        try:
            outcome, actual_return = _classify_outcome(
                record.signal_classification,
                record.entry_price,
                float(candidate_bar.close),
            )
        except Exception as exc:
            failure_detail = f"Unavailable: outcome classification failed ({type(exc).__name__})."
            logger.warning(
                "Evaluation classification unavailable for %s (%s)",
                record.symbol,
                type(exc).__name__,
            )
            changed = _transition_matured_evaluation(
                db,
                record.id,
                {"outcome": "unavailable", "data_source": failure_detail[:100]},
            )
            if changed:
                result["unavailable"] += 1
            continue

        changed = _transition_matured_evaluation(
            db,
            record.id,
            dict(
                outcome=outcome,
                exit_price=round(float(candidate_bar.close), 2),
                actual_return_percent=actual_return,
                data_source=source[:100] or "Historical price feed",
            ),
        )
        if changed:
            result["evaluated"] += 1

    return result


def get_evaluation_metrics(db: Session) -> dict[str, Any]:
    """Aggregate real session latencies, signal accuracy, and evaluation coverage."""
    sessions = db.execute(
        select(AnalysisSession).order_by(desc(AnalysisSession.created_at)).limit(100)
    ).scalars().all()

    total_sessions = len(sessions)
    if total_sessions > 0:
        total_latencies = [s.total_latency_ms for s in sessions if s.total_latency_ms > 0]
        rag_latencies = [s.rag_latency_ms for s in sessions if s.rag_latency_ms > 0]
        avg_total_latency = round(sum(total_latencies) / max(1, len(total_latencies)), 1) if total_latencies else 0.0
        avg_rag_latency = round(sum(rag_latencies) / max(1, len(rag_latencies)), 1) if rag_latencies else 0.0

        # Parse per-agent latencies
        agent_latency_map: dict[str, list[float]] = {}
        for s in sessions:
            try:
                agents = json.loads(s.agents_data)
                for a in agents:
                    name = a.get("agent_name", "Unknown Agent")
                    lat = a.get("latency_ms", 0.0)
                    if lat > 0:
                        agent_latency_map.setdefault(name, []).append(lat)
            except Exception:
                pass

        agent_latencies = {
            name: round(sum(lats) / len(lats), 1)
            for name, lats in agent_latency_map.items()
        }
    else:
        avg_total_latency = 0.0
        avg_rag_latency = 0.0
        agent_latencies = {}

    # Signal evaluations
    evals = db.execute(
        select(SignalEvaluation).order_by(desc(SignalEvaluation.signal_timestamp)).limit(200)
    ).scalars().all()

    total_evals = len(evals)
    completed_evals = [
        e for e in evals
        if not e.is_synthetic and e.outcome in ("accurate", "inaccurate", "inconclusive")
    ]
    pending_evals = [e for e in evals if not e.is_synthetic and e.outcome == "pending_window"]
    unavailable_evals = [e for e in evals if not e.is_synthetic and e.outcome == "unavailable"]
    synthetic_evals = [e for e in evals if e.is_synthetic]
    synthetic_completed = [
        e for e in synthetic_evals
        if e.outcome in ("accurate", "inaccurate", "inconclusive")
    ]
    synthetic_pending = [e for e in synthetic_evals if e.outcome == "pending_window"]

    session_evaluation_counts: dict[str, dict[str, int]] = {}
    session_ids = [session.id for session in sessions]
    if session_ids:
        session_evaluations = db.execute(
            select(SignalEvaluation).where(SignalEvaluation.session_id.in_(session_ids))
        ).scalars().all()
        for evaluation in session_evaluations:
            counts = session_evaluation_counts.setdefault(
                evaluation.session_id,
                {"evaluated": 0, "pending": 0, "unavailable": 0, "excluded": 0},
            )
            counts[_evaluation_status(evaluation)] += 1

    accurate_count = sum(1 for e in completed_evals if e.outcome == "accurate")
    inaccurate_count = sum(1 for e in completed_evals if e.outcome == "inaccurate")
    inconclusive_count = sum(1 for e in completed_evals if e.outcome == "inconclusive")

    accuracy_rate = (
        round((accurate_count / max(1, len(completed_evals))) * 100.0, 1)
        if completed_evals
        else 0.0
    )

    recent_sessions_summary = [
        {
            "id": s.id,
            "symbol": s.symbol,
            "status": s.status,
            "overall_classification": s.overall_classification,
            "analysis_completeness": _session_analysis_completeness(s.agents_data),
            "total_latency_ms": s.total_latency_ms,
            "rag_latency_ms": s.rag_latency_ms,
            "created_at": s.created_at.isoformat(),
            "evaluation_status_counts": session_evaluation_counts.get(
                s.id,
                {"evaluated": 0, "pending": 0, "unavailable": 0, "excluded": 0},
            ),
        }
        for s in sessions[:10]
    ]

    eval_history = [
        {
            "id": e.id,
            "symbol": e.symbol,
            "dimension": e.signal_dimension,
            "classification": e.signal_classification,
            "entry_price": e.entry_price,
            "exit_price": e.exit_price,
            "horizon_days": e.evaluation_horizon_days,
            "signal_date": e.signal_timestamp.strftime("%Y-%m-%d"),
            "target_date": e.target_date,
            "actual_return_percent": e.actual_return_percent,
            "outcome": e.outcome,
            "status": _evaluation_status(e),
            "status_detail": e.data_source if e.outcome == "unavailable" else None,
            "is_synthetic": e.is_synthetic,
        }
        for e in evals[:15]
    ]

    return {
        "total_sessions": total_sessions,
        "average_total_latency_ms": avg_total_latency,
        "average_rag_latency_ms": avg_rag_latency,
        "agent_latencies": agent_latencies,
        "total_signals_evaluated": total_evals,
        "synthetic_signals_evaluated": len(synthetic_evals),
        "completed_windows_count": len(completed_evals),
        "pending_windows_count": len(pending_evals),
        "unavailable_windows_count": len(unavailable_evals),
        "excluded_windows_count": len(synthetic_evals),
        "synthetic_completed_windows_count": len(synthetic_completed),
        "synthetic_pending_windows_count": len(synthetic_pending),
        "accuracy_rate_percent": accuracy_rate,
        "accurate_signals_count": accurate_count,
        "inaccurate_signals_count": inaccurate_count,
        "inconclusive_signals_count": inconclusive_count,
        "evaluation_history": eval_history,
        "recent_sessions": recent_sessions_summary,
        "last_updated_at": datetime.now(timezone.utc).isoformat(),
    }


def seed_historical_evaluations(db: Session) -> int:
    """Seed explicitly synthetic evaluation examples for UI demonstrations."""
    # Correct records created by older versions which presented demo prices as real.
    legacy_seeded = db.execute(
        select(SignalEvaluation).where(
            SignalEvaluation.data_source == "Historical 30-Day Evaluation Log",
            SignalEvaluation.is_synthetic.is_(False),
        )
    ).scalars().all()
    for evaluation in legacy_seeded:
        evaluation.is_synthetic = True
        evaluation.data_source = "Synthetic demonstration benchmark"
    if legacy_seeded:
        db.commit()

    existing_count = db.execute(select(func.count(SignalEvaluation.id))).scalar() or 0
    if existing_count > 0:
        return existing_count

    # Illustrative outcomes only; these are not sourced from historical market prices.
    benchmark_records = [
        # Completed windows (approx 60-90 days ago)
        {"symbol": "NVDA", "dim": "synthesis", "cls": "bullish", "entry": 118.5, "exit": 138.2, "days_ago": 75, "synth": True},
        {"symbol": "AAPL", "dim": "technical", "cls": "bullish", "entry": 224.0, "exit": 235.5, "days_ago": 60, "synth": True},
        {"symbol": "MSFT", "dim": "fundamental", "cls": "bullish", "entry": 415.0, "exit": 432.0, "days_ago": 55, "synth": True},
        {"symbol": "TSLA", "dim": "synthesis", "cls": "bearish", "entry": 252.0, "exit": 218.4, "days_ago": 50, "synth": True},
        {"symbol": "GOOGL", "dim": "news", "cls": "neutral", "entry": 165.0, "exit": 168.1, "days_ago": 45, "synth": True},
        {"symbol": "NVDA", "dim": "technical", "cls": "bullish", "entry": 128.0, "exit": 141.5, "days_ago": 40, "synth": True},
        {"symbol": "AAPL", "dim": "fundamental", "cls": "neutral", "entry": 230.0, "exit": 228.0, "days_ago": 35, "synth": True},
        # Pending windows (less than 30 days old)
        {"symbol": "MSFT", "dim": "synthesis", "cls": "bullish", "entry": 428.0, "exit": None, "days_ago": 15, "synth": True},
        {"symbol": "NVDA", "dim": "news", "cls": "bullish", "entry": 135.0, "exit": None, "days_ago": 10, "synth": True},
        {"symbol": "TSLA", "dim": "technical", "cls": "bullish", "entry": 240.0, "exit": None, "days_ago": 5, "synth": True},
    ]

    for rec in benchmark_records:
        sig_dt = datetime.now(timezone.utc) - timedelta(days=rec["days_ago"])
        record_signal_evaluation(
            db=db,
            symbol=rec["symbol"],
            signal_classification=rec["cls"],
            signal_dimension=rec["dim"],
            entry_price=rec["entry"],
            signal_timestamp=sig_dt,
            evaluation_horizon_days=30,
            exit_price=rec["exit"],
            is_synthetic=rec["synth"],
            data_source="Synthetic demonstration benchmark",
        )

    return len(benchmark_records)
