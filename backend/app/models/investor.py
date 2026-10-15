from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class InvestorProfile(Base):
    __tablename__ = "investor_profiles"

    __table_args__ = (
        CheckConstraint(
            "risk_tolerance >= 1 AND risk_tolerance <= 5",
            name="check_risk_tolerance",
        ),
        CheckConstraint(
            "investment_horizon_months > 0",
            name="check_investment_horizon",
        ),
        CheckConstraint(
            "max_single_asset_allocation > 0 "
            "AND max_single_asset_allocation <= 1",
            name="check_max_asset_allocation",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(
            "user_identities.id", ondelete="SET NULL",
            name="fk_investor_profiles_owner_id",
        ),
        nullable=True, index=True,
    )

    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    risk_tolerance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    investment_horizon_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=12,
    )

    max_single_asset_allocation: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.20,
    )

    investment_objective: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="Capital Growth",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    holdings: Mapped[list["PortfolioHolding"]] = relationship(
        "PortfolioHolding",
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("investor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )

    shares: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    cost_basis: Mapped[float] = mapped_column(
        Float,
        nullable=True,
    )

    asset_category: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        default="Equity",
    )

    is_watchlist: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    profile: Mapped["InvestorProfile"] = relationship(
        "InvestorProfile",
        back_populates="holdings",
    )
