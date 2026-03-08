"""Runs API endpoints for DRS research pipeline.

Provides RESTful API for:
- Creating new research runs
- Querying run status
- Streaming real-time SSE events
- HITL approvals (outline, sections)
- Cancelling runs
- Listing all runs

Integrates with:
- RunManager service for orchestration
- SSEBroker for real-time events
- PostgreSQL for persistence
- LangGraph checkpointer for HITL

Spec: §10 API specification, §20 HITL workflow
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import Run
from src.services.run_manager import run_manager
from services.sse_broker import get_broker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["runs"])

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class RunCreateRequest(BaseModel):
    """Request body for POST /api/runs."""
    topic: str = Field(..., min_length=3, max_length=500, description="Research topic")
    quality_preset: str = Field("Balanced", description="Economy | Balanced | Premium")
    target_words: int = Field(5000, ge=1000, le=50000, description="Target document length")
    max_budget: float = Field(50.0, ge=1.0, le=1000.0, description="Maximum budget in USD")
    style_profile: str = Field("academic", description="Writing style")
    knowledge_space_id: Optional[str] = Field(None, description="Optional Knowledge Space for RAG")

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Quantum Computing in 2026",
                "quality_preset": "Balanced",
                "target_words": 5000,
                "max_budget": 50.0,
                "style_profile": "academic",
                "knowledge_space_id": "space-abc-123",
            }
        }


class RunCreateResponse(BaseModel):
    """Response for POST /api/runs."""
    doc_id: str
    status: str = "initializing"
    message: str = "Run started successfully"


class RunStatusResponse(BaseModel):
    """Response for GET /api/runs/{doc_id}."""
    doc_id: str
    topic: str
    status: str
    total_cost: float
    total_words: int
    quality_preset: str
    target_words: int
    created_at: Optional[str]
    completed_at: Optional[str]
    is_active: bool
    current_section: Optional[int] = None
    total_sections: Optional[int] = None
    budget_spent: Optional[float] = None
    budget_remaining_pct: Optional[float] = None


class RunListItem(BaseModel):
    """Item in GET /api/runs response."""
    doc_id: str
    topic: str
    status: str
    quality_preset: str
    total_cost: float
    created_at: Optional[str]
    completed_at: Optional[str]


class ApproveOutlineRequest(BaseModel):
    """Request body for POST /api/runs/{doc_id}/approve-outline."""
    approved: bool = True
    sections: Optional[List[dict]] = None  # User-edited outline


class ApproveSectionRequest(BaseModel):
    """Request body for POST /api/runs/{doc_id}/approve-section."""
    section_idx: int
    approved: bool = True
    content: Optional[str] = None  # User-edited content


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/runs", response_model=RunCreateResponse, status_code=201)
async def create_run(
    body: RunCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> RunCreateResponse:
    """Start a new research run.

    Creates a database entry and launches the graph pipeline in the background.

    Args:
        body: Run creation request with topic, preset, budget, etc.
        db:   Database session (injected).

    Returns:
        RunCreateResponse with doc_id.

    Raises:
        HTTPException 400: If validation fails.
        HTTPException 500: If run creation fails.
    """
    # Validate quality preset
    if body.quality_preset not in ["Economy", "Balanced", "Premium"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid quality_preset: {body.quality_preset}",
        )

    # Generate doc_id
    doc_id = f"doc-{uuid4()}"

    logger.info(
        "Creating run: doc_id=%s, topic='%s', preset=%s",
        doc_id, body.topic, body.quality_preset,
    )

    try:
        # Start run via RunManager
        run = await run_manager.start_run(
            doc_id=doc_id,
            topic=body.topic,
            quality_preset=body.quality_preset,
            target_words=body.target_words,
            max_budget=body.max_budget,
            style_profile=body.style_profile,
            knowledge_space_id=body.knowledge_space_id,
        )

        return RunCreateResponse(
            doc_id=doc_id,
            status="initializing",
            message="Run started successfully. Subscribe to /api/runs/{doc_id}/stream for updates.",
        )

    except ValueError as exc:
        logger.error("Run creation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        logger.error("Run creation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/runs", response_model=List[RunListItem])
async def list_runs(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> List[RunListItem]:
    """List all runs with pagination.

    Args:
        db:     Database session (injected).
        limit:  Max results to return (default 50).
        offset: Skip first N results (default 0).

    Returns:
        List of RunListItem objects.
    """
    result = await db.execute(
        select(Run)
        .order_by(Run.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    runs = result.scalars().all()

    return [
        RunListItem(
            doc_id=r.doc_id,
            topic=r.topic,
            status=r.status,
            quality_preset=r.quality_preset or "Balanced",
            total_cost=float(r.total_cost or 0),
            created_at=r.created_at.isoformat() if r.created_at else None,
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in runs
    ]


@router.get("/runs/{doc_id}", response_model=RunStatusResponse)
async def get_run(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
) -> RunStatusResponse:
    """Get current status of a run.

    Returns combined data from DB + in-memory active runs.

    Args:
        doc_id: Document ID.
        db:     Database session (injected).

    Returns:
        RunStatusResponse with full status.

    Raises:
        HTTPException 404: If run not found.
    """
    try:
        status = await run_manager.get_run_status(doc_id)
        return RunStatusResponse(**status)

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    except Exception as exc:
        logger.error("Failed to get run status: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/runs/{doc_id}/stream")
async def stream_run_events(doc_id: str):
    """Stream real-time SSE events for a run.

    Server-Sent Events (SSE) stream that emits graph execution events:
    - NODE_STARTED
    - NODE_COMPLETED
    - HUMAN_REQUIRED (HITL approvals)
    - SECTION_DRAFTED
    - CRITIC_FEEDBACK
    - DOCUMENT_COMPLETED
    - etc.

    Args:
        doc_id: Document ID.

    Returns:
        StreamingResponse with text/event-stream.
    """
    broker = get_broker()

    async def event_generator():
        """Generate SSE events from broker subscription."""
        try:
            async for event in broker.subscribe(doc_id):
                # SSE format: "data: {json}\n\n"
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.error(
                "[%s] SSE stream error: %s",
                doc_id, exc, exc_info=True,
            )
            # Send error event and close
            error_event = {
                "type": "ERROR",
                "payload": {"message": "Stream error"},
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/runs/{doc_id}/approve-outline", status_code=200)
async def approve_outline(
    doc_id: str,
    body: ApproveOutlineRequest,
) -> dict:
    """Approve outline after Planner node (HITL).

    User can edit the outline before approving. The edited outline is
    passed back to the graph to resume execution.

    Args:
        doc_id: Document ID.
        body:   Approval request with optional edited sections.

    Returns:
        Success message.

    Note:
        Full HITL implementation requires LangGraph interrupt + resume.
        For MVP, this emits an event and logs.
    """
    logger.info(
        "Outline approved for run %s (approved=%s, sections=%s)",
        doc_id, body.approved, len(body.sections) if body.sections else 0,
    )

    try:
        await run_manager.resume_run(
            doc_id,
            user_input={
                "type": "outline_approval",
                "approved": body.approved,
                "sections": body.sections,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"status": "ok", "message": "Outline approval received"}


@router.post("/runs/{doc_id}/approve-section", status_code=200)
async def approve_section(
    doc_id: str,
    body: ApproveSectionRequest,
) -> dict:
    """Approve section after Writer node (HITL).

    User can edit the section content before approving.

    Args:
        doc_id: Document ID.
        body:   Approval request with section index and optional edited content.

    Returns:
        Success message.

    Note:
        Full HITL implementation requires LangGraph interrupt + resume.
        For MVP, this emits an event.
    """
    logger.info(
        "Section %d approved for run %s (approved=%s)",
        body.section_idx, doc_id, body.approved,
    )

    try:
        await run_manager.resume_run(
            doc_id,
            user_input={
                "type": "section_approval",
                "section_idx": body.section_idx,
                "approved": body.approved,
                "content": body.content,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {"status": "ok", "message": "Section approval received"}


@router.delete("/runs/{doc_id}", status_code=204)
async def cancel_run(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Cancel an active run.

    Gracefully stops the graph execution and updates DB status.

    Args:
        doc_id: Document ID.
        db:     Database session (injected).

    Returns:
        204 No Content on success.

    Raises:
        HTTPException 404: If run not found or not active.
        HTTPException 500: If cancellation fails.
    """
    logger.info("Cancelling run: %s", doc_id)

    try:
        await run_manager.cancel_run(doc_id)
        return {"status": "ok"}

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    except Exception as exc:
        logger.error("Failed to cancel run: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
