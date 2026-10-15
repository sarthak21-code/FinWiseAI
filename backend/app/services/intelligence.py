import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas.intelligence import (
    AgentAssessment,
    AgentDisagreement,
    IntelligenceAnalysis,
    ReasoningStep,
)
from app.schemas.news import NewsSentimentResult
from app.schemas.rag import GroundedCitation
from app.schemas.signals import StructuredSignal
from app.schemas.technical import TechnicalAnalysis
from app.services.fundamental_analysis import (
    FundamentalDataUnavailable,
    fetch_fundamental_metrics,
    interpret_fundamentals,
)
from app.services.historical_prices import get_historical_prices
from app.services.investors import generate_personalized_interpretation
from app.services.news_sentiment import analyze_news_sentiment
from app.services.rag import ground_agent_claims, search_documents
from app.services.signals import (
    classify_fundamental_health_signal,
    classify_news_sentiment_signal,
    classify_price_momentum,
    classify_volume_anomaly,
)
from app.services.technical_analysis import get_technical_analysis

logger = logging.getLogger(__name__)


def interpret_technical_analysis(technical) -> AgentAssessment:
    """Interpret calculated indicators without using an LLM."""
    evidence = list(getattr(technical, "evidence", []))

    limitations = [
        "Technical indicators describe historical price behaviour.",
        "Technical signals do not establish future returns or investment suitability.",
    ]

    is_demo = getattr(technical, "is_demo", False)
    if is_demo:
        limitations.append(
            "The analysis uses synthetic demonstration data, not verified market data."
        )

        return AgentAssessment(
            agent_name="Technical Agent",
            status="insufficient_data",
            summary=(
                "A technical assessment cannot be treated as market evidence "
                "because the underlying data is synthetic."
            ),
            evidence=evidence,
            limitations=limitations,
            source=getattr(technical, "source", "Synthetic"),
            is_demo=True,
            agent_id="tech_agent_01",
            confidence=0.0,
            confidence_method="Synthetic data flag active.",
        )

    status = getattr(technical, "technical_bias", "neutral")

    if status == "insufficient_data":
        summary = "There is insufficient historical data to establish a technical bias."
        confidence = 0.0
    elif status == "bullish":
        summary = "The configured technical indicators meet the rules for a bullish bias."
        confidence = 0.80
    elif status == "bearish":
        summary = "The configured technical indicators meet the rules for a bearish bias."
        confidence = 0.80
    else:
        summary = "The available indicators do not collectively meet the configured bullish or bearish conditions."
        confidence = 0.50

    return AgentAssessment(
        agent_name="Technical Agent",
        status=status,
        summary=summary,
        evidence=evidence,
        limitations=limitations,
        source=getattr(technical, "source", "Historical Market Data"),
        is_demo=False,
        agent_id="tech_agent_01",
        confidence=confidence,
        confidence_method="Deterministic technical rules (SMA 20, SMA 50, RSI 14, momentum).",
    )


def detect_disagreements(
    assessments: list[AgentAssessment],
) -> list[AgentDisagreement]:
    """Report opposing directional assessments without forcing consensus."""
    directional = [
        assessment
        for assessment in assessments
        if not assessment.is_demo
        and assessment.status in ("bullish", "bearish")
    ]

    disagreements: list[AgentDisagreement] = []

    for index, first in enumerate(directional):
        for second in directional[index + 1:]:
            if first.status == second.status:
                continue

            disagreements.append(
                AgentDisagreement(
                    agents=[first.agent_name, second.agent_name],
                    conflict=(
                        f"{first.agent_name} is {first.status}, while "
                        f"{second.agent_name} is {second.status}."
                    ),
                    evidence=[
                        f"{first.agent_name}: {first.summary}",
                        f"{second.agent_name}: {second.summary}",
                    ],
                    significance="high",
                )
            )

    return disagreements


