# SQLAlchemy ORM models with Multi-User Auth

from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, BigInteger, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import uuid

# pgvector support
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    def Vector(dim):
        return Text


class Base(DeclarativeBase):
    pass


# ============================================================================
# User & Authentication Models
# ============================================================================

class User(Base):
    """User account with authentication credentials."""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(20), default="user")  # admin, user, viewer
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)
    metadata = Column(JSONB, nullable=True)
    
    # Relationships
    runs = relationship("Run", back_populates="user", cascade="all, delete-orphan")
    spaces = relationship("Space", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    """Active user sessions with JWT tokens."""
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_jti = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(500), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


# ============================================================================
# Research Runs
# ============================================================================

class Run(Base):
    __tablename__ = "runs"

    doc_id         = Column(String, primary_key=True)
    user_id        = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic          = Column(Text, nullable=False)
    quality_preset = Column(String(20))
    target_words   = Column(Integer)
    max_budget_dollars = Column(Numeric(10, 4))
    total_cost     = Column(Numeric(10, 6), default=0)
    total_words    = Column(Integer)
    css_content    = Column(Numeric(4, 3))
    css_style      = Column(Numeric(4, 3))
    css_source     = Column(Numeric(4, 3))
    current_iteration = Column(Integer, default=1)
    status         = Column(String(30), default="initializing")
    created_at     = Column(DateTime, server_default=func.now())
    completed_at   = Column(DateTime)
    output_paths   = Column(JSONB)
    
    # Relationships
    user = relationship("User", back_populates="runs")


class Section(Base):
    """Document section."""
    __tablename__ = "sections"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String, ForeignKey("runs.doc_id", ondelete="CASCADE"), nullable=False)
    section_idx = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text)
    status = Column(String(30), default="pending")
    metadata = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    api_keys = Column(JSONB, nullable=True)
    model_assignments = Column(JSONB, nullable=True)
    default_config = Column(JSONB, nullable=True)
    connectors = Column(JSONB, nullable=True)
    webhooks = Column(JSONB, nullable=True)


# ============================================================================
# Knowledge Spaces
# ============================================================================

class Space(Base):
    """Knowledge Space."""
    __tablename__ = "spaces"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id     = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="spaces")
    sources = relationship("Source", back_populates="space", cascade="all, delete-orphan")
    chunks  = relationship("Chunk",  back_populates="space", cascade="all, delete-orphan")


class Source(Base):
    """Source file."""
    __tablename__ = "sources"

    id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    space_id     = Column(String(36), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    filename     = Column(String(512), nullable=False)
    mime_type    = Column(String(128), nullable=True)
    file_size    = Column(BigInteger, nullable=True)
    storage_path = Column(Text, nullable=True)
    status       = Column(String(30), default="pending")
    created_at   = Column(DateTime, server_default=func.now())
    metadata     = Column(JSONB, nullable=True)
    
    # Relationships
    space  = relationship("Space", back_populates="sources")
    chunks = relationship("Chunk", back_populates="source", cascade="all, delete-orphan")


class Chunk(Base):
    """Text chunk."""
    __tablename__ = "chunks"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    space_id   = Column(String(36), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False)
    source_id  = Column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    metadata   = Column(JSONB, nullable=True)
    embedding  = Column(Vector(384), nullable=True)
    
    # Relationships
    space  = relationship("Space",  back_populates="chunks")
    source = relationship("Source", back_populates="chunks")
