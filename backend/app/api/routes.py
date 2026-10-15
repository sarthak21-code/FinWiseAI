import json
import secrets
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth import get_current_user
from app.db.session import get_db, set_database_context
from app.models.document import DocumentChunk, FinancialDocument
from app.models.session import AnalysisSession
from app.models.user import UserIdentity
from app.models.investor import InvestorProfile
from app.schemas.fundamental import FundamentalMetrics
from app.schemas.intelligence import (
    AnalyzeRequest,
    CompareProfilesRequest,
    IntelligenceAnalysis,
    ProfileComparisonResponse,
)
from app.schemas.investor import (
    InvestorProfileCreate,
    InvestorProfileResponse,
    PortfolioHoldingCreate,
    PortfolioHoldingResponse,
    PortfolioRiskMetrics,
)
from app.schemas.market import (
    HistoricalPriceResponse,
    MarketQuote,
)
from app.schemas.signals import SignalDimension
from app.schemas.rag import DocumentSearchResult
from app.schemas.technical import TechnicalAnalysis
from app.services.evaluation import (
    get_evaluation_metrics,
    seed_historical_evaluations,
    update_matured_evaluations,
)
from app.services.fundamental_analysis import (
    FundamentalDataUnavailable,
    fetch_fundamental_metrics,
)
from app.services.historical_prices import (
    HistoricalDataUnavailable,
    get_historical_prices,
)
from app.services.intelligence import analyze_symbol
from app.services.investors import (
    add_portfolio_holding,
    calculate_portfolio_risk,
    create_investor_profile,
    generate_personalized_interpretation,
    get_investor_profile,
    list_investor_profiles,
    list_portfolio_holdings,
    seed_default_investor_profiles,
)
from app.services.market_data import (
    InvalidMarketSymbol,
    MarketDataUnavailable,
    get_market_quote,
)
from app.services.rag import (
    search_documents,
    seed_demonstration_corpus,
)
from app.services.technical_analysis import get_technical_analysis

router = APIRouter(prefix="/api/v1")


def _accessible_profile(
    db: Session,
    profile_id: str,
    user: UserIdentity,
    *,
    allow_demo: bool,
) -> InvestorProfile | None:
    ownership = [InvestorProfile.owner_id == user.id]
    if allow_demo:
        ownership.append(InvestorProfile.is_demo.is_(True))
    return db.execute(
        select(InvestorProfile).where(
            InvestorProfile.id == profile_id,
            or_(*ownership),
        )
    ).scalar_one_or_none()


@router.get("/users/me")
def read_current_user(user: UserIdentity = Depends(get_current_user)):
    return {"id": user.id, "issuer": user.issuer, "subject": user.subject}


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "application": settings.app_name,
        "version": settings.app_version,
        "database": "connected",
    }


# ==========================================
# Market Data & History
# ==========================================

@router.get("/market/quote/{symbol}", response_model=MarketQuote)
async def read_market_quote(symbol: str):
    try:
        return await get_market_quote(symbol)
    except InvalidMarketSymbol as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/market/history/{symbol}", response_model=HistoricalPriceResponse)
