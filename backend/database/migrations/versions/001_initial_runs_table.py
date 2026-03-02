"""Initial runs table

Revision ID: 001
Revises:
Create Date: 2026-03-02
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("doc_id",         sa.String(),          nullable=False),
        sa.Column("topic",          sa.Text(),            nullable=False),
        sa.Column("quality_preset", sa.String(20),        nullable=True),
        sa.Column("target_words",   sa.Integer(),         nullable=True),
        sa.Column("max_budget",     sa.Numeric(10, 4),    nullable=True),
        sa.Column("total_cost",     sa.Numeric(10, 6),    nullable=True),
        sa.Column("total_words",    sa.Integer(),         nullable=True),
        sa.Column("css_content",    sa.Numeric(4, 3),     nullable=True),
        sa.Column("css_style",      sa.Numeric(4, 3),     nullable=True),
        sa.Column("css_source",     sa.Numeric(4, 3),     nullable=True),
        sa.Column("status",         sa.String(30),        nullable=True, server_default="initializing"),
        sa.Column("created_at",     sa.DateTime(),        nullable=True, server_default=sa.text("now()")),
        sa.Column("completed_at",   sa.DateTime(),        nullable=True),
        sa.Column("output_paths",   postgresql.JSONB(),   nullable=True),
        sa.PrimaryKeyConstraint("doc_id"),
    )
    op.create_index("ix_runs_status",     "runs", ["status"])
    op.create_index("ix_runs_created_at", "runs", ["created_at"])

    # Create Settings table
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("api_keys", postgresql.JSONB(), nullable=True),
        sa.Column("model_assignments", postgresql.JSONB(), nullable=True),
        sa.Column("default_config", postgresql.JSONB(), nullable=True),
        sa.Column("connectors", postgresql.JSONB(), nullable=True),
        sa.Column("webhooks", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_runs_created_at", table_name="runs")
    op.drop_index("ix_runs_status",     table_name="runs")
    op.drop_table("runs")
