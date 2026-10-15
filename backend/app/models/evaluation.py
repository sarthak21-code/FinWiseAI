from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SignalEvaluation(Base):
    __tablename__ = "signal_evaluations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(
            "user_identities.id", ondelete="SET NULL",
            name="fk_signal_evaluations_owner_id",
        ),
        nullable=True, index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )

    signal_dimension: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="synthesis",
    )

    signal_classification: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    signal_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    entry_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    evaluation_horizon_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
    )

    target_date: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    exit_price: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    actual_return_percent: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    outcome: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending_window",
    )

    is_synthetic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    data_source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Historical Price Feed",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
