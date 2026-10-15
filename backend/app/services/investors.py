from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.investor import InvestorProfile, PortfolioHolding
from app.schemas.investor import (
    InvestorProfileCreate,
    PersonalizedAnalysis,
    PortfolioHoldingCreate,
    PortfolioHoldingResponse,
    PortfolioRiskMetrics,
)


def create_investor_profile(
    db: Session,
    profile_data: InvestorProfileCreate,
) -> InvestorProfile:
    name_clean = profile_data.name.strip()
    if not name_clean:
        raise ValueError("Name cannot contain only whitespace.")

    profile = InvestorProfile(
        name=name_clean,
        risk_tolerance=profile_data.risk_tolerance,
        investment_horizon_months=profile_data.investment_horizon_months,
        max_single_asset_allocation=profile_data.max_single_asset_allocation,
        investment_objective=profile_data.investment_objective.strip() or "Capital Growth",
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def list_investor_profiles(db: Session) -> list[InvestorProfile]:
    return list(
        db.query(InvestorProfile)
        .order_by(InvestorProfile.created_at.desc())
        .all()
    )


def get_investor_profile(db: Session, profile_id: str) -> InvestorProfile | None:
    return db.get(InvestorProfile, profile_id)


def add_portfolio_holding(
    db: Session,
    profile_id: str,
    holding_data: PortfolioHoldingCreate,
) -> PortfolioHolding:
    profile = db.get(InvestorProfile, profile_id)
    if not profile:
        raise ValueError(f"Investor profile {profile_id} not found.")

    holding = PortfolioHolding(
        profile_id=profile_id,
        symbol=holding_data.symbol.strip().upper(),
        shares=holding_data.shares,
        weight=holding_data.weight,
        cost_basis=holding_data.cost_basis,
        asset_category=holding_data.asset_category.strip() or "Equity",
        is_watchlist=holding_data.is_watchlist,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


def list_portfolio_holdings(
    db: Session,
    profile_id: str,
) -> list[PortfolioHolding]:
    return list(
        db.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.profile_id == profile_id)
            .order_by(PortfolioHolding.weight.desc())
        ).scalars().all()
    )


def calculate_portfolio_risk(
    db: Session,
    profile_id: str,
) -> PortfolioRiskMetrics:
    """Calculate portfolio concentration using the Herfindahl-Hirschman Index (HHI)."""
    profile = db.get(InvestorProfile, profile_id)
    if not profile:
        raise ValueError(f"Investor profile {profile_id} not found.")

    all_items = list_portfolio_holdings(db, profile_id)
    holdings = [item for item in all_items if not item.is_watchlist]
    watchlist = [item for item in all_items if item.is_watchlist]

    # Convert to response objects
    holding_responses = [PortfolioHoldingResponse.model_validate(h) for h in holdings]
    watchlist_responses = [PortfolioHoldingResponse.model_validate(w) for w in watchlist]

    if not holdings:
        return PortfolioRiskMetrics(
            profile_id=profile.id,
            profile_name=profile.name,
            risk_tolerance=profile.risk_tolerance,
            investment_horizon_months=profile.investment_horizon_months,
            investment_objective=profile.investment_objective,
            total_holdings_count=0,
            hhi_score=0.0,
            concentration_level="No Holdings Recorded",
            largest_position_symbol=None,
            largest_position_weight=0.0,
            max_allocation_limit=profile.max_single_asset_allocation,
            allocation_breached=False,
            warnings=["No active portfolio positions found for this profile."],
            holdings=[],
            watchlist=watchlist_responses,
        )

    # Normalize weights so sum of weights equals 1.0
    raw_weights = [h.weight for h in holdings]
    total_weight = sum(raw_weights)
    if total_weight > 0:
        normalized_weights = [w / total_weight for w in raw_weights]
    else:
        # Equal weighted if unspecified
        normalized_weights = [1.0 / len(holdings)] * len(holdings)

    # Herfindahl-Hirschman Index: sum of squared fraction weights
    hhi = sum(w ** 2 for w in normalized_weights)

    # Find largest position
    max_idx = max(range(len(normalized_weights)), key=lambda i: normalized_weights[i])
    largest_sym = holdings[max_idx].symbol
    largest_weight = normalized_weights[max_idx]

    # Classification: HHI < 0.15 is low, 0.15-0.25 is moderate, > 0.25 is high
    if hhi < 0.15:
        concentration_level = "Low Concentration (Well Diversified)"
    elif hhi <= 0.25:
        concentration_level = "Moderate Concentration"
    else:
        concentration_level = "High Concentration (Cluster Risk)"

    warnings: list[str] = []
    allocation_breached = largest_weight > profile.max_single_asset_allocation
    if allocation_breached:
        warnings.append(
            f"Largest position in {largest_sym} ({largest_weight * 100:.1f}%) exceeds "
            f"profile's max single-asset allocation limit of {profile.max_single_asset_allocation * 100:.1f}%."
        )

    if hhi > 0.25:
        warnings.append(
            f"High portfolio concentration detected (HHI: {hhi:.3f}). "
            "Downside events in top holdings will heavily impact total portfolio value."
        )

    return PortfolioRiskMetrics(
        profile_id=profile.id,
        profile_name=profile.name,
        risk_tolerance=profile.risk_tolerance,
        investment_horizon_months=profile.investment_horizon_months,
        investment_objective=profile.investment_objective,
        total_holdings_count=len(holdings),
        hhi_score=round(hhi, 3),
        concentration_level=concentration_level,
        largest_position_symbol=largest_sym,
        largest_position_weight=round(largest_weight, 3),
        max_allocation_limit=profile.max_single_asset_allocation,
        allocation_breached=allocation_breached,
        warnings=warnings,
        holdings=holding_responses,
        watchlist=watchlist_responses,
    )


