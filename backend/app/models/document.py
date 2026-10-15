from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class FinancialDocument(Base):
    __tablename__ = "financial_documents"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    issuer: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    ticker: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    document_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        default="10-K",
    )

    reporting_period: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    source_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Official Filing",
    )

    source_url: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    synthetic: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    raw_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("financial_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    section: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="General",
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    document: Mapped["FinancialDocument"] = relationship(
        "FinancialDocument",
        back_populates="chunks",
    )
