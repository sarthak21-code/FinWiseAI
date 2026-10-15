from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class DocumentChunkModel(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    section: str
    text: str
    token_count: int


class FinancialDocumentModel(BaseModel):
    id: str
    issuer: str
    ticker: str
    title: str
    document_type: str
    reporting_period: str
    published_at: datetime
    source_name: str
    source_url: Optional[str] = None
    synthetic: bool = False
    content_hash: str
    chunk_count: int = 0


class DocumentSearchResult(BaseModel):
    document_id: str
    chunk_id: str
    document_title: str
    issuer: str
    ticker: str
    document_type: str
    reporting_period: str
    published_at: datetime
    source_name: str
    source_url: Optional[str] = None
    relevance_score: float
    excerpt: str
    synthetic: bool


class GroundedCitation(BaseModel):
    citation_id: str = Field(default_factory=lambda: str(uuid4()))
    claim: str
    # Retrieval establishes context only. Support/contradiction requires a
    # separate verifier and must never be inferred from a BM25 match.
    claim_type: str = "context"
    document_id: str
    chunk_id: str
    document_title: str
    issuer: str
    ticker: str
    reporting_period: str
    excerpt: str
    relevance_score: float
    synthetic: bool
    source_name: str = "Unknown source"
    source_url: Optional[str] = None
