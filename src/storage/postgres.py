"""SQLAlchemy async models + repository pattern — §21.1, §33.5 canonical."""
from __future__ import annotations

import uuid
import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import (
    String, Text, Integer, Boolean, ForeignKey, Index,
    Numeric, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, TIMESTAMP
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── Base ─────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Declarative base for all DRS tables."""
    pass


# ── Helper ───────────────────────────────────────────────────────────────────

def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> Mapped[datetime.datetime]:
    return mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=datetime.datetime.utcnow,
    )


# ── ORM Models ───────────────────────────────────────────────────────────────
# Placeholder — filled in below

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    created_at: Mapped[datetime.datetime] = _now()


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    config_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = _now()
    updated_at: Mapped[datetime.datetime] = _now()
    completed_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('draft','partial','complete','failed')", name="ck_documents_status"),
    )


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = _pk()
    thread_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    profile: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    started_at: Mapped[datetime.datetime] = _now()
    completed_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_heartbeat: Mapped[datetime.datetime] = _now()

    __table_args__ = (
        CheckConstraint(
            "status IN ('initializing','running','paused','awaiting_approval',"
            "'completed','failed','cancelled','orphaned')",
            name="ck_runs_status",
        ),
        Index("idx_runs_thread", "thread_id"),
        Index("idx_runs_status", "status"),
        Index("idx_runs_document", "document_id"),
    )


class Outline(Base):
    __tablename__ = "outlines"
    id: Mapped[uuid.UUID] = _pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_words: Mapped[int] = mapped_column(Integer, nullable=False)
    dependencies: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    approved_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("document_id", "section_index", name="uq_outlines_doc_section"),
    )


class Section(Base):
    __tablename__ = "sections"
    id: Mapped[uuid.UUID] = _pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    css_content: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    css_style: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    iterations_used: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    checkpoint_hash: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[datetime.datetime] = _now()
    warnings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        CheckConstraint("status IN ('approved','regenerating','superseded')", name="ck_sections_status"),
        UniqueConstraint("document_id", "section_index", "version", name="uq_sections_doc_idx_ver"),
        Index("idx_sections_document", "document_id", "section_index"),
    )


class JuryRound(Base):
    __tablename__ = "jury_rounds"
    id: Mapped[uuid.UUID] = _pk()
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)
    judge_slot: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[str] = mapped_column(String(8), nullable=False)
    veto_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    css_contribution: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    motivation: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime.datetime] = _now()

    __table_args__ = (
        CheckConstraint("confidence IN ('low','medium','high')", name="ck_jury_confidence"),
        Index("idx_jury_section", "section_id", "iteration"),
    )


class CostEntry(Base):
    __tablename__ = "costs"
    id: Mapped[uuid.UUID] = _pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    section_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iteration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime.datetime] = _now()

    __table_args__ = (
        Index("idx_costs_run", "run_id"),
    )


class SourceRecord(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = _pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    nli_entailment: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    http_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ghost_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('academic','institutional','web','social','upload')",
            name="ck_sources_type",
        ),
        Index("idx_sources_document", "document_id", "section_index"),
    )


class WriterMemoryRecord(Base):
    __tablename__ = "writer_memory"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    forbidden_hits: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    glossary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    citation_ratio: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    style_drift_idx: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    updated_at: Mapped[datetime.datetime] = _now()


class RunCompanionLog(Base):
    __tablename__ = "run_companion_log"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iteration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime.datetime] = _now()

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_companion_role"),
        Index("idx_companion_run", "run_id", "timestamp"),
    )


# ── Engine factory ───────────────────────────────────────────────────────────

async def build_engine(dsn: str):
    """Create async engine + session factory.

    Args:
        dsn: PostgreSQL connection string (postgresql+asyncpg://...).

    Returns:
        Tuple of (engine, sessionmaker).
    """
    engine = create_async_engine(dsn, pool_size=10, max_overflow=5)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


# ── Repositories (stubs — implementations follow) ───────────────────────────

class DocumentRepository:
    """CRUD for documents table."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, *, user_id: uuid.UUID, topic: str, config_yaml: str) -> Document:
        doc = Document(user_id=user_id, topic=topic, config_yaml=config_yaml, status="draft")
        self._s.add(doc)
        await self._s.flush()
        return doc

    async def get_by_id(self, doc_id: uuid.UUID) -> Document | None:
        return await self._s.get(Document, doc_id)

    async def set_status(self, doc_id: uuid.UUID, status: str) -> None:
        doc = await self._s.get(Document, doc_id)
        if doc:
            doc.status = status
            doc.updated_at = datetime.datetime.utcnow()
            await self._s.flush()


class RunRepository:
    """CRUD for runs table."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, *, document_id: uuid.UUID, user_id: uuid.UUID,
                     thread_id: str, profile: str, config: dict) -> Run:
        run = Run(
            document_id=document_id, user_id=user_id,
            thread_id=thread_id, profile=profile, config=config,
            status="initializing",
        )
        self._s.add(run)
        await self._s.flush()
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> Run | None:
        return await self._s.get(Run, run_id)

    async def set_status(self, run_id: uuid.UUID, status: str, *, error: str | None = None) -> None:
        run = await self._s.get(Run, run_id)
        if run:
            run.status = status
            if status in ("completed", "failed", "cancelled"):
                run.completed_at = datetime.datetime.utcnow()
            await self._s.flush()

    async def update_heartbeat(self, run_id: uuid.UUID) -> None:
        run = await self._s.get(Run, run_id)
        if run:
            run.last_heartbeat = datetime.datetime.utcnow()
            await self._s.flush()


class SectionRepository:
    """CRUD for sections (permanent approved-section store)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def insert_approved(
        self, *,
        document_id: uuid.UUID,
        run_id: uuid.UUID,
        section_index: int,
        version: int,
        title: str,
        content: str,
        css_content: float | None,
        css_style: float | None,
        iterations_used: int,
        cost_usd: float,
        checkpoint_hash: str,
        warnings: list | None = None,
    ) -> Section:
        section = Section(
            document_id=document_id,
            run_id=run_id,
            section_index=section_index,
            version=version,
            title=title,
            content=content,
            status="approved",
            css_content=Decimal(str(css_content)) if css_content is not None else None,
            css_style=Decimal(str(css_style)) if css_style is not None else None,
            iterations_used=iterations_used,
            cost_usd=Decimal(str(cost_usd)),
            checkpoint_hash=checkpoint_hash,
            warnings=warnings or [],
        )
        self._s.add(section)
        await self._s.flush()
        return section

    async def fetch_approved_sections(self, doc_id: uuid.UUID) -> list[Section]:
        from sqlalchemy import select
        stmt = (
            select(Section)
            .where(Section.document_id == doc_id, Section.status == "approved")
            .order_by(Section.section_index, Section.version.desc())
        )
        result = await self._s.execute(stmt)
        rows = result.scalars().all()
        # Keep only latest version per section_index
        seen: dict[int, Section] = {}
        for row in rows:
            if row.section_index not in seen:
                seen[row.section_index] = row
        return sorted(seen.values(), key=lambda s: s.section_index)


class CostRepository:
    """CRUD for costs table."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record_cost(self, entry: dict) -> None:
        cost = CostEntry(**entry)
        self._s.add(cost)
        await self._s.flush()

    async def get_total_cost(self, run_id: uuid.UUID) -> float:
        from sqlalchemy import select, func
        stmt = select(func.coalesce(func.sum(CostEntry.cost_usd), 0)).where(
            CostEntry.run_id == run_id
        )
        result = await self._s.execute(stmt)
        return float(result.scalar_one())


class JuryRoundRepository:
    """CRUD for jury_rounds table."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record_verdict(self, *, section_id: uuid.UUID, run_id: uuid.UUID,
                             iteration: int, judge_slot: str, model: str,
                             verdict: bool, confidence: str,
                             veto_category: str | None,
                             css_contribution: float | None,
                             motivation: str) -> JuryRound:
        jr = JuryRound(
            section_id=section_id, run_id=run_id, iteration=iteration,
            judge_slot=judge_slot, model=model, verdict=verdict,
            confidence=confidence, veto_category=veto_category,
            css_contribution=Decimal(str(css_contribution)) if css_contribution is not None else None,
            motivation=motivation,
        )
        self._s.add(jr)
        await self._s.flush()
        return jr


class SourceRepository:
    """CRUD for sources table."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def bulk_insert(self, sources: list[dict]) -> None:
        for src in sources:
            self._s.add(SourceRecord(**src))
        await self._s.flush()
