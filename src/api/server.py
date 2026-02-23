"""FastAPI server for Deep Research System.

Provides REST API for pipeline execution, run monitoring, and health checks.

Usage::

    uvicorn src.api.server:app --host 0.0.0.0 --port 8000
    # or
    python -m src.api.server
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import (
    HealthResponse,
    QualityPreset,
    RunCreateRequest,
    RunResponse,
    RunStatus,
    RunSummaryResponse,
)
from src.observability.metrics import start_metrics_server

logger = logging.getLogger(__name__)

# ── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Deep Research System",
    description="AI-powered long-form document generation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-Memory Run Store (production: use PostgreSQL) ─────────────────────────

_runs: dict[str, dict[str, Any]] = {}
_start_time = time.time()


# ── Lifecycle Events ─────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup():
    start_metrics_server(port=9090)
    logger.info("DRS API server started")


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    active = sum(1 for r in _runs.values() if r["status"] in ("queued", "running"))
    return HealthResponse(
        status="ok",
        version="0.1.0",
        uptime_s=round(time.time() - _start_time, 1),
        runs_active=active,
    )


# ── Runs ─────────────────────────────────────────────────────────────────────

@app.post("/api/v1/runs", response_model=RunResponse, status_code=202, tags=["Runs"])
async def create_run(req: RunCreateRequest, background_tasks: BackgroundTasks):
    """Start a new pipeline run (async — returns immediately)."""
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    run_record: dict[str, Any] = {
        "run_id": run_id,
        "topic": req.topic,
        "status": RunStatus.queued,
        "quality_preset": req.quality_preset.value,
        "target_words": req.target_words,
        "style_profile": req.style_profile,
        "max_budget": req.max_budget,
        "sections_completed": 0,
        "cost_usd": 0.0,
        "created_at": now,
        "completed_at": None,
        "error": None,
    }
    _runs[run_id] = run_record

    background_tasks.add_task(_execute_run, run_id)

    logger.info("Run %s queued — topic='%s' preset=%s", run_id, req.topic, req.quality_preset.value)
    return RunResponse(**run_record)


@app.get("/api/v1/runs/{run_id}", response_model=RunResponse, tags=["Runs"])
async def get_run(run_id: str):
    """Get the status of a pipeline run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return RunResponse(**_runs[run_id])


@app.get("/api/v1/runs", response_model=list[RunSummaryResponse], tags=["Runs"])
async def list_runs(limit: int = 20):
    """List recent pipeline runs."""
    sorted_runs = sorted(_runs.values(), key=lambda r: r["created_at"], reverse=True)
    return [
        RunSummaryResponse(
            run_id=r["run_id"],
            topic=r["topic"],
            status=r["status"],
            cost_usd=r["cost_usd"],
            created_at=r["created_at"],
        )
        for r in sorted_runs[:limit]
    ]


@app.delete("/api/v1/runs/{run_id}", status_code=204, tags=["Runs"])
async def cancel_run(run_id: str):
    """Cancel a queued or running pipeline run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run = _runs[run_id]
    if run["status"] in (RunStatus.completed, RunStatus.failed):
        raise HTTPException(
            status_code=409,
            detail=f"Run {run_id} already {run['status'].value}",
        )

    run["status"] = RunStatus.failed
    run["error"] = "Cancelled by user"
    run["completed_at"] = datetime.now(timezone.utc)
    logger.info("Run %s cancelled", run_id)


# ── Execution ────────────────────────────────────────────────────────────────

async def _execute_run(run_id: str) -> None:
    """Background task: execute the pipeline for a given run."""
    run = _runs.get(run_id)
    if not run:
        return

    run["status"] = RunStatus.running

    try:
        from src.main import run_pipeline

        result = await run_pipeline(
            topic=run["topic"],
            target_words=run["target_words"],
            quality_preset=run["quality_preset"],
            style_profile=run["style_profile"],
            max_budget=run["max_budget"],
        )

        run["status"] = RunStatus.completed
        run["sections_completed"] = len(result.get("approved_sections", []))
        run["cost_usd"] = result.get("budget", {}).get("spent_dollars", 0)
        run["completed_at"] = datetime.now(timezone.utc)

        logger.info(
            "Run %s completed — %d sections, $%.4f",
            run_id, run["sections_completed"], run["cost_usd"],
        )

    except Exception as exc:
        run["status"] = RunStatus.failed
        run["error"] = str(exc)[:500]
        run["completed_at"] = datetime.now(timezone.utc)
        logger.error("Run %s failed: %s", run_id, exc, exc_info=True)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