def generate_personalized_interpretation(
    db: Session,
    profile_id: Optional[str],
    symbol: str,
    overall_status: str,
    technical: any = None,
    fundamentals: any = None,
) -> Optional[PersonalizedAnalysis]:
    """Generate investor-specific risk context and suitability without altering factual market data."""
    if not profile_id:
        return None

    profile = db.get(InvestorProfile, profile_id)
    if not profile:
        return None

    risk_metrics = calculate_portfolio_risk(db, profile_id)
    clean_sym = symbol.strip().upper()

    # Check if stock is already in portfolio
    existing_holding = next(
        (h for h in risk_metrics.holdings if h.symbol.upper() == clean_sym),
        None,
    )

    is_conservative = profile.risk_tolerance <= 2
    is_aggressive = profile.risk_tolerance >= 4

    volatility = getattr(technical, "daily_volatility_percent", 1.5) or 1.5
    rsi = getattr(technical, "rsi_14", 50.0) or 50.0

    questions: list[str] = []

    if is_conservative:
        if volatility > 2.2 or rsi > 70 or overall_status == "bearish":
            suitability = "Caution / High Volatility for Conservative Mandate"
            risk_emphasis = (
                f"Elevated price fluctuation ({volatility:.1f}% daily volatility) conflicts with "
                f"conservative capital preservation mandate (Risk Score: {profile.risk_tolerance}/5). "
                f"Focus should remain on downside mitigation and drawdown thresholds."
            )
        else:
            suitability = "Conditional Suitability for Defensive Allocation"
            risk_emphasis = (
                f"Acceptable volatility profile within conservative constraints. "
                f"Any position sizing should remain strictly below {profile.max_single_asset_allocation * 100:.0f}% limit."
            )

        questions = [
            f"Does {clean_sym}'s cash flow or dividend yield offer a buffer against cyclical multiple contraction?",
            f"What is the maximum portfolio drawdown if {clean_sym} experiences a 20% correction?",
            f"Would capital be more defensively deployed in short-duration liquid instruments given current market regime?",
        ]

    elif is_aggressive:
        suitability = "Suitable for Growth Mandate"
        risk_emphasis = (
            f"Compatible with high risk tolerance ({profile.risk_tolerance}/5) and {profile.investment_horizon_months}-month "
            f"horizon. Aggressive mandate accepts elevated volatility ({volatility:.1f}%) in exchange for upside potential."
        )
        questions = [
            f"Does {clean_sym}'s market expansion justify current valuation multiples over a {profile.investment_horizon_months}-month horizon?",
            f"Is {clean_sym} exposed to semiconductor or regulatory bottlenecks that could constrain growth velocity?",
            f"How does adding {clean_sym} affect the overall growth beta of the active equity basket?",
        ]
    else:
        # Moderate
        suitability = "Balanced Suitability"
        risk_emphasis = (
            f"Moderately aligned with balanced risk tolerance ({profile.risk_tolerance}/5). "
            f"Portfolio impact depends on position sizing relative to {profile.max_single_asset_allocation * 100:.0f}% ceiling."
        )
        questions = [
            f"Does {clean_sym} align with your target sector allocation?",
            f"Have you evaluated potential correlation with other technology or cyclical holdings?",
        ]

    # Portfolio impact analysis
    if existing_holding:
        portfolio_impact = (
            f"{clean_sym} is currently held at {existing_holding.weight * 100:.1f}% of total portfolio. "
            f"Adding exposure would raise position weight closer to or above your "
            f"{profile.max_single_asset_allocation * 100:.0f}% maximum single-asset threshold."
        )
    else:
        portfolio_impact = (
            f"{clean_sym} is a new position candidate. With current portfolio concentration at HHI {risk_metrics.hhi_score:.3f} "
            f"({risk_metrics.concentration_level}), introducing {clean_sym} up to "
            f"{profile.max_single_asset_allocation * 100:.0f}% can assist diversification if non-correlated."
        )

    return PersonalizedAnalysis(
        profile_id=profile.id,
        profile_name=profile.name,
        risk_tolerance=profile.risk_tolerance,
        suitability_rating=suitability,
        risk_emphasis=risk_emphasis,
        portfolio_impact_analysis=portfolio_impact,
        concentration_warning=risk_metrics.warnings[0] if risk_metrics.warnings else None,
        suggested_investor_questions=questions,
        underlying_market_facts_unaltered=True,
    )


