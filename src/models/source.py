"""Pydantic models for sources and citations — §17, §18."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class SourceModel(BaseModel):
    """§17 — Research source with reliability scoring."""
    source_id: str
    url: str | None = None
    doi: str | None = None
    isbn: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    source_type: Literal["academic", "institutional", "social", "web", "upload"]
    publisher: str | None = None
    reliability_score: float = Field(ge=0.0, le=1.0, default=0.5)
    abstract: str | None = None
    nli_entailment: float | None = Field(ge=0.0, le=1.0, default=None)
    http_verified: bool = False
    ghost_flag: bool = False


class CitationEntry(BaseModel):
    """§18 — Citation reference in output document."""
    citation_id: str
    source_id: str
    section_idx: int
    in_text_marker: str
    page_or_paragraph: str | None = None
    quote_snippet: str | None = None
    citation_style_output: str = ""
