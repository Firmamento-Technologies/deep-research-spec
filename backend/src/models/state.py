"""ResearchState — the single source of truth for the LangGraph pipeline.

All graph nodes receive this state and return partial updates.
The graph merges updates automatically via LangGraph's reducer logic.

Design notes
------------
- TypedDict (not dataclass) so LangGraph can serialize/deserialize.
- All fields have defaults so nodes only need to return changed keys.
- Sub-types (Section, SearchResult, etc.) are plain dataclasses for
  easy JSON serialisation via dataclasses.asdict().
- Aligns exactly with the initial_state dict in services/run_manager.py
  and with the Pydantic schemas in database/schemas.py.

Spec references
---------------
- §9  Researcher node
- §11 Planner node
- §13 Writer node
- §14 Critic / CSS scoring
- §17 Knowledge Spaces (knowledge_space_id)
- §19 Budget tracking
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING
from typing_extensions import TypedDict

if TYPE_CHECKING:
    from services.sse_broker import SSEBroker


# ─────────────────────────────────────────────
# Literal types
# ─────────────────────────────────────────────

RunStatus = Literal[
    "initializing",
    "estimating",
    "planning",
    "awaiting_outline_approval",
    "researching",
    "writing",
    "awaiting_section_approval",
    "critiquing",
    "finalizing",
    "completed",
    "failed",
    "cancelled",
]

SectionStatus = Literal[
    "pending",       # not yet started
    "researching",   # Researcher node running
    "drafting",      # Writer node running
    "awaiting",      # waiting for HITL approval
    "critiquing",    # Critic node running
    "approved",      # accepted (HITL or auto)
    "failed",        # gave up after max_iterations
]


# ─────────────────────────────────────────────
# Section
# ─────────────────────────────────────────────

@dataclass
class Section:
    """A single section of the research document.

    Lifecycle: pending → researching → drafting → awaiting → approved
    Matches SectionDef in database/schemas.py plus runtime fields.
    """
    title: str
    scope: str = ""
    target_words: int = 1000

    # Runtime — filled as the pipeline progresses
    content: str = ""                           # Markdown draft from Writer
    status: SectionStatus = "pending"
    iteration: int = 0                          # How many Writer→Critic cycles
    search_results: List["SearchResult"] = field(default_factory=list)
    css_scores: Optional["CSSScores"] = None   # Latest Critic scores
    word_count: int = 0
    cost_usd: float = 0.0                      # LLM cost for this section

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_schema(cls, schema_dict: dict) -> "Section":
        """Build from SectionDef dict (e.g. from HITL outline approval)."""
        return cls(
            title=schema_dict["title"],
            scope=schema_dict.get("scope", ""),
            target_words=schema_dict.get("target_words", 1000),
        )


# ─────────────────────────────────────────────
# SearchResult
# ─────────────────────────────────────────────

@dataclass
class SearchResult:
    """A single result from web search or semantic search (Knowledge Spaces).

    source_type distinguishes web results from RAG chunks so the Writer
    and Critic can cite them correctly.
    """
    title: str
    url: str
    snippet: str
    source_type: Literal["web", "rag"] = "web"  # "rag" = from Knowledge Space
    similarity: Optional[float] = None          # cosine similarity (RAG only)
    chunk_id: Optional[str] = None             # Chunk.id (RAG only)
    published_date: Optional[str] = None        # ISO date string (web only)

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────
# CSS Scores  (Content / Style / Source)
# ─────────────────────────────────────────────

@dataclass
class CSSScores:
    """Critic evaluation scores — spec §14 CSS scoring.

    Each dimension is 0.0–1.0. The Critic approves a section when
    all three scores exceed the regime threshold (REGIME_PARAMS).
    """
    content: float = 0.0   # Factual accuracy, depth, completeness
    style: float = 0.0     # Clarity, readability, tone
    source: float = 0.0    # Citation quality and diversity

    @property
    def average(self) -> float:
        return (self.content + self.style + self.source) / 3.0

    def meets_threshold(self, threshold: float) -> bool:
        """All three dimensions must exceed threshold."""
        return (
            self.content >= threshold
            and self.style >= threshold
            and self.source >= threshold
        )

    def to_dict(self) -> dict:
        return {"content": self.content, "style": self.style, "source": self.source}


# ─────────────────────────────────────────────
# Node tracking
# ─────────────────────────────────────────────

@dataclass
class NodeInfo:
    """Per-node execution metadata — emitted as SSE NODE_COMPLETED payloads."""
    node_id: str
    started_at: Optional[str] = None    # ISO timestamp
    completed_at: Optional[str] = None
    duration_s: float = 0.0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class JuryVerdict:
    """Record of a single Critic/Jury evaluation.

    Stored in ResearchState.jury_verdicts for audit and oscillation detection.
    """
    section_idx: int
    iteration: int
    scores: CSSScores
    approved: bool
    feedback: str = ""      # Critic feedback passed to Writer on reject
    node_model: str = ""    # Which LLM was used

    def to_dict(self) -> dict:
        d = asdict(self)
        d["scores"] = self.scores.to_dict()
        return d


# ─────────────────────────────────────────────
# ResearchState  — root TypedDict
# ─────────────────────────────────────────────

class ResearchState(TypedDict, total=False):
    """Shared state for the full LangGraph research pipeline.

    total=False means all keys are optional so nodes only need to
    return the fields they modify.

    Fields are grouped by concern and ordered as they are populated
    during pipeline execution.
    """

    # ── Identity ──────────────────────────────
    doc_id: str                         # UUID, set at run creation
    topic: str                          # Research question/title
    status: RunStatus                   # Current pipeline status

    # ── Run parameters (from RunCreateRequest) ──
    quality_preset: str                 # "Economy" | "Balanced" | "Premium"
    target_words: int                   # Total document word count target
    max_budget: float                   # Hard spend cap in USD
    style_profile: Optional[str]        # Writing style (optional)

    # ── Budget tracking ───────────────────────
    budget_spent: float                 # Cumulative LLM cost so far
    budget_remaining_pct: float         # (max_budget - spent) / max_budget * 100
    hard_stop_fired: bool               # True once budget >= 100% — halt pipeline

    # ── Knowledge Space (optional RAG) ────────
    knowledge_space_id: Optional[str]   # If set, Researcher uses RAG

    # ── Planner output ────────────────────────
    outline: List[Section]              # Sections generated by Planner
    total_sections: int                 # len(outline)

    # ── Researcher / Writer progress ──────────
    sections: List[Section]             # Sections with content, filled by Writer
    current_section: int                # Index into sections (0-based)
    current_iteration: int              # Writer→Critic iteration for current section

    # ── Critic / Jury state ───────────────────
    css_scores: Dict[str, float]        # Latest scores as plain dict (SSE payload)
    jury_verdicts: List[JuryVerdict]    # Full history for audit + oscillation guard
    oscillation_detected: bool          # True if Critic alternates approve/reject
    force_approve: bool                 # Override: skip Critic and accept draft

    # ── Advanced modes ────────────────────────
    shine_active: bool                  # SHINE loop enabled (spec §15)
    rlm_mode: bool                      # Recursive LLM mode (spec §16)

    # ── Node metadata ─────────────────────────
    nodes: Dict[str, NodeInfo]          # node_id → NodeInfo (timing, cost)

    # ── Output ────────────────────────────────
    output_paths: Optional[Dict[str, str]]  # {"md": "...", "docx": "..."}

    # ── SSE broker (not serialised to Redis) ──
    # Injected by run_pipeline(), excluded from state snapshots.
    broker: Any                         # SSEBroker instance


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────

def build_initial_state(
    doc_id: str,
    topic: str,
    quality_preset: str = "Balanced",
    target_words: int = 5_000,
    max_budget: float = 50.0,
    style_profile: Optional[str] = None,
    knowledge_space_id: Optional[str] = None,
    broker: Any = None,
) -> ResearchState:
    """Build the initial ResearchState for a new run.

    This mirrors the initial_state dict in services/run_manager.py and
    is the canonical way to create a ResearchState.

    Args:
        doc_id:              UUID from POST /api/runs
        topic:               Research question
        quality_preset:      "Economy" | "Balanced" | "Premium"
        target_words:        Total word count target
        max_budget:          Hard spend cap in USD
        style_profile:       Optional writing style profile
        knowledge_space_id:  Optional Knowledge Space ID for RAG
        broker:              SSEBroker instance (injected by run_pipeline)

    Returns:
        Fully initialised ResearchState ready to pass to graph.ainvoke()
    """
    return ResearchState(
        # Identity
        doc_id=doc_id,
        topic=topic,
        status="initializing",

        # Run params
        quality_preset=quality_preset,
        target_words=target_words,
        max_budget=max_budget,
        style_profile=style_profile,

        # Budget
        budget_spent=0.0,
        budget_remaining_pct=100.0,
        hard_stop_fired=False,

        # RAG
        knowledge_space_id=knowledge_space_id,

        # Planner (empty until planner_node runs)
        outline=[],
        total_sections=0,

        # Progress
        sections=[],
        current_section=0,
        current_iteration=0,

        # Critic
        css_scores={"content": 0.0, "style": 0.0, "source": 0.0},
        jury_verdicts=[],
        oscillation_detected=False,
        force_approve=False,

        # Advanced modes (off by default)
        shine_active=False,
        rlm_mode=False,

        # Node tracking
        nodes={},

        # Output
        output_paths=None,

        # SSE broker
        broker=broker,
    )


# ─────────────────────────────────────────────
# Serialisation helpers
# ─────────────────────────────────────────────

def state_to_redis_dict(state: ResearchState) -> dict:
    """Convert ResearchState to a JSON-serialisable dict for Redis.

    Excludes the `broker` field (not serialisable).
    Converts Section / CSSScores / NodeInfo / JuryVerdict objects to dicts.
    """
    d = dict(state)
    d.pop("broker", None)  # never serialise the broker

    # Serialise Section lists
    if "outline" in d:
        d["outline"] = [s.to_dict() if isinstance(s, Section) else s for s in d["outline"]]
    if "sections" in d:
        d["sections"] = [s.to_dict() if isinstance(s, Section) else s for s in d["sections"]]

    # Serialise jury verdicts
    if "jury_verdicts" in d:
        d["jury_verdicts"] = [
            v.to_dict() if isinstance(v, JuryVerdict) else v
            for v in d["jury_verdicts"]
        ]

    # Serialise node info
    if "nodes" in d:
        d["nodes"] = {
            k: v.to_dict() if isinstance(v, NodeInfo) else v
            for k, v in d["nodes"].items()
        }

    return d


def state_from_redis_dict(d: dict, broker: Any = None) -> ResearchState:
    """Reconstruct a ResearchState from a Redis-stored dict.

    Re-hydrates Section, CSSScores, NodeInfo, JuryVerdict objects.
    The broker must be re-injected since it is never stored.
    """
    state = dict(d)

    # Re-hydrate Section lists
    if "outline" in state:
        state["outline"] = [
            Section(**s) if isinstance(s, dict) else s
            for s in state["outline"]
        ]
    if "sections" in state:
        raw_sections = []
        for s in state["sections"]:
            if isinstance(s, dict):
                # Re-hydrate nested CSSScores
                if s.get("css_scores") and isinstance(s["css_scores"], dict):
                    s = {**s, "css_scores": CSSScores(**s["css_scores"])}
                raw_sections.append(Section(**s))
            else:
                raw_sections.append(s)
        state["sections"] = raw_sections

    # Re-hydrate jury verdicts
    if "jury_verdicts" in state:
        verdicts = []
        for v in state["jury_verdicts"]:
            if isinstance(v, dict):
                if "scores" in v and isinstance(v["scores"], dict):
                    v = {**v, "scores": CSSScores(**v["scores"])}
                verdicts.append(JuryVerdict(**v))
            else:
                verdicts.append(v)
        state["jury_verdicts"] = verdicts

    # Re-hydrate node info
    if "nodes" in state:
        state["nodes"] = {
            k: NodeInfo(**v) if isinstance(v, dict) else v
            for k, v in state["nodes"].items()
        }

    # Re-inject broker
    state["broker"] = broker

    return ResearchState(**state)  # type: ignore[arg-type]
