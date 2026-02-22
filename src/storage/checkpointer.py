"""LangGraph AsyncPostgresSaver configuration — §21.2 canonical.

Checkpoint frequency: LangGraph saves state after every super-step (node completion).
Every node in the graph is one checkpoint boundary. No additional checkpoint logic needed.

thread_id lifecycle:
  POST /v1/runs received → thread_id = str(uuid4()) saved to runs.thread_id BEFORE first LLM call
  Node completes         → LangGraph auto-saves checkpoint keyed by thread_id
  Process crash          → State preserved in checkpoints table
  POST /v1/runs/{id}/resume → graph.ainvoke({}, config={"configurable": {"thread_id": existing_thread_id}})
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


async def build_checkpointer(dsn: str) -> AsyncPostgresSaver:
    """Create the LangGraph async checkpointer backed by PostgreSQL.

    Args:
        dsn: PostgreSQL DSN (e.g. ``postgresql://user:pass@host:5432/db``).
            Note: this is the *raw* psycopg DSN, NOT the SQLAlchemy
            ``postgresql+asyncpg://`` variant.

    Returns:
        An initialised ``AsyncPostgresSaver`` ready for ``graph.compile(checkpointer=...)``.
    """
    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=2,
        max_size=10,
        kwargs={"autocommit": True},
    )
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()  # creates checkpoint tables if not present
    return checkpointer


# ── Runnable config helper ───────────────────────────────────────────────────

class RunnableConfig(TypedDict):
    """Config dict passed to every ``graph.ainvoke()`` call.

    Must contain ``configurable.thread_id`` for checkpoint keying.
    """
    configurable: dict  # must contain {"thread_id": str}


def make_config(thread_id: str) -> RunnableConfig:
    """Build a ``RunnableConfig`` for the given thread.

    Args:
        thread_id: The unique thread identifier (stored in ``runs.thread_id``).

    Returns:
        A config dict suitable for ``graph.ainvoke(state, config=...)``.
    """
    return {"configurable": {"thread_id": thread_id}}


# ── Resume reconciliation — §21.3 ───────────────────────────────────────────

async def preflight_reconcile(
    document_id: str,
    session_factory,
) -> dict:
    """Re-sync approved_sections from permanent store after crash recovery.

    §21.3 architectural invariant: ``sections`` table is the source of truth
    for approved content. ``DRSState.approved_sections`` is a derived cache
    rebuilt from ``sections`` table on resume. If State and Store diverge,
    Store wins.

    Args:
        document_id: The document UUID string.
        session_factory: SQLAlchemy ``async_sessionmaker``.

    Returns:
        Partial state update dict with ``approved_sections`` and
        ``current_section_idx`` reconciled from the DB.
    """
    import uuid
    from src.storage.postgres import SectionRepository

    async with session_factory() as session:
        repo = SectionRepository(session)
        db_sections = await repo.fetch_approved_sections(uuid.UUID(document_id))
        return {
            "approved_sections": [
                {
                    "section_index": s.section_index,
                    "title": s.title,
                    "content": s.content,
                    "css_content": float(s.css_content) if s.css_content else None,
                    "css_style": float(s.css_style) if s.css_style else None,
                    "iterations_used": s.iterations_used,
                    "cost_usd": float(s.cost_usd),
                    "checkpoint_hash": s.checkpoint_hash,
                }
                for s in db_sections
            ],
            "current_section_idx": len(db_sections),  # resume from next section
        }


# ── Orphan detector — §21.3 ─────────────────────────────────────────────────

async def detect_orphaned_runs(session_factory, threshold_minutes: int = 3) -> list[str]:
    """Find runs whose heartbeat is stale while status is still 'running'.

    A run is orphaned if ``last_heartbeat > threshold_minutes`` ago and
    ``status == 'running'``.

    Args:
        session_factory: SQLAlchemy ``async_sessionmaker``.
        threshold_minutes: Minutes of silence before declaring orphan (default 3).

    Returns:
        List of orphaned ``run_id`` strings to re-queue.
    """
    import datetime
    from sqlalchemy import select, text
    from src.storage.postgres import Run

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=threshold_minutes)

    async with session_factory() as session:
        stmt = select(Run.id).where(
            Run.status == "running",
            Run.last_heartbeat < cutoff,
        )
        result = await session.execute(stmt)
        return [str(row) for row in result.scalars().all()]
