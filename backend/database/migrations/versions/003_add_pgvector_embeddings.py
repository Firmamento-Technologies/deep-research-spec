"""Add pgvector embedding column to chunks

Revision ID: 003
Revises: 002
Create Date: 2026-03-04
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pgvector extension and embedding column.
    
    pgvector enables efficient vector similarity search in PostgreSQL:
    - VECTOR(384) stores 384-dimensional embeddings from all-MiniLM-L6-v2
    - ivfflat index enables fast approximate nearest neighbor (ANN) search
    - <=> operator computes cosine distance for similarity queries
    
    Index parameters:
    - lists=100: good for 10K-100K vectors (tune based on data size)
    - Rule of thumb: lists ≈ sqrt(num_rows) for optimal performance
    
    Spec: §17 Knowledge Spaces, Task 1.2
    """
    
    # Enable pgvector extension
    # Note: Requires PostgreSQL 11+ with pgvector installed
    # Install: sudo apt install postgresql-<version>-pgvector
    # Or build from source: https://github.com/pgvector/pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # Add embedding column to chunks table
    # VECTOR(384) matches all-MiniLM-L6-v2 output dimension
    op.execute(
        "ALTER TABLE chunks ADD COLUMN embedding VECTOR(384);"
    )
    
    # Create ivfflat index for fast cosine similarity search
    # ivfflat = inverted file with flat compression
    # Lists parameter: number of clusters (tune based on dataset size)
    # - 10K vectors: lists=100
    # - 100K vectors: lists=316 (sqrt(100K))
    # - 1M vectors: lists=1000
    
    op.execute(
        """
        CREATE INDEX idx_chunks_embedding_cosine 
        ON chunks 
        USING ivfflat (embedding vector_cosine_ops) 
        WITH (lists = 100);
        """
    )
    
    # Optional: Create indexes for other distance metrics
    # Uncomment if needed:
    
    # L2 (Euclidean) distance - use if embeddings NOT normalized
    # op.execute(
    #     """
    #     CREATE INDEX idx_chunks_embedding_l2 
    #     ON chunks 
    #     USING ivfflat (embedding vector_l2_ops) 
    #     WITH (lists = 100);
    #     """
    # )
    
    # Inner product - use for dot product similarity
    # op.execute(
    #     """
    #     CREATE INDEX idx_chunks_embedding_ip 
    #     ON chunks 
    #     USING ivfflat (embedding vector_ip_ops) 
    #     WITH (lists = 100);
    #     """
    # )


def downgrade() -> None:
    """Remove pgvector embedding column and extension."""
    
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_cosine;")
    # op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_l2;")
    # op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_ip;")
    
    # Drop column
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding;")
    
    # Drop extension (careful: might affect other tables)
    # Comment out if other tables use vector type
    op.execute("DROP EXTENSION IF EXISTS vector;")
