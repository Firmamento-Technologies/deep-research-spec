"""YAML config Pydantic schema — §29.6. Expanded in Phase 3."""
from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel, Field, model_validator


class DRSYAMLConfig(BaseModel):
    """Top-level YAML config — §29.6."""
    version: str = "1.0"
    defaults: DefaultsConfig = Field(default_factory=lambda: DefaultsConfig())
    models: YAMLModelsConfig = Field(default_factory=lambda: YAMLModelsConfig())
    convergence: YAMLConvergenceConfig = Field(default_factory=lambda: YAMLConvergenceConfig())
    sources: YAMLSourcesConfig = Field(default_factory=lambda: YAMLSourcesConfig())
    style: YAMLStyleConfig = Field(default_factory=lambda: YAMLStyleConfig())
    security: YAMLSecurityConfig = Field(default_factory=lambda: YAMLSecurityConfig())
    observability: YAMLObservabilityConfig = Field(default_factory=lambda: YAMLObservabilityConfig())


class DefaultsConfig(BaseModel):
    quality_preset: Literal["economy", "balanced", "premium"] = "balanced"
    language: str = "en"
    citation_style: str = "APA7"
    max_budget_dollars: float = Field(default=50.0, ge=1.0, le=500.0)
    target_words: int = Field(default=5000, ge=500, le=100000)
    output_formats: list[str] = Field(default_factory=lambda: ["markdown", "docx"])
    hitl_enabled: bool = True
    privacy_mode: Literal["standard", "enhanced", "strict", "self_hosted"] = "standard"


class YAMLModelsConfig(BaseModel):
    """§29.6 — Per-slot model overrides."""
    overrides: dict[str, str] = Field(default_factory=dict)


class YAMLConvergenceConfig(BaseModel):
    """§29.3 — Convergence tuning."""
    jury_weights: dict[str, float] = Field(
        default_factory=lambda: {"reasoning": 0.35, "factual": 0.45, "style": 0.20}
    )
    panel_max_rounds: int = Field(default=2, ge=1, le=5)
    oscillation_soft_limit: int = Field(default=3, ge=1, le=10)
    oscillation_hard_limit: int = Field(default=5, ge=2, le=15)

    @model_validator(mode="after")
    def check_weights_sum(self) -> YAMLConvergenceConfig:
        total = sum(self.jury_weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"jury_weights must sum to 1.0, got {total}")
        return self


class YAMLSourcesConfig(BaseModel):
    max_per_section: int = Field(default=15, ge=5, le=50)
    min_per_section: int = Field(default=3, ge=1, le=15)
    preferred_types: list[str] = Field(default_factory=lambda: ["academic", "institutional"])
    blocked_domains: list[str] = Field(default_factory=list)


class YAMLStyleConfig(BaseModel):
    default_profile: str = "academic"
    custom_profiles_dir: str = "config/styles/"


class YAMLSecurityConfig(BaseModel):
    rate_limit_rpm: int = Field(default=60, ge=1)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    jwt_issuer: str = "drs"


class YAMLObservabilityConfig(BaseModel):
    otel_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"
