# SQLAlchemy ORM models — spec: UI_BUILD_PLAN.md Section 10.

from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import uuid

# pgvector support (Task 1.2)
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    # Fallback: define dummy Vector to avoid import errors
    def Vector(dim):
        return Text  # Graceful degradation


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    doc_id         = Column(String,          primary_key=True)
    topic          = Column(Text,            nullable=False)
    quality_preset = Column(String(20))
    target_words   = Column(Integer)
    max_budget     = Column(Numeric(10, 4))
    total_cost     = Column(Numeric(10, 6),  default=0)
    total_words    = Column(Integer)
    css_content    = Column(Numeric(4, 3))
    css_style      = Column(Numeric(4, 3))
    css_source     = Column(Numeric(4, 3))
    status         = Column(String(30),      default="initializing")
    created_at     = Column(DateTime,        server_default=func.now())
    completed_at   = Column(DateTime)
    output_paths   = Column(JSONB)


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    api_keys = Column(JSONB, nullable=True)
    model_assignments = Column(JSONB, nullable=True)
    default_config = Column(JSONB, nullable=True)
    connectors = Column(JSONB, nullable=True)
    webhooks = Column(JSONB, nullable=True)


# ============================================================================
# Knowledge Spaces Models (§17 RAG Integration)
# ============================================================================

class Space(Base):
    """Knowledge Space: container for user-uploaded sources.
    
    Each space is a logical grouping of files/URLs that can be selected
    during run creation for RAG-enhanced research.
    
    Spec: §17 Knowledge Spaces
    """
    __tablename__ = "spaces"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    user_id     = Column(String(36), nullable=True)  # For multi-tenancy
    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    sources = relationship("Source", back_populates="space", cascade="all, delete-orphan")
    chunks  = relationship("Chunk",  back_populates="space", cascade="all, delete-orphan")


class Source(Base):
    """Source file or URL uploaded to a Knowledge Space.
    
    After upload, the file is processed by space_indexer (Task 2.5) to
    generate chunks with embeddings.
    
    Spec: §17 Knowledge Spaces
    """
    __tablename__ = "sources"

    id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    space_id     = Column(String(36), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    filename     = Column(String(512), nullable=False)
    mime_type    = Column(String(128), nullable=True)
    file_size    = Column(BigInteger, nullable=True)  # bytes
    storage_path = Column(Text, nullable=True)  # /data/spaces/{space_id}/{source_id}.ext
    status       = Column(String(30), default="pending")  # pending, indexed, failed
    created_at   = Column(DateTime, server_default=func.now())
    metadata     = Column(JSONB, nullable=True)  # {"original_url": "...", "page_count": 42}
    
    # Relationships
    space  = relationship("Space", back_populates="sources")
    chunks = relationship("Chunk", back_populates="source", cascade="all, delete-orphan")


class Chunk(Base):
    """Text chunk extracted from a Source for RAG retrieval.
    
    Each chunk is ~512 tokens (overlap 50) with semantic boundaries.
    Embeddings generated via sentence-transformers (Task 2.3).
    
    Spec: §17 Knowledge Spaces, §5.2 Researcher (memvid_local connector)
    """
    __tablename__ = "chunks"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    space_id   = Column(String(36), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    source_id  = Column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    metadata   = Column(JSONB, nullable=True)  # {"chunk_idx": 0, "token_count": 512}
    
    # pgvector embedding column (Task 1.2)
    # 384 dimensions from all-MiniLM-L6-v2 (sentence-transformers)
    # Supports cosine similarity queries: ORDER BY embedding <=> query_vector
    embedding = Column(Vector(384), nullable=True)
    
    # Relationships
    space  = relationship("Space",  back_populates="chunks")
    source = relationship("Source", back_populates="chunks")