async def analyze_symbol(
    symbol: str,
    profile_id: Optional[str] = None,
    db: Optional[Session] = None,
    owner_id: Optional[str] = None,
) -> IntelligenceAnalysis:
    """Combine technical, fundamental, news, and filing evidence concurrently."""
    start_total = time.perf_counter()
    session_id = str(uuid4())
    warnings: list[str] = []
    reasoning_trace: list[ReasoningStep] = []

    # Step 1: Ingestion & Validation
    reasoning_trace.append(
        ReasoningStep(
            step_number=1,
            title="Market Observation & Data Ingestion",
            description=f"Initiating concurrent observation retrieval for symbol '{symbol}'.",
            outcome="Technical, fundamental, and news services were requested in parallel; document retrieval runs after agent evidence is available.",
            metadata={"symbol": symbol, "session_id": session_id},
        )
    )

    # 1. Concurrent Agent Execution
    async def run_tech():
        t0 = time.perf_counter()
        try:
            res = await get_technical_analysis(symbol)
            if res is not None and not isinstance(res, TechnicalAnalysis):
                payload = res if isinstance(res, dict) else vars(res)
                res = TechnicalAnalysis.model_validate(payload)
            return res, (time.perf_counter() - t0) * 1000.0, None
        except Exception as exc:
            return None, (time.perf_counter() - t0) * 1000.0, exc

    async def run_fund():
        t0 = time.perf_counter()
        res = None
        try:
            res = await fetch_fundamental_metrics(symbol)
            assessment = interpret_fundamentals(res)
            latency = (time.perf_counter() - t0) * 1000.0
            return res, assessment, latency, None
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1000.0
            return res, None, latency, exc

    async def run_news():
        t0 = time.perf_counter()
        try:
            res = await analyze_news_sentiment(symbol)
            if not isinstance(res, NewsSentimentResult):
                payload = res if isinstance(res, dict) else vars(res)
                res = NewsSentimentResult.model_validate(payload)
            if res.status in ("bullish", "bearish", "neutral") and (
                res.sentiment_score is None or not res.articles
            ):
                raise ValueError("News result is missing its score or headline evidence.")
            if res.status == "bullish" and res.sentiment_score < 0.15:
                raise ValueError("Bullish news result conflicts with its sentiment score.")
            if res.status == "bearish" and res.sentiment_score > -0.15:
                raise ValueError("Bearish news result conflicts with its sentiment score.")
            return res, (time.perf_counter() - t0) * 1000.0, None
        except Exception as exc:
            return None, (time.perf_counter() - t0) * 1000.0, exc

    async def run_history():
        try:
            return await get_historical_prices(symbol)
        except Exception:
            return None

    # Parallel dispatch
    tech_task = asyncio.create_task(run_tech())
    fund_task = asyncio.create_task(run_fund())
    news_task = asyncio.create_task(run_news())
    hist_task = asyncio.create_task(run_history())

    (tech_res, tech_lat, tech_exc), (fund_res, fundamental_assessment, fund_lat, fund_exc), (news_res, news_lat, news_exc), hist_res = await asyncio.gather(
        tech_task, fund_task, news_task, hist_task
    )

    # Interpret Technical
    if tech_exc is not None or tech_res is None:
        warnings.append(
            "Technical Agent unavailable; technical price evidence was not included."
        )
        technical_assessment = AgentAssessment(
            agent_name="Technical Agent",
            status="unavailable",
            summary="Technical analysis could not be completed from the available market data.",
            evidence=[],
            limitations=["No technical indicators are available for this analysis."],
            source="Unavailable",
            agent_id="tech_agent_01",
            confidence=0.0,
            confidence_method="Unavailable; no technical result was returned.",
        )
    else:
        technical_assessment = interpret_technical_analysis(tech_res)
    technical_assessment.latency_ms = round(tech_lat, 1)
    assessments = [technical_assessment]

    if getattr(tech_res, "is_demo", False):
        warnings.append(
            "Synthetic market data detected. Do not treat the technical "
            "assessment as evidence about the real market."
        )

    # Interpret Fundamentals
    # Only feed metrics downstream when both retrieval and interpretation
    # completed. A malformed object can otherwise still influence signals
    # after its fundamental assessment was marked unavailable.
    fundamental_metrics = (
        fund_res
        if fund_exc is None and fundamental_assessment is not None
        else None
    )
    if fund_exc is not None:
        if isinstance(fund_exc, FundamentalDataUnavailable):
            warnings.append("Fundamental Agent unavailable; provider fundamentals were not returned.")
            assessments.append(
                AgentAssessment(
                    agent_name="Fundamental Agent",
                    status="unavailable",
                    summary="Fundamental data is unavailable from the configured provider.",
                    evidence=[],
                    limitations=["No verified financial statement metrics were returned for this symbol."],
                    source="Unavailable",
                    is_demo=False,
                    agent_id="fund_agent_01",
                    latency_ms=round(fund_lat, 1),
                    confidence=0.0,
                    confidence_method="Unavailable; no fundamental metrics were returned.",
                )
            )
        else:
            warnings.append(
                "Fundamental Agent could not complete its assessment because "
                "of an unexpected provider or processing error."
            )
            assessments.append(
                AgentAssessment(
                    agent_name="Fundamental Agent",
                    status="unavailable",
                    summary="Fundamental assessment could not be completed due to a processing error.",
                    evidence=[],
                    limitations=["Fundamental metrics unavailable."],
                    source="Unavailable",
                    is_demo=False,
                    agent_id="fund_agent_01",
                    latency_ms=round(fund_lat, 1),
                    confidence=0.0,
                    confidence_method="Unavailable; provider or processing error prevented a result.",
                )
            )
    else:
        if fundamental_assessment is not None:
            fundamental_assessment.latency_ms = round(fund_lat, 1)
            fundamental_assessment.agent_id = "fund_agent_01"
            assessments.append(fundamental_assessment)
            warnings.extend(getattr(fundamental_metrics, "data_warnings", []))
        else:
            warnings.append(
                "Fundamental Agent interpretation failed; no fundamental conclusion was included."
            )
            if not any(a.agent_name == "Fundamental Agent" for a in assessments):
                assessments.append(
                    AgentAssessment(
                        agent_name="Fundamental Agent",
                        status="unavailable",
                        summary="Fundamental assessment failed during interpretation.",
                        evidence=[],
                        limitations=["Fundamental metrics unavailable."],
                        source="Unavailable",
                        is_demo=False,
                        agent_id="fund_agent_01",
                        latency_ms=round(fund_lat, 1),
                        confidence=0.0,
                        confidence_method="Unavailable; fundamental interpretation failed.",
                    )
                )

    # Interpret News
    if news_exc is not None or news_res is None:
        warnings.append(
            "News Sentiment Agent unavailable; no news-based conclusion was included."
        )
        news_result = NewsSentimentResult(
            symbol=symbol.strip().upper(),
            status="unavailable",
            summary="News sentiment analysis could not be completed.",
            evidence=[],
            limitations=["No usable news result was returned by the provider or analysis service."],
            source="Unavailable",
            fetched_at_utc=datetime.now(timezone.utc),
            sentiment_score=None,
            articles=[],
            data_warnings=["News evidence is unavailable for this session."],
        )
    else:
        news_result = news_res

    news_confidence = 0.0
    if (
        news_result.status not in ("insufficient_data", "unavailable")
        and news_result.sentiment_score is not None
    ):
        news_confidence = round(
            min(
                0.85,
                0.40
                + len(news_result.articles) * 0.03
                + abs(news_result.sentiment_score) * 0.2,
            ),
            2,
        )
    news_assessment = AgentAssessment(
        agent_name="News Sentiment Agent",
        status=news_result.status,
        summary=news_result.summary,
        evidence=news_result.evidence,
        limitations=news_result.limitations,
        source=news_result.source,
        is_demo=news_result.is_demo,
        agent_id="news_agent_01",
        latency_ms=round(news_lat, 1),
        confidence=news_confidence,
        confidence_method=(
            "Heuristic based on provider-sourced headline count and absolute "
            "lexical sentiment score; not a calibrated probability."
        ),
    )
    assessments.append(news_assessment)
    warnings.extend(news_result.data_warnings)

    if hist_res is None:
        warnings.append(
            "Historical volume data is unavailable; the volume signal is insufficient."
        )

    # Step 2: Signal Classification
    signals: list[StructuredSignal] = []
    sig_mom = classify_price_momentum(symbol, tech_res)
    signals.append(sig_mom)

    sig_vol = classify_volume_anomaly(symbol, hist_res.bars if hist_res else [])
    signals.append(sig_vol)

    sig_news = classify_news_sentiment_signal(symbol, news_result)
    signals.append(sig_news)

    sig_fund = classify_fundamental_health_signal(symbol, fundamental_metrics)
    signals.append(sig_fund)

    reasoning_trace.append(
        ReasoningStep(
            step_number=2,
            title="Multi-Dimensional Signal Classification",
            description="Derived independent momentum, volume anomaly, sentiment, and fundamental signals.",
            outcome=f"Evaluated 4 signals: Momentum={sig_mom.classification.value}, Volume={sig_vol.classification.value}, News={sig_news.classification.value}, Fund={sig_fund.classification.value}.",
            metadata={"signals_count": len(signals)},
        )
    )

    # Step 3: RAG Retrieval & Passage Grounding
    t_rag_start = time.perf_counter()
    citations: list[GroundedCitation] = []
    rag_latency_ms = 0.0
    evidence_claims_count = 0
    evidence_cited_claims_count = 0
    evidence_coverage_percent: float | None = None
    retrieval_status = "unavailable"

    owns_db = False
    active_db = db
    rag_issue: str | None = None
    if active_db is None:
        try:
            active_db = SessionLocal()
            owns_db = True
        except Exception as exc:
            active_db = None
            rag_issue = f"Database session unavailable ({type(exc).__name__})."

    if active_db is not None:
        try:
            # Retrieve context for actual structured agent evidence.
            claims_to_ground = list(news_assessment.evidence[:3])
            fundamental_assessment = next(
                (assessment for assessment in assessments
                 if assessment.agent_name == "Fundamental Agent"),
                None,
            )
            if fundamental_assessment is not None:
                claims_to_ground.extend(fundamental_assessment.evidence[:2])
            claims_to_ground = list(dict.fromkeys(claims_to_ground))
            evidence_claims_count = len(claims_to_ground)

            if claims_to_ground:
                citations = ground_agent_claims(
                    active_db,
                    symbol=symbol,
                    claims=claims_to_ground,
                )
                evidence_cited_claims_count = len(
                    {citation.claim for citation in citations}
                )
                retrieval_status = (
                    "completed" if citations else "no_relevant_evidence"
                )
                evidence_coverage_percent = round(
                    evidence_cited_claims_count / evidence_claims_count * 100.0,
                    1,
                )
                if not citations:
                    warnings.append(
                        "Document search completed, but no relevant passages matched the agent claims; no citations were attached."
                    )
                for assessment in assessments:
                    assessment.citations = [
                        citation for citation in citations
                        if citation.claim in assessment.evidence
                    ]
            else:
                retrieval_status = "no_agent_claims"
                warnings.append(
                    "No agent evidence claims were available to search; no citations were attached."
                )
        except Exception as exc:
            citations = []
            retrieval_status = "failed"
            rag_issue = f"Document retrieval failed ({type(exc).__name__})."
        finally:
            if owns_db:
                active_db.close()
    elif rag_issue is None:
        rag_issue = "Document retrieval unavailable because no database session could be opened."

    if rag_issue:
        warnings.append(
            "Financial document retrieval was unavailable; this analysis has no document context citations."
        )

    rag_latency_ms = (time.perf_counter() - t_rag_start) * 1000.0

    reasoning_trace.append(
        ReasoningStep(
            step_number=3,
            title="Financial Document Retrieval (RAG)",
            description=f"Searched the document corpus using BM25 for '{symbol}'.",
            outcome=(
                f"Retrieved {len(citations)} related passages; lexical relevance does not verify a claim."
                if retrieval_status == "completed"
                else (
                    "Search completed with no relevant passage matches; no citations were attached."
                    if retrieval_status == "no_relevant_evidence"
                    else (
                        "No agent claims were available to search; no citations were attached."
                        if retrieval_status == "no_agent_claims"
                        else "Document retrieval was unavailable; no citations were attached."
                    )
                )
            ),
            metadata={
                "citations_count": len(citations),
                "rag_latency_ms": round(rag_latency_ms, 1),
                "retrieval_issue": rag_issue or "",
                "retrieval_status": retrieval_status,
                "evidence_claims_count": evidence_claims_count,
                "evidence_cited_claims_count": evidence_cited_claims_count,
                "evidence_coverage_percent": evidence_coverage_percent,
                "evidence_coverage_definition": (
                    "Distinct agent evidence claims with at least one BM25 context passage / claims submitted; lexical coverage is not factual support."
                ),
            },
        )
    )

    # Step 4: Disagreement Detection
    disagreements = detect_disagreements(assessments)

    # Step 5: Deterministic Consensus Rules
    usable_assessments = [
        assessment
        for assessment in assessments
        if not assessment.is_demo
        and assessment.status in ("bullish", "bearish", "neutral")
    ]

    directional_assessments = [
        assessment
        for assessment in usable_assessments
        if assessment.status in ("bullish", "bearish")
    ]

    directional_statuses = {
        assessment.status
        for assessment in directional_assessments
    }

    if len(directional_statuses) > 1:
        overall_status = "neutral"
        analysis_note = (
            "Directional agents conflict: at least one is bullish and another "
            "is bearish. No shared direction is established; inspect the "
            "individual evidence and limitations."
        )

    elif len(directional_assessments) >= 2:
        overall_status = directional_assessments[0].status

        non_directional_assessments = [
            assessment
            for assessment in assessments
            if assessment.is_demo
            or assessment.status not in ("bullish", "bearish")
        ]

        if non_directional_assessments:
            other_agents = "; ".join(
                f"{assessment.agent_name}: "
                f"{assessment.status.replace('_', ' ')}"
                for assessment in non_directional_assessments
            )

            analysis_note = (
                "The available directional assessments agree, but this "
                "represents partial support rather than unanimous confirmation. "
                f"Other agent assessments: {other_agents}. "
                "This is not a validated prediction model."
            )
        else:
            analysis_note = (
                "All available agent assessments are directional and agree. "
                "This is not a validated consensus model or a prediction of "
                "future returns."
            )

    elif len(directional_assessments) == 1:
        if len(usable_assessments) > 1:
            overall_status = "neutral"
            analysis_note = (
                f"Only {directional_assessments[0].agent_name} established a "
                "directional assessment. Other usable agents do not confirm "
                "that direction, so multi-agent confirmation is lacking."
            )
        else:
            overall_status = directional_assessments[0].status
            analysis_note = (
                "Only one usable agent established a directional assessment. "
                "Its direction is provisional and is not multi-agent confirmation."
            )

    elif assessments and all(
        assessment.status in ("insufficient_data", "unavailable")
        or assessment.is_demo
        for assessment in assessments
    ):
        overall_status = "insufficient_data"
        analysis_note = (
            "Available agents could not establish a usable directional assessment."
        )

    else:
        overall_status = "neutral"
        analysis_note = (
            "The available agents do not establish a shared bullish or bearish "
            "direction. Neutral does not mean the investment is risk-free."
        )

    reasoning_trace.append(
        ReasoningStep(
            step_number=4,
            title="Deterministic Consensus & Disagreement Resolution",
            description="Evaluated directional agreement and conflict across specialized agents without arbitrary averaging.",
            outcome=f"Determined overall status: '{overall_status}'. Disagreements detected: {len(disagreements)}.",
            metadata={"overall_status": overall_status, "disagreements_count": len(disagreements)},
        )
    )

    # Step 6: Investor Personalization (Optional)
    personalized = None
    if profile_id:
        db_for_profile = db or SessionLocal()
        try:
            personalized = generate_personalized_interpretation(
                db=db_for_profile,
                profile_id=profile_id,
                symbol=symbol,
                overall_status=overall_status,
                technical=tech_res,
                fundamentals=fundamental_metrics,
            )
            if personalized:
                reasoning_trace.append(
                    ReasoningStep(
                        step_number=5,
                        title="Investor Profile Risk Personalization",
                        description=f"Generated portfolio-aware suitability context for '{personalized.profile_name}'.",
                        outcome=f"Assigned suitability: '{personalized.suitability_rating}'. Underlying market observations remained 100% unaltered.",
                        metadata={"profile_id": profile_id, "suitability": personalized.suitability_rating},
                    )
                )
        finally:
            if db is None:
                db_for_profile.close()

    total_latency_ms = (time.perf_counter() - start_total) * 1000.0

    required_agents = {
        "Technical Agent",
        "Fundamental Agent",
        "News Sentiment Agent",
    }
    available_assessments = {
        assessment.agent_name: assessment
        for assessment in assessments
        if assessment.status in ("bullish", "bearish", "neutral")
        and not assessment.is_demo
    }
    analysis_completeness = (
        "complete"
        if required_agents.issubset(available_assessments)
        else "partial"
    )

    # Step 7: Final Informational Synthesis
    reasoning_trace.append(
        ReasoningStep(
            step_number=6,
            title="Informational Synthesis & Provenance Verification",
            description="Compiled structured intelligence payload with source attribution and limitation warnings.",
            outcome=f"Analysis completed in {total_latency_ms:.1f}ms. Ready for research inspection.",
            metadata={"total_latency_ms": round(total_latency_ms, 1)},
        )
    )

    analysis_res = IntelligenceAnalysis(
        symbol=getattr(tech_res, "symbol", symbol).upper(),
        generated_at_utc=datetime.now(timezone.utc),
        overall_status=overall_status,
        analysis_completeness=analysis_completeness,
        assessments=assessments,
        disagreements=disagreements,
        data_warnings=list(dict.fromkeys(warnings)),
        analysis_note=analysis_note,
        news_sentiment_score=news_result.sentiment_score,
        news_fetched_at_utc=news_result.fetched_at_utc,
        news_articles=news_result.articles,
        session_id=session_id,
        total_latency_ms=round(total_latency_ms, 1),
        rag_latency_ms=round(rag_latency_ms, 1),
        evidence_claims_count=evidence_claims_count,
        evidence_cited_claims_count=evidence_cited_claims_count,
        evidence_coverage_percent=evidence_coverage_percent,
        signals=signals,
        citations=citations,
        reasoning_trace=reasoning_trace,
        personalized_interpretation=personalized,
        profile_id=profile_id,
    )

    # Persist session and log evaluation if db is available
    db_to_persist = db or SessionLocal()
    try:
        from app.services.evaluation import record_analysis_session, record_signal_evaluation
        record_analysis_session(
            db=db_to_persist,
            session_id=session_id,
            symbol=analysis_res.symbol,
            overall_classification=analysis_res.overall_status,
            total_latency_ms=analysis_res.total_latency_ms,
            rag_latency_ms=analysis_res.rag_latency_ms,
            agents_data=[a.model_dump() for a in analysis_res.assessments],
            disagreements_data=[d.model_dump() for d in analysis_res.disagreements],
            signals_data=[s.model_dump() for s in analysis_res.signals],
            citations_data=[c.model_dump() for c in analysis_res.citations],
            reasoning_trace=[r.model_dump() for r in analysis_res.reasoning_trace],
            personalized_interpretation=analysis_res.personalized_interpretation.model_dump() if analysis_res.personalized_interpretation else None,
            profile_id=profile_id,
            owner_id=owner_id,
        )
        # Only score complete, real-data analyses. Partial or synthetic
        # sessions remain in the audit trail but are not comparable as
        # complete real-world predictions.
        if (
            analysis_res.analysis_completeness == "complete"
            and not any(assessment.is_demo for assessment in analysis_res.assessments)
            and hasattr(tech_res, "latest_close")
            and tech_res.latest_close
        ):
            record_signal_evaluation(
                db=db_to_persist,
                symbol=analysis_res.symbol,
                signal_classification=analysis_res.overall_status,
                signal_dimension="synthesis",
                entry_price=tech_res.latest_close,
                signal_timestamp=analysis_res.generated_at_utc,
                evaluation_horizon_days=30,
                session_id=session_id,
                owner_id=owner_id,
            )
    except Exception as exc:
        logger.warning(
            "Analysis persistence failed (%s); analysis result is returned without a saved audit record",
            type(exc).__name__,
        )
        analysis_res.data_warnings.append(
            "The analysis completed but its audit record could not be saved."
        )
        if db_to_persist is not None:
            db_to_persist.rollback()
    finally:
        if db is None:
            db_to_persist.close()

    return analysis_res
