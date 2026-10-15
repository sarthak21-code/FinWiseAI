from datetime import datetime

from pydantic import BaseModel, Field


class MarketQuote(BaseModel):
    symbol: str

    price: float = Field(gt=0)
    change: float
    change_percent: float

    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    volume: int | None = Field(default=None, ge=0)

    currency: str | None = None
    latest_trading_day: str
    fetched_at_utc: datetime

    source: str
    is_demo: bool
    data_note: str


class HistoricalBarModel(BaseModel):
    trading_day: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None


class HistoricalPriceResponse(BaseModel):
    symbol: str
    bars: list[HistoricalBarModel]
    source: str
    fetched_at_utc: datetime
    data_note: str