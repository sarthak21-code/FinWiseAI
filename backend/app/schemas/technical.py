from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TechnicalAnalysis(BaseModel):
    symbol: str

    latest_close: float = Field(gt=0)
    latest_trading_day: str
    calculated_at_utc: datetime

    sma_20: float | None = None
    sma_50: float | None = None

    rsi_14: float | None = Field(default=None, ge=0, le=100)

    momentum_20d_percent: float | None = None
    daily_volatility_percent: float | None = None

    technical_bias: Literal[
        "bullish",
        "bearish",
        "neutral",
        "insufficient_data",
    ]

    evidence: list[str] = Field(default_factory=list)

    source: str
    is_demo: bool
    data_note: str