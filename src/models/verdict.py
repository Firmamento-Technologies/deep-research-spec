"""Pydantic models for jury verdicts — §8.6, §10.1, §10.3."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class DimensionScores(BaseModel):
    """§8.6 — Typed dimension scores from each judge."""
    logical_structure: float | None = None
    argument_validity: float | None = None
    causal_reasoning: float | None = None
    factual_accuracy: float | None = None
    source_support: float | None = None
    citation_precision: float | None = None
    tone_consistency: float | None = None
    vocabulary_level: float | None = None
    readability: float | None = None
    formatting: float | None = None
    grammar: float | None = None
    coherence: float | None = None


class VerdictJSON(BaseModel):
    """§8.6 — Structured output from each judge."""
    judge_slot: Literal["R1","R2","R3","F1","F2","F3","S1","S2","S3"]
    model: str
    dimension_scores: DimensionScores
    pass_fail: bool
    veto_category: Literal[
        "fabricated_source", "factual_error",
        "logical_contradiction", "plagiarism"
    ] | None = None
    confidence: Literal["low", "medium", "high"]
    motivation: str = Field(max_length=2000)
    failed_claims: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    external_sources_consulted: list[str] = Field(default_factory=list)
    css_contribution: float = 0.0


class L1VetoVerdict(BaseModel):
    """§10.1 — Individual veto verdict."""
    judge_slot: str
    model: str
    veto_category: Literal[
        "fabricated_source", "factual_error",
        "logical_contradiction", "plagiarism"
    ]
    affected_text: str = Field(max_length=200)
    evidence: str = Field(max_length=400)
    external_source_url: str | None = None
    confidence: Literal["low", "medium", "high"]
    timestamp: str


class RogueJudgeFlag(BaseModel):
    """§10.3 — Rogue judge detection flag."""
    judge_slot: str
    model: str
    disagreement_rate: float
    sections_evaluated: int
    action: Literal["temporary_replacement", "monitor"]
    replacement_model: str


class RogueJudgeReport(BaseModel):
    """§10.3 — Rogue judge detection report."""
    doc_id: str
    evaluated_at_section: int
    flags: list[RogueJudgeFlag] = Field(default_factory=list)
    notification_dispatched: bool = False
