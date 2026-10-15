from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SignalDimension(str, Enum):
    PRICE_MOMENTUM = "price_momentum"
    VOLUME_ANOMALY = "volume_anomaly"
    NEWS_SENTIMENT = "news_sentiment"
    FUNDAMENTAL_HEALTH = "fundamental_health"
    SYNTHESIS = "synthesis"


class SignalClassification(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    INSUFFICIENT_DATA = "insufficient_data"
    UNAVAILABLE = "unavailable"


class StructuredSignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    dimension: SignalDimension
    classification: SignalClassification
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_method: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    data_status: str = "valid"
    metrics: dict[str, Any] = Field(default_factory=dict)
