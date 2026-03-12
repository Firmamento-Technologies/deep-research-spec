# Pydantic v2 request / response schemas — mirror the TypeScript types in
# frontend/src/types/api.ts.

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ── Runs ────────────────────────────────────────────────────────────────────────

class RunCreateRequest(BaseModel):
    topic:          str
    quality_preset: str   = Field(default="Balanced", pattern="^(Economy|Balanced|Premium)$")
    target_words:   int   = Field(default=5_000, ge=500,  le=100_000)
    max_budget:     float = Field(default=50.0,  ge=0.1,  le=500.0)
    style_profile:  Optional[str] = None


class RunCreateResponse(BaseModel):
    doc_id: str
    status: str = "initializing"


class RunListItem(BaseModel):
    doc_id:        str
    topic:         str
    status:        str
    quality_preset:str
    budget_spent:  float
    max_budget:    float
    created_at:    datetime
    completed_at:  Optional[datetime] = None


# ── HITL ─────────────────────────────────────────────────────────────────────────

class SectionDef(BaseModel):
    title:        str
    scope:        str = ""
    target_words: int = 1000


class ApproveOutlineRequest(BaseModel):
    sections: List[SectionDef]


class ApproveSectionRequest(BaseModel):
    section_idx:    int
    approved:       bool
    edited_content: Optional[str] = None


class ResolveEscalationRequest(BaseModel):
    action:         str  # auto | manual | skip
    edited_content: Optional[str] = None


# ── Config patch ──────────────────────────────────────────────────────────────────

class NodeModelPatch(BaseModel):
    node_id:   str
    new_model: str


# ── Companion ───────────────────────────────────────────────────────────────────

class ConversationMessage(BaseModel):
    id:        str
    role:      str   # user | companion
    content:   str


class CompanionChatRequest(BaseModel):
    message:              str
    conversation_history: List[ConversationMessage] = []
    current_run_state:    Optional[Dict[str, Any]] = None


class Chip(BaseModel):
    label: str
    value: str


class CompanionChatResponse(BaseModel):
    reply:  str
    chips:  Optional[List[Chip]] = None
    action: Optional[Dict[str, Any]] = None


# ── Settings ───────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    openrouter_api_key:    Optional[str]              = None
    model_assignments:     Optional[Dict[str, str]]   = None
    default_preset:        Optional[str]              = None
    default_budget:        Optional[float]            = None
    default_style_profile: Optional[str]              = None
    connectors:            Optional[Dict[str, bool]]  = None
    webhook_url:           Optional[str]              = None
    webhook_events:        Optional[Dict[str, bool]]  = None
