"""Add chunks table for Knowledge Spaces

Revision ID: 002
Revises: 001
Create Date: 2026-03-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create chunks table for RAG retrieval.
    
    Schema per §17 Knowledge Spaces:
    - Each chunk belongs to a space and source
    - Content is raw text (512 token target)
    - embedding column added in migration 003
    - metadata stores chunk position, token count, etc.
    """
    
    # Create spaces table if not exists (prerequisite)
    # NOTE: If spaces already exists from another migration, remove this block
    op.create_table(
        "spaces",
        sa.Column("id",          sa.String(36), nullable=False),
        sa.Column("name",        sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_id",     sa.String(36), nullable=True),
        sa.Column("created_at",  sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at",  sa.DateTime(), server_default=sa.text("now()"), onupdate=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spaces_user_id", "spaces", ["user_id"])
    
    # Create sources table (files/URLs uploaded to spaces)
    op.create_table(
        "sources",
        sa.Column("id",           sa.String(36), nullable=False),
        sa.Column("space_id",     sa.String(36), nullable=False),
        sa.Column("filename",     sa.String(512), nullable=False),
        sa.Column("mime_type",    sa.String(128), nullable=True),
        sa.Column("file_size",    sa.BigInteger(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("status",       sa.String(30), server_default="pending"),  # pending, indexed, failed
        sa.Column("created_at",   sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("metadata",     postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sources_space_id", "sources", ["space_id"])
    op.create_index("ix_sources_status",   "sources", ["status"])
    
    # Create chunks table (main RAG storage)
    op.create_table(
        "chunks",
        sa.Column("id",         sa.String(36), nullable=False),
        sa.Column("space_id",   sa.String(36), nullable=False),
        sa.Column("source_id",  sa.String(36), nullable=False),
        sa.Column("content",    sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("metadata",   postgresql.JSONB(), nullable=True),  # {"chunk_idx": 0, "token_count": 512}
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["space_id"],  ["spaces.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
    )
    
    # Indexes for fast filtering
    op.create_index("ix_chunks_space_id",  "chunks", ["space_id"])
    op.create_index("ix_chunks_source_id", "chunks", ["source_id"])
    
    # Note: Vector index created in migration 003 after pgvector column added


def downgrade() -> None:
    """Remove chunks, sources, and spaces tables."""
    op.drop_index("ix_chunks_source_id", table_name="chunks")
    op.drop_index("ix_chunks_space_id",  table_name="chunks")
    op.drop_table("chunks")
    
    op.drop_index("ix_sources_status",   table_name="sources")
    op.drop_index("ix_sources_space_id", table_name="sources")
    op.drop_table("sources")
    
    op.drop_index("ix_spaces_user_id", table_name="spaces")
    op.drop_table("spaces")
