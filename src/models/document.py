"""API response models and SSE event types — §24.2, §24.3."""
from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field


class RunStatusResponse(BaseModel):
    """§24.2 — GET /v1/runs/{id}."""
    run_id: str
    status: Literal[
        "initializing", "running", "paused",
        "awaiting_approval", "completed", "failed", "cancelled"
    ]
    progress: RunProgress | None = None
    estimated_cost_usd: float = 0.0
    created_at: str
    updated_at: str


class RunProgress(BaseModel):
    current_section_idx: int = 0
    total_sections: int = 0
    current_iteration: int = 0
    phase: Literal["setup", "research", "writing", "review", "output"] = "setup"
    css_content_latest: float = 0.0
    css_style_latest: float = 0.0


class RunCancelResponse(BaseModel):
    run_id: str
    status: str = "cancelled"
    partial_output_url: str | None = None


# ── SSE Event Types (§24.3) ─────────────────────────────────────────────────

class SSEEvent(BaseModel):
    """Base SSE event."""
    event: str
    data: dict[str, Any]
    id: str | None = None
    retry: int | None = None


class SectionStartedEvent(BaseModel):
    event: str = "section_started"
    section_idx: int
    title: str
    target_words: int


class JuryVerdictEvent(BaseModel):
    event: str = "jury_verdict"
    section_idx: int
    iteration: int
    css_content: float
    css_style: float
    route: str


class SectionApprovedEvent(BaseModel):
    event: str = "section_approved"
    section_idx: int
    css_final: float
    iterations_used: int


class EscalationEvent(BaseModel):
    event: str = "escalation"
    escalation_type: str
    trigger: str
    options: list[str] = Field(default_factory=list)


class CostUpdateEvent(BaseModel):
    event: str = "cost_update"
    spent_usd: float
    projected_usd: float
    regime: str


class RunCompletedEvent(BaseModel):
    event: str = "run_completed"
    export_urls: dict[str, str] = Field(default_factory=dict)
    total_cost_usd: float


class RunFailedEvent(BaseModel):
    event: str = "run_failed"
    error_code: str
    message: str


class ProgressEvent(BaseModel):
    event: str = "progress"
    phase: str
    detail: str
