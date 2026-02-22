"""API input config models — §03, §24.2, §29. Conflict C02/C09/C17/C18 applied."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

StyleProfile = Literal["academic", "business", "technical", "journalistic", "creative", "legal"]
PrivacyMode = Literal["standard", "enhanced", "strict", "self_hosted"]
DocumentType = Literal[
    "research_paper", "report", "essay", "analysis",
    "literature_review", "white_paper", "case_study",
]
CitationStyle = Literal["APA7", "IEEE", "Chicago", "Harvard", "Vancouver", "MLA9"]
QualityPreset = Literal["economy", "balanced", "premium"]


class SourcesConfig(BaseModel):
    max_sources_per_section: int = Field(default=15, ge=5, le=50)
    min_sources_per_section: int = Field(default=3, ge=1, le=15)
    preferred_source_types: list[str] = Field(default_factory=lambda: ["academic", "institutional"])
    recency_preference: Literal["latest", "balanced", "classic"] = "balanced"
    upload_source_ids: list[str] = Field(default_factory=list)


class ConvergenceConfig(BaseModel):
    css_content_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    css_style_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    max_iterations: int | None = Field(default=None, ge=1, le=12)
    panel_max_rounds: int = Field(default=2, ge=1, le=5)
    jury_weights: dict[str, float] | None = None


class ModelsConfig(BaseModel):
    writer: str | None = None
    researcher: str | None = None
    planner: str | None = None
    reflector: str | None = None


class RunCreateRequest(BaseModel):
    """§24.2 — POST /v1/runs request body."""
    topic: str = Field(min_length=10, max_length=2000)
    document_type: DocumentType = "research_paper"
    style_profile: StyleProfile = "academic"
    target_words: int = Field(default=5000, ge=500, le=100000)
    max_budget_dollars: float = Field(default=50.0, ge=1.0, le=500.0)
    quality_preset: QualityPreset = "balanced"
    language: str = Field(default="en", max_length=5)
    citation_style: CitationStyle = "APA7"
    output_formats: list[str] = Field(default_factory=lambda: ["markdown", "docx"])
    privacy_mode: PrivacyMode = "standard"
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    convergence: ConvergenceConfig = Field(default_factory=ConvergenceConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    custom_instructions: str | None = Field(default=None, max_length=5000)
    webhook_url: str | None = None
    hitl_enabled: bool = True
    style_exemplar: str | None = Field(default=None, max_length=10000)


class RunCreateResponse(BaseModel):
    """§24.2 — POST /v1/runs response."""
    run_id: str
    status: str = "initializing"
    stream_url: str
    estimated_cost_usd: float
    estimated_time_minutes: float
