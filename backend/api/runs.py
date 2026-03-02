from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid

router = APIRouter()


class RunCreateRequest(BaseModel):
    topic: str
    target_words: int
    quality_preset: str  # Economy | Balanced | Premium
    style_profile: Optional[str] = "Academic"
    max_budget: float = 50.0
    output_formats: List[str] = ["markdown", "docx"]
    hitl_enabled: bool = False
    citation_style: str = "APA"


@router.post("/runs")
async def create_run(body: RunCreateRequest):
    # TODO: STEP 5 — save to Redis + PostgreSQL + start LangGraph pipeline
    doc_id = str(uuid.uuid4())
    return {"doc_id": doc_id, "status": "initializing"}


@router.get("/runs")
async def list_runs():
    # TODO: STEP 5 — read from Redis set runs:all
    return []


@router.get("/runs/{doc_id}")
async def get_run(doc_id: str):
    # TODO: STEP 5 — read run:{doc_id}:state from Redis
    raise HTTPException(status_code=404, detail="Run not found")


@router.get("/runs/{doc_id}/events")
async def stream_events(doc_id: str):
    # TODO: STEP 5 — subscribe to Redis pub/sub run:{doc_id}:events
    async def placeholder():
        yield 'data: {"event": "CONNECTED", "data": {}}\n\n'
    return StreamingResponse(
        placeholder(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{doc_id}/approve-outline")
async def approve_outline(doc_id: str, body: dict):
    # TODO: STEP 5 — write to Redis, unblock waiting pipeline
    return {"accepted": True}


@router.post("/runs/{doc_id}/approve-section")
async def approve_section(doc_id: str, body: dict):
    # TODO: STEP 5
    return {"accepted": True}


@router.post("/runs/{doc_id}/resolve-escalation")
async def resolve_escalation(doc_id: str, body: dict):
    # TODO: STEP 5
    return {"accepted": True}


@router.get("/runs/{doc_id}/output/{format}")
async def download_output(doc_id: str, format: str):
    # TODO: STEP 12 — serve presigned URL from MinIO
    raise HTTPException(status_code=404, detail="Output not found")


@router.delete("/runs/{doc_id}")
async def cancel_run(doc_id: str):
    # TODO: STEP 5 — set status=cancelled, signal pipeline to stop
    return {"cancelled": True}


@router.patch("/runs/{doc_id}/config")
async def update_run_config(doc_id: str, body: dict):
    # TODO: STEP 8 — update node model assignment for next invocation
    return {"updated": True}