def seed_default_investor_profiles(db: Session) -> list[InvestorProfile]:
    """Seed demo profiles: Conservative vs Aggressive with realistic portfolios."""
    prof_a = db.get(InvestorProfile, "demo_profile_conservative")
    if not prof_a:
        prof_a = InvestorProfile(
            id="demo_profile_conservative",
            name="Conservative Capital Preservation",
            risk_tolerance=1,
            investment_horizon_months=36,
            max_single_asset_allocation=0.15,
            investment_objective="Capital Preservation & Fixed Income",
        )
        db.add(prof_a)
        db.flush()

        holdings_a = [
            PortfolioHolding(profile_id=prof_a.id, symbol="AAPL", shares=25, weight=0.12, cost_basis=185.0, asset_category="Technology"),
            PortfolioHolding(profile_id=prof_a.id, symbol="JNJ", shares=60, weight=0.25, cost_basis=155.0, asset_category="Healthcare"),
            PortfolioHolding(profile_id=prof_a.id, symbol="PG", shares=50, weight=0.23, cost_basis=160.0, asset_category="Consumer Staples"),
            PortfolioHolding(profile_id=prof_a.id, symbol="SHV", shares=400, weight=0.40, cost_basis=110.0, asset_category="Treasury / Cash"),
        ]
        for h in holdings_a:
            db.add(h)

    prof_b = db.get(InvestorProfile, "demo_profile_aggressive")
    if not prof_b:
        prof_b = InvestorProfile(
            id="demo_profile_aggressive",
            name="Aggressive Growth Investor",
            risk_tolerance=5,
            investment_horizon_months=60,
            max_single_asset_allocation=0.35,
            investment_objective="High-Beta Growth & Tech Expansion",
        )
        db.add(prof_b)
        db.flush()

        holdings_b = [
            PortfolioHolding(profile_id=prof_b.id, symbol="NVDA", shares=150, weight=0.35, cost_basis=95.0, asset_category="Semiconductors"),
            PortfolioHolding(profile_id=prof_b.id, symbol="MSFT", shares=80, weight=0.30, cost_basis=390.0, asset_category="Cloud Software"),
            PortfolioHolding(profile_id=prof_b.id, symbol="TSLA", shares=100, weight=0.20, cost_basis=210.0, asset_category="Automotive EV"),
            PortfolioHolding(profile_id=prof_b.id, symbol="AMZN", shares=75, weight=0.15, cost_basis=175.0, asset_category="E-Commerce / Cloud"),
        ]
        for h in holdings_b:
            db.add(h)

    db.commit()
    db.refresh(prof_a)
    db.refresh(prof_b)
    return [prof_a, prof_b]