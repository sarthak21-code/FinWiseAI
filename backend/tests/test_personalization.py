import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.investor import InvestorProfile, PortfolioHolding
from app.schemas.technical import TechnicalAnalysis
from app.services.investors import (
    calculate_portfolio_risk,
    generate_personalized_interpretation,
    seed_default_investor_profiles,
)


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def test_hhi_calculation_and_concentration_levels(in_memory_db):
    prof = InvestorProfile(
        id="test_prof",
        name="Test Diversified",
        risk_tolerance=3,
        investment_horizon_months=12,
        max_single_asset_allocation=0.25,
        investment_objective="Growth",
    )
    in_memory_db.add(prof)

    # 4 equal holdings of 25% each -> HHI = 4 * (0.25)^2 = 0.25
    for sym in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
        in_memory_db.add(
            PortfolioHolding(profile_id=prof.id, symbol=sym, shares=10, weight=0.25)
        )
    in_memory_db.commit()

    risk = calculate_portfolio_risk(in_memory_db, prof.id)
    assert risk.hhi_score == 0.25
    assert risk.total_holdings_count == 4
    assert not risk.allocation_breached


def test_identical_market_facts_produce_different_personalizations(in_memory_db):
    profs = seed_default_investor_profiles(in_memory_db)
    prof_cons = next(p for p in profs if p.id == "demo_profile_conservative")
    prof_aggr = next(p for p in profs if p.id == "demo_profile_aggressive")

    # Pass exactly the same non-null market snapshot to both profile interpretations.
    technical_snapshot = TechnicalAnalysis(
        symbol="NVDA",
        latest_close=140.0,
        latest_trading_day="2026-10-14",
        calculated_at_utc=datetime.now(timezone.utc),
        sma_20=135.0,
        sma_50=128.0,
        rsi_14=62.0,
        momentum_20d_percent=4.0,
        daily_volatility_percent=2.4,
        technical_bias="bullish",
        evidence=["Fixed technical fixture used for both profiles."],
        source="Deterministic profile comparison fixture",
        is_demo=False,
        data_note="Same immutable test snapshot.",
    )
    market_snapshot_before = technical_snapshot.model_dump()

    interp_cons = generate_personalized_interpretation(
        db=in_memory_db,
        profile_id=prof_cons.id,
        symbol="NVDA",
        overall_status="bullish",
        technical=technical_snapshot,
    )

    interp_aggr = generate_personalized_interpretation(
        db=in_memory_db,
        profile_id=prof_aggr.id,
        symbol="NVDA",
        overall_status="bullish",
        technical=technical_snapshot,
    )

    assert interp_cons is not None
    assert interp_aggr is not None
    assert interp_cons.underlying_market_facts_unaltered is True
    assert interp_aggr.underlying_market_facts_unaltered is True

    # Suitability and risk emphasis must differ based on risk tolerance
    assert interp_cons.risk_tolerance == 1
    assert interp_aggr.risk_tolerance == 5
    assert interp_cons.suitability_rating != interp_aggr.suitability_rating
    assert "conservative" in interp_cons.risk_emphasis.lower()
    assert "aggressive" in interp_aggr.risk_emphasis.lower()
    assert technical_snapshot.model_dump() == market_snapshot_before
