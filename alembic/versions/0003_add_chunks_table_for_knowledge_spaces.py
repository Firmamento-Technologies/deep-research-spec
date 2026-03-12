"""Add chunks table for Knowledge Spaces RAG

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-04 16:23:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'  # Adjust based on your last migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension if not already enabled
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create chunks table
    op.create_table(
        'chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('space_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=False),  # pgvector stores as float[]
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        
        # Foreign keys with cascade delete
        sa.ForeignKeyConstraint(['space_id'], ['spaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
    )
    
    # Index on space_id for fast filtering
    op.create_index('idx_chunks_space_id', 'chunks', ['space_id'])
    
    # IVFFlat index for vector similarity search (cosine distance)
    # Note: pgvector extension required
    # lists = 100 is recommended for datasets < 1M rows
    op.execute("""
        CREATE INDEX idx_chunks_embedding ON chunks 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    
    # Optional: Add source_id index if queries often filter by source
    op.create_index('idx_chunks_source_id', 'chunks', ['source_id'])
    
    # Comment for documentation
    op.execute("""
        COMMENT ON TABLE chunks IS 
        'Text chunks from Knowledge Space sources with vector embeddings for RAG retrieval. 
        Embeddings generated via sentence-transformers/all-MiniLM-L6-v2 (384 dimensions).'
    """)
    
    op.execute("""
        COMMENT ON COLUMN chunks.embedding IS 
        'Vector embedding (384-dim) from sentence-transformers/all-MiniLM-L6-v2. 
        Used for cosine similarity search in RAG pipeline.'
    """)


def downgrade() -> None:
    op.drop_index('idx_chunks_embedding', table_name='chunks')
    op.drop_index('idx_chunks_source_id', table_name='chunks')
    op.drop_index('idx_chunks_space_id', table_name='chunks')
    op.drop_table('chunks')
    # Note: Not dropping vector extension as other tables might use it
