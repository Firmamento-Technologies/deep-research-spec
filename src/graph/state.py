"""DocumentState and all sub-TypedDicts — §4.6 canonical."""
from __future__ import annotations
from typing import TypedDict, Annotated, Any, Literal
from langgraph.graph.message import add_messages


# ── Sub-TypedDicts ───────────────────────────────────────────────────────────

class BudgetState(TypedDict):
    max_dollars: float
    spent_dollars: float
    projected_final: float
    regime: Literal["Economy", "Balanced", "Premium"]
    css_content_threshold: float
    css_style_threshold: float
    css_panel_threshold: float
    max_iterations: int
    jury_size: int
    mow_enabled: bool
    alarm_70_fired: bool
    alarm_90_fired: bool
    hard_stop_fired: bool


class OutlineSection(TypedDict):
    idx: int
    title: str
    scope: str
    target_words: int
    dependencies: list[int]


class Source(TypedDict):
    source_id: str
    url: str | None
    doi: str | None
    isbn: str | None
    title: str
    authors: list[str]
    year: int | None
    source_type: Literal["academic", "institutional", "social", "web", "upload"]
    publisher: str | None
    reliability_score: float
    abstract: str | None
    nli_entailment: float | None
    http_verified: bool
    ghost_flag: bool


class JudgeVerdict(TypedDict):
    judge_slot: Literal["R1","R2","R3","F1","F2","F3","S1","S2","S3"]
    model: str
    dimension_scores: dict[str, float]
    pass_fail: bool
    veto_category: Literal[
        "fabricated_source", "factual_error",
        "logical_contradiction", "plagiarism"
    ] | None
    confidence: Literal["low", "medium", "high"]
    motivation: str
    failed_claims: list[str]
    missing_evidence: list[str]
    external_sources_consulted: list[str]
    css_contribution: float


class AggregatorVerdict(TypedDict):
    verdict_type: Literal[
        "APPROVED", "VETO", "MISSING_EVIDENCE",
        "FAIL_CONTENT", "FAIL_STYLE", "PANEL_REQUIRED"
    ]
    css_content: float
    css_style: float
    css_composite: float
    dissenting_reasons: list[str]
    best_elements: list[dict]


class ReflectorOutput(TypedDict):
    scope: Literal["SURGICAL", "PARTIAL", "FULL"]
    dominant_scope: Literal["SURGICAL", "PARTIAL", "FULL"]
    feedback_items: list[dict]


class StyleLintViolation(TypedDict):
    rule_id: str
    level: Literal["L1", "L2"]
    category: str
    position: int
    matched_text: str
    message: str
    fix_hint: str


class CoherenceConflict(TypedDict):
    level: Literal["SOFT", "HARD"]
    section_a_idx: int
    section_b_idx: int
    claim_a: str
    claim_b: str
    description: str


class SectionCSSReport(TypedDict):
    """§9.8 — Run Report output per section/iteration."""
    section_idx: int
    iteration: int
    css_content: float
    css_style: float
    css_composite: float
    n_r: int
    n_f: int
    n_s: int
    pass_r: int
    pass_f: int
    pass_s: int
    route_taken: str
    panel_triggered: bool
    veto_triggered: bool
    threshold_content: float
    threshold_style: float


# ── Main State ───────────────────────────────────────────────────────────────

class DocumentState(TypedDict):
    # ── Identifiers ──────────────────────────────────────────────────────
    doc_id: str
    thread_id: str
    user_id: str
    status: Literal[
        "initializing", "running", "paused",
        "awaiting_approval", "completed", "failed", "cancelled"
    ]

    # ── Config (frozen after preflight) ──────────────────────────────────
    config: dict[str, Any]
    style_profile: dict[str, Any]
    style_exemplar: str | None
    quality_preset: Literal["Economy", "Balanced", "Premium"]

    # ── Outline (Phase A) ────────────────────────────────────────────────
    outline: list[OutlineSection]
    outline_approved: bool

    # ── Section loop control ─────────────────────────────────────────────
    current_section_idx: int
    total_sections: int

    # ── Current section state (reset each section) ───────────────────────
    current_sources: list[Source]
    synthesized_sources: str
    current_draft: str
    current_iteration: int
    post_draft_gaps: list[dict]
    style_lint_violations: list[StyleLintViolation]
    jury_verdicts: list[JudgeVerdict]
    all_verdicts_history: list[list[JudgeVerdict]]
    aggregator_verdict: AggregatorVerdict
    reflector_output: ReflectorOutput | None
    css_history: list[float]
    draft_embeddings: list[list[float]]

    # ── Aggregator CSS outputs (§9.7) ────────────────────────────────────
    css_content_current: float
    css_style_current: float
    css_composite_current: float

    # ── Force-approve (§19.5) ────────────────────────────────────────────
    force_approve: bool

    # ── Targeted research flag ───────────────────────────────────────────
    targeted_research_active: bool

    # ── MoW state (internal to writer — §7.1) ────────────────────────────
    mow_drafts: list[str]
    mow_css_per_draft: list[float]
    fusor_draft: str | None

    # ── Approved sections store ──────────────────────────────────────────
    approved_sections: list[dict]
    compressed_context: str

    # ── Writer Memory (§5.18) ────────────────────────────────────────────
    writer_memory: dict[str, Any]

    # ── Budget (§19) ─────────────────────────────────────────────────────
    budget: BudgetState

    # ── Oscillation (§13) ────────────────────────────────────────────────
    oscillation_detected: bool
    oscillation_type: Literal["CSS", "SEMANTIC", "WHACK_A_MOLE"] | None

    # ── Panel Discussion (§11) ───────────────────────────────────────────
    panel_active: bool
    panel_round: int
    panel_anonymized_log: list[dict]

    # ── Coherence / Post-QA ──────────────────────────────────────────────
    coherence_conflicts: list[CoherenceConflict]
    format_validated: bool

    # ── Human-in-the-loop ────────────────────────────────────────────────
    human_intervention_required: bool
    active_escalation: dict | None

    # ── Run Companion (§6) ───────────────────────────────────────────────
    companion_messages: Annotated[list, add_messages]

    # ── Output ───────────────────────────────────────────────────────────
    output_paths: dict[str, str]
    run_metrics: dict[str, Any]
