from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.news import NewsArticleSummary
from app.schemas.rag import GroundedCitation
from app.schemas.signals import StructuredSignal
from app.schemas.investor import PersonalizedAnalysis


AgentStatus = Literal[
    "bullish",
    "bearish",
    "neutral",
    "insufficient_data",
    "unavailable",
]
AnalysisCompleteness = Literal["complete", "partial"]


class AgentAssessment(BaseModel):
    agent_name: str
    status: AgentStatus
    summary: str
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source: str
    is_demo: bool = False
    agent_id: Optional[str] = None
    latency_ms: float = 0.0
    confidence: float = 0.50
    confidence_method: Optional[str] = None
    citations: list[GroundedCitation] = Field(default_factory=list)


class AgentDisagreement(BaseModel):
    agents: list[str]
    conflict: str
    evidence: list[str] = Field(default_factory=list)
    significance: Literal["low", "medium", "high"]


class ReasoningStep(BaseModel):
    step_number: int
    title: str
    description: str
    outcome: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntelligenceAnalysis(BaseModel):
    symbol: str
    generated_at_utc: datetime
    overall_status: AgentStatus
    analysis_completeness: AnalysisCompleteness = "partial"
    assessments: list[AgentAssessment] = Field(default_factory=list)
    news_sentiment_score: float | None = None
    news_fetched_at_utc: datetime | None = None
    news_articles: list[NewsArticleSummary] = Field(default_factory=list)
    disagreements: list[AgentDisagreement] = Field(default_factory=list)
    data_warnings: list[str] = Field(default_factory=list)
    analysis_note: str

    # Extended execution, RAG, and personalization fields
    session_id: Optional[str] = None
    total_latency_ms: float = 0.0
    rag_latency_ms: float = 0.0
    evidence_claims_count: int = 0
    evidence_cited_claims_count: int = 0
    evidence_coverage_percent: float | None = None
    signals: list[StructuredSignal] = Field(default_factory=list)
    citations: list[GroundedCitation] = Field(default_factory=list)
    reasoning_trace: list[ReasoningStep] = Field(default_factory=list)
    personalized_interpretation: Optional[PersonalizedAnalysis] = None
    profile_id: Optional[str] = None


class AnalyzeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    profile_id: Optional[str] = None


class CompareProfilesRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    profile_a_id: str
    profile_b_id: str


class ProfileComparisonResponse(BaseModel):
    symbol: str
    market_facts_unaltered: bool = True
    overall_status: AgentStatus
    profile_a: PersonalizedAnalysis
    profile_b: PersonalizedAnalysis
    comparison_summary: str
