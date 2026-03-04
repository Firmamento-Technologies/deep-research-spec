# Async SQLAlchemy engine, session factory, and convenience helpers.

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from .models import Base
from config.settings import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_async_engine() -> AsyncEngine:
    """Return the global async engine instance.
    
    Used by RAG retriever and other components that need direct
    engine access (e.g., raw SQL queries for pgvector).
    """
    return engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session and auto-commits or rolls back."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables on startup (idempotent — does not drop existing tables)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
