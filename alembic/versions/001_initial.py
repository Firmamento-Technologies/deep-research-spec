"""Initial schema — all DRS tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    # Documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("config_yaml", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('draft','partial','complete','failed')", name="ck_documents_status"),
    )

    # Runs
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("thread_id", sa.Text, nullable=False, unique=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("profile", sa.Text, nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_heartbeat", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('initializing','running','paused','awaiting_approval',"
            "'completed','failed','cancelled','orphaned')",
            name="ck_runs_status",
        ),
    )
    op.create_index("idx_runs_thread", "runs", ["thread_id"])
    op.create_index("idx_runs_status", "runs", ["status"])
    op.create_index("idx_runs_document", "runs", ["document_id"])

    # Outlines
    op.create_table(
        "outlines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("section_index", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("estimated_words", sa.Integer, nullable=False),
        sa.Column("dependencies", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("document_id", "section_index", name="uq_outlines_doc_section"),
    )

    # Sections
    op.create_table(
        "sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("section_index", sa.Integer, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("css_content", sa.Numeric(4, 3), nullable=True),
        sa.Column("css_style", sa.Numeric(4, 3), nullable=True),
        sa.Column("iterations_used", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Numeric(8, 4), nullable=False),
        sa.Column("checkpoint_hash", sa.Text, nullable=False),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("warnings", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.CheckConstraint("status IN ('approved','regenerating','superseded')", name="ck_sections_status"),
        sa.UniqueConstraint("document_id", "section_index", "version", name="uq_sections_doc_idx_ver"),
    )
    op.create_index("idx_sections_document", "sections", ["document_id", "section_index"])

    # Jury Rounds
    op.create_table(
        "jury_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("iteration", sa.Integer, nullable=False),
        sa.Column("judge_slot", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("verdict", sa.Boolean, nullable=False),
        sa.Column("confidence", sa.String(8), nullable=False),
        sa.Column("veto_category", sa.Text, nullable=True),
        sa.Column("css_contribution", sa.Numeric(4, 3), nullable=True),
        sa.Column("motivation", sa.Text, nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("confidence IN ('low','medium','high')", name="ck_jury_confidence"),
    )
    op.create_index("idx_jury_section", "jury_rounds", ["section_id", "iteration"])

    # Costs
    op.create_table(
        "costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("section_index", sa.Integer, nullable=True),
        sa.Column("iteration", sa.Integer, nullable=True),
        sa.Column("agent", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False),
        sa.Column("tokens_out", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Numeric(8, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("idx_costs_run", "costs", ["run_id"])

    # Sources
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_index", sa.Integer, nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("authors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("doi", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("reliability_score", sa.Numeric(3, 2), nullable=False),
        sa.Column("nli_entailment", sa.Numeric(4, 3), nullable=True),
        sa.Column("http_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ghost_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.CheckConstraint(
            "source_type IN ('academic','institutional','web','social','upload')",
            name="ck_sources_type",
        ),
    )
    op.create_index("idx_sources_document", "sources", ["document_id", "section_index"])

    # Writer Memory
    op.create_table(
        "writer_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("forbidden_hits", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("glossary", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("citation_ratio", sa.Numeric(4, 3), nullable=True),
        sa.Column("style_drift_idx", sa.Numeric(4, 3), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    # Run Companion Log
    op.create_table(
        "run_companion_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("section_index", sa.Integer, nullable=True),
        sa.Column("iteration", sa.Integer, nullable=True),
        sa.Column("modification", postgresql.JSONB, nullable=True),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_companion_role"),
    )
    op.create_index("idx_companion_run", "run_companion_log", ["run_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("run_companion_log")
    op.drop_table("writer_memory")
    op.drop_table("sources")
    op.drop_table("costs")
    op.drop_table("jury_rounds")
    op.drop_table("sections")
    op.drop_table("outlines")
    op.drop_table("runs")
    op.drop_table("documents")
    op.drop_table("users")
