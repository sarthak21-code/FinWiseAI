from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


NewsLabel = Literal["positive", "negative", "neutral"]
NewsStatus = Literal[
    "bullish",
    "bearish",
    "neutral",
    "insufficient_data",
    "unavailable",
]


class NewsArticleSummary(BaseModel):
    id: str | None = None
    title: str
    publisher: str | None = None
    link: str | None = None
    published_at_utc: datetime
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    sentiment_label: NewsLabel
    relevance_score: float = Field(ge=0.0, le=1.0)
    related_tickers: list[str] = Field(default_factory=list)


class NewsSentimentResult(BaseModel):
    symbol: str
    status: NewsStatus
    summary: str
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source: str
    fetched_at_utc: datetime
    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    articles: list[NewsArticleSummary] = Field(default_factory=list)
    data_warnings: list[str] = Field(default_factory=list)
    is_demo: bool = False
