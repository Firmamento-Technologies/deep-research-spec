"""Run Manager service for orchestrating research pipeline execution.

The RunManager is a singleton service that manages the lifecycle of research
runs (documents). It handles:

- Starting new runs (creating DB entry + launching graph)
- Cancelling runs (graceful task cancellation)
- Resuming runs (HITL user input after interrupts)
- Status tracking (DB + in-memory active runs)
- Error handling (exceptions → DB error state)
- SSE integration (real-time events to frontend)

Architecture:

    API endpoint
        ↓
    RunManager.start_run()
        ↓
    Background AsyncIO task:
        1. Create DB Run record
        2. Build graph with checkpointer
        3. Inject SSE broker into state
        4. Execute graph.ainvoke()
        5. Update DB on completion/error
        6. Cleanup active_runs
        ↓
    Graph emits SSE events → Frontend

Usage:
    from src.services.run_manager import run_manager
    
    # Start a new run
    run = await run_manager.start_run(
        doc_id="doc-abc-123",
        topic="Quantum Computing",
        quality_preset="Balanced",
        target_words=5000,
        max_budget=50.0,
    )
    
    # Check status
    status = await run_manager.get_run_status("doc-abc-123")
    
    # Cancel run
    await run_manager.cancel_run("doc-abc-123")
    
    # Resume after HITL (outline approval)
    await run_manager.resume_run("doc-abc-123", user_input={"approved": True})

Spec: §10 Graph orchestration, §20 HITL workflow
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database.models import Run
from database.connection import get_db
from src.models.state import build_initial_state, ResearchState
from src.graph import build_graph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active runs registry
# ---------------------------------------------------------------------------

# In-memory dict to track active runs:
# {doc_id: {"task": AsyncIO task, "state": current state, "graph": compiled graph}}
active_runs: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# RunManager class
# ---------------------------------------------------------------------------

class RunManager:
    """Singleton service for managing research pipeline runs."""

    def __init__(self):
        self.graph_checkpointer_dsn: Optional[str] = None
        logger.info("RunManager initialized")

    def configure(self, checkpointer_dsn: Optional[str] = None):
        """Configure the run manager.

        Args:
            checkpointer_dsn: PostgreSQL DSN for LangGraph checkpointing.
                             Format: "postgresql://user:pass@host/db"
        """
        self.graph_checkpointer_dsn = checkpointer_dsn
        logger.info("RunManager configured (checkpointer=%s)", bool(checkpointer_dsn))

    async def start_run(
        self,
        doc_id: str,
        topic: str,
        quality_preset: str = "Balanced",
        target_words: int = 5000,
        max_budget: float = 50.0,
        style_profile: str = "academic",
        knowledge_space_id: Optional[str] = None,
    ) -> Run:
        """Start a new research run in the background.

        Creates a DB entry and launches graph execution as an AsyncIO task.

        Args:
            doc_id:             Unique document ID.
            topic:              Research topic.
            quality_preset:     "Economy" | "Balanced" | "Premium".
            target_words:       Target document length.
            max_budget:         Maximum budget in USD.
            style_profile:      Writing style (academic, journalistic, etc.).
            knowledge_space_id: Optional Knowledge Space for RAG.

        Returns:
            Run: Database Run record.

        Raises:
            ValueError: If run already exists or is active.
        """
        # Check if run already exists
        async for db in get_db():
            existing = await db.get(Run, doc_id)
            if existing:
                raise ValueError(f"Run {doc_id} already exists")

        # Check if run is already active
        if doc_id in active_runs:
            raise ValueError(f"Run {doc_id} is already active")

        logger.info(
            "Starting run: doc_id=%s, topic='%s', preset=%s, target=%d",
            doc_id, topic, quality_preset, target_words,
        )

        # Create DB entry
        async for db in get_db():
            run = Run(
                doc_id=doc_id,
                topic=topic,
                quality_preset=quality_preset,
                target_words=target_words,
                max_budget=max_budget,
                status="initializing",
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)

        # Build initial state
        initial_state = build_initial_state(
            doc_id=doc_id,
            topic=topic,
            target_words=target_words,
            max_budget=max_budget,
            quality_preset=quality_preset,
            style_profile=style_profile,
            knowledge_space_id=knowledge_space_id,
        )

        # Build graph
        graph = build_graph(checkpointer_dsn=self.graph_checkpointer_dsn)

        # Launch background task
        task = asyncio.create_task(
            self._run_graph_task(doc_id, graph, initial_state)
        )

        # Register active run
        active_runs[doc_id] = {
            "task": task,
            "graph": graph,
            "state": initial_state,
        }

        logger.info("Run %s launched in background", doc_id)
        return run

    async def cancel_run(self, doc_id: str) -> None:
        """Cancel an active run.

        Gracefully cancels the background task and updates DB status.

        Args:
            doc_id: Document ID to cancel.

        Raises:
            ValueError: If run is not active.
        """
        if doc_id not in active_runs:
            raise ValueError(f"Run {doc_id} is not active")

        logger.info("Cancelling run: %s", doc_id)

        # Cancel task
        task = active_runs[doc_id]["task"]
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            logger.info("Run %s task cancelled", doc_id)

        # Update DB
        async for db in get_db():
            await db.execute(
                update(Run)
                .where(Run.doc_id == doc_id)
                .values(status="cancelled", completed_at=datetime.utcnow())
            )
            await db.commit()

        # Cleanup (idempotent: _run_graph_task may have already removed it)
        active_runs.pop(doc_id, None)
        logger.info("Run %s cancelled and cleaned up", doc_id)

    async def resume_run(
        self,
        doc_id: str,
        user_input: Dict[str, Any],
    ) -> None:
        """Resume a run after HITL user input.

        Used for outline approval, section approval, etc.

        Args:
            doc_id:     Document ID to resume.
            user_input: User input dict (e.g., {"approved": True, "outline": [...]}).

        Raises:
            ValueError: If run is not active.
        """
        if doc_id not in active_runs:
            raise ValueError(f"Run {doc_id} is not active (cannot resume)")

        logger.info("Resuming run %s with user input: %s", doc_id, user_input)

        from services.sse_broker import get_broker
        broker = get_broker()

        approval_type = str(user_input.get("type", ""))
        if approval_type == "outline_approval":
            payload = {
                "approved": bool(user_input.get("approved", True)),
                "sections": user_input.get("sections"),
            }
            await broker.submit_outline_approval(doc_id, payload)
            await broker.emit(doc_id, "OUTLINE_APPROVED", payload)

        elif approval_type == "section_approval":
            section_idx = int(user_input.get("section_idx", 0))
            payload = {
                "section_idx": section_idx,
                "approved": bool(user_input.get("approved", True)),
                "content": user_input.get("content"),
            }
            await broker.submit_section_approval(doc_id, section_idx, payload)
            await broker.emit(doc_id, "SECTION_APPROVED", payload)

        else:
            raise ValueError(f"Unsupported resume input type: {approval_type!r}")

        await self._update_run_status(doc_id, "running")
        await broker.emit(doc_id, "RUN_RESUMED", {"type": approval_type})

    async def get_run_status(self, doc_id: str) -> Dict[str, Any]:
        """Get current status of a run.

        Returns combined info from DB + in-memory active runs.

        Args:
            doc_id: Document ID.

        Returns:
            Status dict with keys: doc_id, status, total_cost, total_words,
            is_active, current_section (if active).

        Raises:
            ValueError: If run not found.
        """
        # Get DB record
        async for db in get_db():
            run = await db.get(Run, doc_id)
            if not run:
                raise ValueError(f"Run {doc_id} not found")

            status = {
                "doc_id": run.doc_id,
                "topic": run.topic,
                "status": run.status,
                "total_cost": float(run.total_cost or 0),
                "total_words": run.total_words or 0,
                "quality_preset": run.quality_preset,
                "target_words": run.target_words,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "is_active": doc_id in active_runs,
            }

            # Add in-memory state if active
            if doc_id in active_runs:
                state = active_runs[doc_id]["state"]
                status["current_section"] = state.get("current_section", 0)
                status["total_sections"] = state.get("total_sections", 0)
                status["budget_spent"] = state.get("budget_spent", 0.0)
                status["budget_remaining_pct"] = state.get("budget_remaining_pct", 100.0)

            return status

    # -----------------------------------------------------------------------
    # Private methods
    # -----------------------------------------------------------------------

    async def _run_graph_task(
        self,
        doc_id: str,
        graph,
        initial_state: ResearchState,
    ) -> None:
        """Background task that executes the graph.

        Handles:
        - SSE broker injection
        - Graph execution
        - DB updates (status, cost, words)
        - Error handling
        - Cleanup

        Args:
            doc_id:        Document ID.
            graph:         Compiled LangGraph.
            initial_state: Initial state dict.
        """
        try:
            logger.info("[%s] Graph execution started", doc_id)

            # Inject SSE broker
            from services.sse_broker import get_broker
            broker = get_broker()
            initial_state["broker"] = broker

            # Emit start event
            await broker.emit(doc_id, "PIPELINE_STARTED", {
                "topic": initial_state["topic"],
                "quality_preset": initial_state["quality_preset"],
                "target_words": initial_state["target_words"],
            })

            # Update DB: initializing → planning
            await self._update_run_status(doc_id, "planning")

            # Execute graph
            config = {"configurable": {"thread_id": doc_id}}
            final_state = await graph.ainvoke(initial_state, config=config)

            # Extract results
            total_words = sum(s.word_count or 0 for s in final_state["sections"])
            total_cost = final_state.get("budget_spent", 0.0)
            final_document = final_state.get("final_document", "")

            # Update DB: completed
            async for db in get_db():
                await db.execute(
                    update(Run)
                    .where(Run.doc_id == doc_id)
                    .values(
                        status="completed",
                        total_cost=total_cost,
                        total_words=total_words,
                        completed_at=datetime.utcnow(),
                    )
                )
                await db.commit()

            # Emit completion event
            await broker.emit(doc_id, "PIPELINE_COMPLETED", {
                "total_words": total_words,
                "total_cost": total_cost,
            })

            logger.info(
                "[%s] Graph execution completed (words=%d, cost=$%.4f)",
                doc_id, total_words, total_cost,
            )

        except asyncio.CancelledError:
            logger.info("[%s] Graph execution cancelled", doc_id)
            await self._update_run_status(doc_id, "cancelled")
            # Emit cancellation event
            from services.sse_broker import get_broker
            await get_broker().emit(doc_id, "PIPELINE_CANCELLED", {})
            raise

        except Exception as exc:
            logger.error("[%s] Graph execution failed: %s", doc_id, exc, exc_info=True)
            await self._update_run_status(doc_id, "error")
            # Emit error event
            from services.sse_broker import get_broker
            await get_broker().emit(doc_id, "PIPELINE_FAILED", {
                "error": str(exc),
            })

        finally:
            # Cleanup active runs (idempotent; cancel path may race)
            removed = active_runs.pop(doc_id, None)
            if removed is not None:
                logger.info("[%s] Cleaned up from active_runs", doc_id)

    async def _update_run_status(self, doc_id: str, status: str) -> None:
        """Update run status in DB."""
        async for db in get_db():
            await db.execute(
                update(Run)
                .where(Run.doc_id == doc_id)
                .values(status=status)
            )
            await db.commit()


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

run_manager = RunManager()


# ---------------------------------------------------------------------------
# Startup configuration
# ---------------------------------------------------------------------------

def configure_run_manager(checkpointer_dsn: Optional[str] = None):
    """Configure the global run manager.

    Should be called at app startup (e.g., in FastAPI lifespan).

    Args:
        checkpointer_dsn: PostgreSQL DSN for checkpointing.
    """
    run_manager.configure(checkpointer_dsn=checkpointer_dsn)