async def read_historical_prices(symbol: str):
    try:
        history = await get_historical_prices(symbol)
        return {
            "symbol": history.symbol,
            "bars": [
                {
                    "trading_day": bar.trading_day,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in history.bars
            ],
            "source": history.source,
            "fetched_at_utc": history.fetched_at_utc,
            "data_note": history.data_note,
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HistoricalDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/market/technical/{symbol}", response_model=TechnicalAnalysis)
async def read_technical_analysis(symbol: str):
    try:
        return await get_technical_analysis(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/market/fundamental/{symbol}", response_model=FundamentalMetrics)
async def read_fundamental_analysis(symbol: str):
    try:
        return await fetch_fundamental_metrics(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FundamentalDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ==========================================
# Multi-Agent Intelligence & Analysis
# ==========================================

@router.get("/intelligence/analyze/{symbol}", response_model=IntelligenceAnalysis)
async def read_intelligence_analysis(
    symbol: str,
    profile_id: Optional[str] = Query(default=None),
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if profile_id and not _accessible_profile(db, profile_id, user, allow_demo=True):
        raise HTTPException(status_code=404, detail="Investor profile not found")
    try:
        return await analyze_symbol(
            symbol=symbol, profile_id=profile_id, db=db, owner_id=user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/intelligence/analyze", response_model=IntelligenceAnalysis)
async def post_intelligence_analysis(
    payload: AnalyzeRequest,
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.profile_id and not _accessible_profile(
        db, payload.profile_id, user, allow_demo=True
    ):
        raise HTTPException(status_code=404, detail="Investor profile not found")
    try:
        return await analyze_symbol(
            symbol=payload.symbol,
            profile_id=payload.profile_id,
            db=db,
            owner_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/intelligence/compare-profiles", response_model=ProfileComparisonResponse)
async def compare_profiles(
    payload: CompareProfilesRequest,
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run an identical market observation snapshot against two distinct investor profiles."""
    prof_a = _accessible_profile(db, payload.profile_a_id, user, allow_demo=True)
    prof_b = _accessible_profile(db, payload.profile_b_id, user, allow_demo=True)
    if not prof_a or not prof_b:
        raise HTTPException(status_code=404, detail="Investor profile not found")
    try:
        analysis = await analyze_symbol(
            symbol=payload.symbol, profile_id=None, db=db, owner_id=user.id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Market snapshot retrieval failed; provider details are withheld.",
        ) from exc

    technical_signal = next(
        (
            signal
            for signal in analysis.signals
            if signal.dimension == SignalDimension.PRICE_MOMENTUM
        ),
        None,
    )
    technical_context = (
        SimpleNamespace(
            daily_volatility_percent=technical_signal.metrics.get("volatility_daily"),
            rsi_14=technical_signal.metrics.get("rsi_14"),
        )
        if technical_signal is not None
        else None
    )

    interp_a = generate_personalized_interpretation(
        db=db,
        profile_id=payload.profile_a_id,
        symbol=payload.symbol,
        overall_status=analysis.overall_status,
        technical=technical_context,
    )

    interp_b = generate_personalized_interpretation(
        db=db,
        profile_id=payload.profile_b_id,
        symbol=payload.symbol,
        overall_status=analysis.overall_status,
        technical=technical_context,
    )

    summary = (
        f"Compared {payload.symbol} under identical market evidence (Status: {analysis.overall_status}). "
        f"{prof_a.name} (Risk: {prof_a.risk_tolerance}/5) received suitability rating '{interp_a.suitability_rating}', "
        f"whereas {prof_b.name} (Risk: {prof_b.risk_tolerance}/5) received '{interp_b.suitability_rating}'. "
        "Underlying market prices, indicators, and filings remained 100% identical."
    )

    return ProfileComparisonResponse(
        symbol=payload.symbol.upper(),
        market_facts_unaltered=True,
        overall_status=analysis.overall_status,
        profile_a=interp_a,
        profile_b=interp_b,
        comparison_summary=summary,
    )


@router.get("/intelligence/sessions")
def list_analysis_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = db.execute(
        select(AnalysisSession)
        .where(AnalysisSession.owner_id == user.id)
        .order_by(desc(AnalysisSession.created_at)).limit(limit)
    ).scalars().all()

    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "status": s.status,
            "overall_classification": s.overall_classification,
            "total_latency_ms": s.total_latency_ms,
            "rag_latency_ms": s.rag_latency_ms,
            "profile_id": s.profile_id,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


@router.get("/intelligence/sessions/{session_id}")
def get_analysis_session_detail(
    session_id: str,
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.execute(
        select(AnalysisSession).where(
            AnalysisSession.id == session_id,
            AnalysisSession.owner_id == user.id,
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": session.id,
        "symbol": session.symbol,
        "status": session.status,
        "overall_classification": session.overall_classification,
        "total_latency_ms": session.total_latency_ms,
        "rag_latency_ms": session.rag_latency_ms,
        "agents": json.loads(session.agents_data),
        "disagreements": json.loads(session.disagreements_data),
        "signals": json.loads(session.signals_data),
        "citations": json.loads(session.citations_data),
        "reasoning_trace": json.loads(session.reasoning_trace),
        "personalized_interpretation": json.loads(session.personalized_interpretation),
        "created_at": session.created_at.isoformat(),
    }


@router.get("/intelligence/evaluation")
def read_evaluation_metrics(
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve session latency, 30-day forward return evaluations, and system accuracy benchmarks."""
    return get_evaluation_metrics(db, owner_id=user.id)


@router.post("/intelligence/evaluation/update")
async def update_evaluation_outcomes(
    limit: int = Query(default=100, ge=1, le=500),
    update_token: Optional[str] = Header(default=None, alias="X-Evaluation-Update-Token"),
    db: Session = Depends(get_db),
):
    """Protected, explicit trigger for retrying matured real outcomes.

    This endpoint is disabled unless an operational token is configured. It
    does not run automatically and must be invoked by a trusted operator.
    """
    expected_token = settings.evaluation_update_token
    if not expected_token or not update_token or not secrets.compare_digest(
        expected_token, update_token
    ):
        raise HTTPException(status_code=404, detail="Not found")
    set_database_context(db, operator=True)
    return await update_matured_evaluations(db, limit=limit)


# ==========================================
# Financial-Document RAG Corpus & Search
# ==========================================

@router.get("/documents/search", response_model=list[DocumentSearchResult])
def search_financial_documents(
    q: str = Query(min_length=1, max_length=200),
    symbol: Optional[str] = Query(default=None),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return search_documents(db=db, query=q, symbol=symbol, top_k=top_k)


@router.get("/documents/{document_id}")
def get_document_detail(
    document_id: str,
    db: Session = Depends(get_db),
):
    doc = db.get(FinancialDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Financial document not found")

    chunks = db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    ).scalars().all()

    return {
        "id": doc.id,
        "issuer": doc.issuer,
        "ticker": doc.ticker,
        "title": doc.title,
        "document_type": doc.document_type,
        "reporting_period": doc.reporting_period,
        "published_at": doc.published_at.isoformat(),
        "source_name": doc.source_name,
        "source_url": doc.source_url,
        "synthetic": doc.synthetic,
        "raw_content": doc.raw_content,
        "chunks": [
            {
                "chunk_id": c.id,
                "chunk_index": c.chunk_index,
                "section": c.section,
                "text": c.text,
                "token_count": c.token_count,
            }
            for c in chunks
        ],
    }


# ==========================================
# Investor Profiles & Portfolios
# ==========================================

@router.post(
    "/investors",
    response_model=InvestorProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/profiles",
    response_model=InvestorProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_investor(
    payload: InvestorProfileCreate,
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return create_investor_profile(db, payload, owner_id=user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/investors",
    response_model=list[InvestorProfileResponse],
)
@router.get(
    "/profiles",
    response_model=list[InvestorProfileResponse],
)
def list_investors(
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_investor_profiles(db, owner_id=user.id)


@router.get(
    "/investors/{profile_id}",
    response_model=InvestorProfileResponse,
)
@router.get(
    "/profiles/{profile_id}",
    response_model=InvestorProfileResponse,
)
def get_investor(
    profile_id: str,
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    investor = _accessible_profile(db, profile_id, user, allow_demo=True)
    if investor is None:
        raise HTTPException(status_code=404, detail="Investor profile not found")
    return investor


@router.get(
    "/profiles/{profile_id}/portfolio",
    response_model=PortfolioRiskMetrics,
)
def get_profile_portfolio(
    profile_id: str,
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _accessible_profile(db, profile_id, user, allow_demo=True):
        raise HTTPException(status_code=404, detail="Investor profile not found")
    try:
        return calculate_portfolio_risk(db, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/profiles/{profile_id}/holdings",
    response_model=PortfolioHoldingResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_holding(
    profile_id: str,
    payload: PortfolioHoldingCreate,
    user: UserIdentity = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _accessible_profile(db, profile_id, user, allow_demo=False):
        raise HTTPException(status_code=404, detail="Investor profile not found")
    try:
        return add_portfolio_holding(db, profile_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ==========================================
# Demonstration Seeding
# ==========================================

@router.post("/demo/seed")
def seed_demo_environment(
    seed_token: Optional[str] = Header(default=None, alias="X-Demo-Seed-Token"),
    db: Session = Depends(get_db),
):
    """Seed demo records only when an operator token is configured."""
    expected_token = settings.demo_seed_token
    if not expected_token or not seed_token or not secrets.compare_digest(
        expected_token, seed_token
    ):
        raise HTTPException(status_code=404, detail="Not found")

    set_database_context(db, operator=True)
    doc_count = seed_demonstration_corpus(db)
    profs = seed_default_investor_profiles(db)
    eval_count = seed_historical_evaluations(db)

    return {
        "status": "success",
        "documents_seeded": doc_count,
        "profiles_seeded": len(profs),
        "historical_evaluations_seeded": eval_count,
        "message": "Demonstration environment primed with synthetic filing-style passages, profiles, and illustrative evaluation examples.",
    }
