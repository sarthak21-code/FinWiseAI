from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    symbol: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )

    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investor_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="completed",
    )

    overall_classification: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="neutral",
    )

    total_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    rag_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    # JSON-encoded structures
    agents_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    disagreements_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    signals_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    citations_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    reasoning_trace: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    personalized_interpretation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
