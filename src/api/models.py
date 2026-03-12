"""Pydantic models for DRS API request/response."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QualityPreset(str, Enum):
    economy = "economy"
    balanced = "balanced"
    premium = "premium"


class RunCreateRequest(BaseModel):
    """POST /api/v1/runs — start a new pipeline run."""
    topic: str = Field(..., min_length=3, max_length=500, description="Research topic")
    target_words: int = Field(5000, ge=500, le=50000, description="Target word count")
    quality_preset: QualityPreset = Field(QualityPreset.balanced, description="Quality preset")
    style_profile: str = Field("academic", description="Style profile name")
    max_budget: float = Field(50.0, ge=0.1, le=500.0, description="Max budget in USD")


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class RunResponse(BaseModel):
    """Response for a pipeline run."""
    run_id: str
    topic: str
    status: RunStatus
    quality_preset: str
    target_words: int
    sections_completed: int = 0
    cost_usd: float = 0.0
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class RunSummaryResponse(BaseModel):
    """Abbreviated run info for listing."""
    run_id: str
    topic: str
    status: RunStatus
    cost_usd: float = 0.0
    created_at: datetime


class HealthResponse(BaseModel):
    """GET /health response."""
    status: str = "ok"
    version: str = "0.1.0"
    uptime_s: float = 0.0
    runs_active: int = 0
