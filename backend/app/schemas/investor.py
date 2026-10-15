from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InvestorProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    risk_tolerance: int = Field(
        default=3,
        ge=1,
        le=5,
    )

    investment_horizon_months: int = Field(
        default=12,
        ge=1,
        le=600,
    )

    max_single_asset_allocation: float = Field(
        default=0.20,
        gt=0,
        le=1,
    )

    investment_objective: str = Field(
        default="Capital Growth",
        max_length=120,
    )


class InvestorProfileResponse(BaseModel):
    id: str
    name: str
    risk_tolerance: int
    investment_horizon_months: int
    max_single_asset_allocation: float
    investment_objective: str = "Capital Growth"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioHoldingCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    shares: float = Field(ge=0.0, default=0.0)
    weight: float = Field(ge=0.0, le=1.0, default=0.0)
    cost_basis: Optional[float] = None
    asset_category: str = Field(default="Equity", max_length=60)
    is_watchlist: bool = False


class PortfolioHoldingResponse(BaseModel):
    id: str
    profile_id: str
    symbol: str
    shares: float
    weight: float
    cost_basis: Optional[float] = None
    asset_category: str
    is_watchlist: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioRiskMetrics(BaseModel):
    profile_id: str
    profile_name: str
    risk_tolerance: int
    investment_horizon_months: int
    investment_objective: str
    total_holdings_count: int
    hhi_score: float
    concentration_level: str  # Low, Moderate, High
    largest_position_symbol: Optional[str] = None
    largest_position_weight: float = 0.0
    max_allocation_limit: float = 0.20
    allocation_breached: bool = False
    warnings: list[str] = Field(default_factory=list)
    holdings: list[PortfolioHoldingResponse] = Field(default_factory=list)
    watchlist: list[PortfolioHoldingResponse] = Field(default_factory=list)


class PersonalizedAnalysis(BaseModel):
    profile_id: str
    profile_name: str
    risk_tolerance: int
    suitability_rating: str  # "Suitable", "Caution / High Volatility", "Unsuitable"
    risk_emphasis: str
    portfolio_impact_analysis: str
    concentration_warning: Optional[str] = None
    suggested_investor_questions: list[str] = Field(default_factory=list)
    underlying_market_facts_unaltered: bool = True