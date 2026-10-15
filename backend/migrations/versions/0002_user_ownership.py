"""Add owner scopes while leaving all pre-existing rows unassigned.

revision = "0002_user_ownership"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_user_ownership"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_user_identity_issuer_subject"),
    )
    op.add_column("investor_profiles", sa.Column("owner_id", sa.String(36), nullable=True))
    op.add_column("investor_profiles", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_investor_profiles_owner_id", "investor_profiles", "user_identities", ["owner_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_investor_profiles_owner_id", "investor_profiles", ["owner_id"])

    op.add_column("analysis_sessions", sa.Column("owner_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_analysis_sessions_owner_id", "analysis_sessions", "user_identities", ["owner_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_analysis_sessions_owner_id", "analysis_sessions", ["owner_id"])

    op.add_column("signal_evaluations", sa.Column("owner_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_signal_evaluations_owner_id", "signal_evaluations", "user_identities", ["owner_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_signal_evaluations_owner_id", "signal_evaluations", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_signal_evaluations_owner_id", table_name="signal_evaluations")
    op.drop_constraint("fk_signal_evaluations_owner_id", "signal_evaluations", type_="foreignkey")
    op.drop_column("signal_evaluations", "owner_id")
    op.drop_index("ix_analysis_sessions_owner_id", table_name="analysis_sessions")
    op.drop_constraint("fk_analysis_sessions_owner_id", "analysis_sessions", type_="foreignkey")
    op.drop_column("analysis_sessions", "owner_id")
    op.drop_index("ix_investor_profiles_owner_id", table_name="investor_profiles")
    op.drop_constraint("fk_investor_profiles_owner_id", "investor_profiles", type_="foreignkey")
    op.drop_column("investor_profiles", "is_demo")
    op.drop_column("investor_profiles", "owner_id")
    op.drop_table("user_identities")
