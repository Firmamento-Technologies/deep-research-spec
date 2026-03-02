# All 10 run endpoints + SSE streaming.
# Spec: UI_BUILD_PLAN.md Section 10.

from __future__ import annotations
import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import Run
from database.schemas import (
    ApproveOutlineRequest,
    ApproveSectionRequest,
    NodeModelPatch,
    ResolveEscalationRequest,
    RunCreateRequest,
    RunCreateResponse,
)
from services.redis_client import redis as redis_client
from services.sse_broker import SSEBroker
from services.run_manager import run_pipeline

router = APIRouter()
broker = SSEBroker(redis_client)


# 1. POST /api/runs — start new run
@router.post("/runs", response_model=RunCreateResponse, status_code=201)
async def create_run(
    body: RunCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    doc_id = str(uuid4())

    initial_state = {
        "doc_id":               doc_id,
        "topic":                body.topic,
        "status":               "initializing",
        "quality_preset":       body.quality_preset,
        "target_words":         body.target_words,
        "max_budget":           body.max_budget,
        "budget_spent":         0.0,
        "budget_remaining_pct": 100.0,
        "total_sections":       0,
        "current_section":      0,
        "current_iteration":    0,
        "nodes":                {},
        "css_scores":           {"content": 0.0, "style": 0.0, "source": 0.0},
        "jury_verdicts":        [],
        "sections":             [],
        "shine_active":         False,
        "rlm_mode":             False,
        "hard_stop_fired":      False,
        "oscillation_detected": False,
        "force_approve":        False,
        "output_paths":         None,
    }

    # Persist to Redis
    await redis_client.set(f"run:{doc_id}:state", json.dumps(initial_state), ex=86_400)
    await redis_client.sadd("runs:all", doc_id)

    # Persist to PostgreSQL
    db.add(Run(
        doc_id=doc_id,
        topic=body.topic,
        quality_preset=body.quality_preset,
        target_words=body.target_words,
        max_budget=str(body.max_budget),
        status="initializing",
    ))

    # Fire pipeline in background
    background_tasks.add_task(run_pipeline, doc_id, body.model_dump(), broker)

    return RunCreateResponse(doc_id=doc_id)


# 2. GET /api/runs — list all runs
@router.get("/runs")
async def list_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Run).order_by(Run.created_at.desc()))
    return [
        {
            "doc_id":        r.doc_id,
            "topic":         r.topic,
            "status":        r.status,
            "quality_preset":r.quality_preset,
            "budget_spent":  float(r.total_cost or 0),
            "max_budget":    float(r.max_budget or 0),
            "created_at":    r.created_at,
            "completed_at":  r.completed_at,
        }
        for r in result.scalars().all()
    ]


# 3. GET /api/runs/{doc_id} — get run state (Redis → fallback DB)
@router.get("/runs/{doc_id}")
async def get_run(doc_id: str, db: AsyncSession = Depends(get_db)):
    raw = await redis_client.get(f"run:{doc_id}:state")
    if raw:
        return json.loads(raw)
    result = await db.execute(select(Run).where(Run.doc_id == doc_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "doc_id":        run.doc_id,
        "topic":         run.topic,
        "status":        run.status,
        "quality_preset":run.quality_preset,
        "budget_spent":  float(run.total_cost or 0),
        "max_budget":    float(run.max_budget or 0),
    }


# 4. GET /api/runs/{doc_id}/events — SSE stream
@router.get("/runs/{doc_id}/events")
async def stream_events(doc_id: str):
    async def event_generator():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"run:{doc_id}:events")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                await asyncio.sleep(0)   # yield to event loop
        finally:
            await pubsub.unsubscribe(f"run:{doc_id}:events")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


# 5. POST /api/runs/{doc_id}/approve-outline — HITL outline approval
@router.post("/runs/{doc_id}/approve-outline")
async def approve_outline(doc_id: str, body: ApproveOutlineRequest):
    await broker.emit(doc_id, "OUTLINE_APPROVED", {
        "sections": [s.model_dump() for s in body.sections]
    })
    return {"status": "ok"}


# 6. POST /api/runs/{doc_id}/approve-section — HITL section approval
@router.post("/runs/{doc_id}/approve-section")
async def approve_section(doc_id: str, body: ApproveSectionRequest):
    await broker.emit(doc_id, "SECTION_APPROVED", body.model_dump())
    return {"status": "ok"}


# 7. POST /api/runs/{doc_id}/resolve-escalation — HITL escalation
@router.post("/runs/{doc_id}/resolve-escalation")
async def resolve_escalation(doc_id: str, body: ResolveEscalationRequest):
    await broker.emit(doc_id, "ESCALATION_RESOLVED", body.model_dump())
    return {"status": "ok"}


# 8. GET /api/runs/{doc_id}/output/{format} — download generated file
@router.get("/runs/{doc_id}/output/{fmt}")
async def download_output(doc_id: str, fmt: str):
    # Full implementation in STEP 12 (MinIO retrieval)
    from services.minio_service import download_output as minio_dl
    from fastapi.concurrency import run_in_threadpool
    try:
        content = await run_in_threadpool(minio_dl, doc_id, fmt)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    content_types = {
        "md":   "text/markdown",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf":  "application/pdf",
        "json": "application/json",
    }
    return Response(
        content=content,
        media_type=content_types.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{doc_id}.{fmt}"'},
    )


# 9. DELETE /api/runs/{doc_id} — cancel run
@router.delete("/runs/{doc_id}", status_code=204)
async def cancel_run(doc_id: str, db: AsyncSession = Depends(get_db)):
    await broker.emit(doc_id, "PIPELINE_CANCELLED", {})
    await redis_client.delete(f"run:{doc_id}:state")
    await db.execute(
        update(Run).where(Run.doc_id == doc_id).values(status="cancelled")
    )
    return Response(status_code=204)


# 10. PATCH /api/runs/{doc_id}/config — update node model for next invocation
@router.patch("/runs/{doc_id}/config")
async def update_node_config(doc_id: str, body: NodeModelPatch):
    config_key = f"run:{doc_id}:config"
    raw = await redis_client.get(config_key)
    cfg: dict = json.loads(raw) if raw else {"model_overrides": {}}
    cfg["model_overrides"][body.node_id] = body.new_model
    await redis_client.set(config_key, json.dumps(cfg), ex=86_400)
    return {"status": "ok", "node_id": body.node_id, "new_model": body.new_model}
