
from datetime import datetime

from pydantic import BaseModel, Field


class FundamentalMetrics(BaseModel):
    symbol: str
    company_name: str | None = None
    currency: str | None = None

    fiscal_year: str | None = None
    fiscal_period: str | None = None

    revenue: float | None = None
    revenue_growth_percent: float | None = None

    net_income: float | None = None
    net_margin_percent: float | None = None

    return_on_equity_percent: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None

    pe_ratio: float | None = None
    eps: float | None = None

    source: str
    fetched_at_utc: datetime
    is_demo: bool = False

    data_warnings: list[str] = Field(default_factory=list)

