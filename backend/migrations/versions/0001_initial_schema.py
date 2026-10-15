"""Initial FinWiseAI SQLAlchemy schema.

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investor_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("risk_tolerance", sa.Integer(), nullable=False),
        sa.Column("investment_horizon_months", sa.Integer(), nullable=False),
        sa.Column("max_single_asset_allocation", sa.Float(), nullable=False),
        sa.Column("investment_objective", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("risk_tolerance >= 1 AND risk_tolerance <= 5", name="check_risk_tolerance"),
        sa.CheckConstraint("investment_horizon_months > 0", name="check_investment_horizon"),
        sa.CheckConstraint("max_single_asset_allocation > 0 AND max_single_asset_allocation <= 1", name="check_max_asset_allocation"),
    )
    op.create_table(
        "analysis_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(24), nullable=False),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("investor_profiles.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("overall_classification", sa.String(32), nullable=False),
        sa.Column("total_latency_ms", sa.Float(), nullable=False),
        sa.Column("rag_latency_ms", sa.Float(), nullable=False),
        sa.Column("agents_data", sa.Text(), nullable=False),
        sa.Column("disagreements_data", sa.Text(), nullable=False),
        sa.Column("signals_data", sa.Text(), nullable=False),
        sa.Column("citations_data", sa.Text(), nullable=False),
        sa.Column("reasoning_trace", sa.Text(), nullable=False),
        sa.Column("personalized_interpretation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "financial_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("issuer", sa.String(120), nullable=False),
        sa.Column("ticker", sa.String(24), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(60), nullable=False),
        sa.Column("reporting_period", sa.String(60), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "signal_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36)),
        sa.Column("symbol", sa.String(24), nullable=False),
        sa.Column("signal_dimension", sa.String(32), nullable=False),
        sa.Column("signal_classification", sa.String(32), nullable=False),
        sa.Column("signal_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("evaluation_horizon_days", sa.Integer(), nullable=False),
        sa.Column("target_date", sa.String(20), nullable=False),
        sa.Column("exit_price", sa.Float()),
        sa.Column("actual_return_percent", sa.Float()),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("data_source", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "portfolio_holdings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("investor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(24), nullable=False),
        sa.Column("shares", sa.Float(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("cost_basis", sa.Float()),
        sa.Column("asset_category", sa.String(60), nullable=False),
        sa.Column("is_watchlist", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("financial_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(120), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    index_specs = {
        "analysis_sessions": ("symbol", "profile_id", "created_at"),
        "financial_documents": ("issuer", "ticker", "content_hash"),
        "signal_evaluations": ("session_id", "symbol"),
        "portfolio_holdings": ("profile_id", "symbol"),
        "document_chunks": ("document_id",),
    }
    for table_name, columns in index_specs.items():
        for column in columns:
            op.create_index(f"ix_{table_name}_{column}", table_name, [column])


def downgrade() -> None:
    for table_name in (
        "document_chunks", "portfolio_holdings", "signal_evaluations",
        "financial_documents", "analysis_sessions", "investor_profiles",
    ):
        op.drop_table(table_name)
