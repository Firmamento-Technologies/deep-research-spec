# 04_architecture.md
## §4 — System Architecture: Phases A–D, DocumentState, LangGraph Graph

---

## §4.1 Phase A — Pre-Flight and Setup

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE A: PRE-FLIGHT & SETUP                                    │
│                                                                 │
│  [preflight] ──► [budget_estimator] ──► [planner]              │
│       │                 │                    │                  │
│  config valid?    stima > 0.80×cap?    outline JSON             │
│  api keys OK?      └── ABORT ──────────────►│                  │
│  models exist?                         [await_outline]          │
│                                              │                  │
│                              approved? ──────┤                  │
│                                YES  │   NO   │                  │
│                                     ▼        └──► [planner]    │
│                              → PHASE B                          │
└─────────────────────────────────────────────────────────────────┘
```

- `preflight`: validates API keys, model availability on OpenRouter, Pydantic config schema (§29.6)
- `budget_estimator`: formula `cost = Σ sections × avg_iter × Σ(agent_tokens × price)`; blocks if projection > `max_budget_dollars × 0.80`
- `planner`: produces `List[OutlineSection]` (title, scope, target_words, dependencies); model `google/gemini-2.5-pro`
- `await_outline`: human checkpoint; user may reorder/edit/remove sections; confirms before Phase B

---

## §4.2 Phase B — Per-Section Loop

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  PHASE B: SECTION LOOP  (repeats for each section idx 0..N-1)                   │
│                                                                                  │
│  [researcher] ──► [citation_manager] ──► [citation_verifier]                    │
│       │                                        │                                 │
│  targeted mode?◄─── missing_evidence ◄─────────┤                                │
│                                         [source_sanitizer]                      │
│                                                │                                 │
│                                        [source_synthesizer]                     │
│                                                │                                 │
│                         MoW enabled? (NOT economy AND section≥400w)             │
│                         YES ──► [writer_A][writer_B][writer_C] (parallel)       │
│                                        │                                         │
│                                 [jury_multi_draft]                              │
│                                        │                                         │
│                                    [fusor]                                      │
│                         NO  ──► [writer_single]                                 │
│                                        │                                         │
│                    (both paths converge to single draft)                        │
│                                        │                                         │
│                            [post_draft_analyzer]                                │
│                            gap found? YES ──► [researcher_targeted]             │
│                                             ──► [span_editor] ──► [diff_merger] │
│                                        │                                         │
│                               [style_linter]                                    │
│                         L1/L2 violation? YES ──► [style_fixer] ──► re-lint     │
│                                        │                                         │
│                               [metrics_collector]                               │
│                                        │                                         │
│                    ┌───────────────────▼──────────────────┐                    │
│                    │  JURY (asyncio.gather parallel)       │                    │
│                    │  [jury_R] [jury_F] [jury_S]           │                    │
│                    └───────────────────┬──────────────────┘                    │
│                                        │                                         │
│                               [aggregator]                                      │
│                                        │                                         │
│          route_after_aggregator() ─────┤                                        │
│          (canonical definition: §9.4)  │                                        │
│                                        │                                         │
│  ┌─────────────────────────────────────▼────────────────────────────────┐       │
│  │  APPROVED ──► [context_compressor] ──► [coherence_guard]            │       │
│  │                                               │                      │       │
│  │                          no_conflict/soft ────┤   hard ──► [await_human]    │
│  │                                               │                      │       │
│  │                                    [section_checkpoint]              │       │
│  │                                               │                      │       │
│  │                           idx+1 < total? ─────┤                      │       │
│  │                           YES ──► next section (loop)                │       │
│  │                           NO  ──► PHASE C                            │       │
│  │                                                                       │       │
│  │  FAIL_REFLECTOR ──► [reflector]                                      │       │
│  │       scope? SURGICAL ──► [span_editor] ──► [diff_merger]            │       │
│  │              PARTIAL  ──► [writer_single]                            │       │
│  │              FULL     ──► [await_human]                              │       │
│  │                       └──► [oscillation_check]                       │       │
│  │                                  │                                    │       │
│  │                    continue ─────┤ escalate ──► [await_human]        │       │
│  │                         └──► [writer_single]                         │       │
│  │                                                                       │       │
│  │  FAIL_STYLE ──► [style_fixer] ──► [style_linter] ──► [jury_S_only]  │       │
│  │                                                                       │       │
│  │  FAIL_MISSING_EV ──► [researcher_targeted] ──► [citation_manager]   │       │
│  │                                                                       │       │
│  │  PANEL      ──► [panel_discussion] ──► [aggregator]                 │       │
│  │                                                                       │       │
│  │  VETO       ──► [reflector] ──► (SURGICAL|PARTIAL|FULL path above)  │       │
│  │                                                                       │       │
│  │  BUDGET_HARD_STOP ──► [publisher]  (partial document)               │       │
│  └───────────────────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## §4.3 Phase C — Post-Flight QA

```
┌──────────────────────────────────────────────┐
│  PHASE C: POST-FLIGHT QA                     │
│                                              │
│  [post_qa]                                   │
│    ├─ contradiction_detector (cross-section) │
│    ├─ format_validator (±10% target_words)   │
│    └─ completeness_check (all sections in    │
│         Store match outline)                 │
│       │                                      │
│  length_out_of_range? ──► [length_adjuster]  │
│  conflicts? ──► [await_human] (optional)     │
│       │                                      │
│       └──► PHASE D                           │
└──────────────────────────────────────────────┘
```

---

## §4.4 Phase D — Publisher and Output

```
┌──────────────────────────────────────────────────┐
│  PHASE D: PUBLISHER & OUTPUT                     │
│                                                  │
│  [publisher]                                     │
│    ├─ assemble sections from Store (immutable)   │
│    ├─ apply DOCX template (python-docx)          │
│    ├─ generate bibliography (citation_style)     │
│    ├─ render formats: docx/pdf/md/json/latex/html│
│    └─ upload to S3/MinIO                         │
│       │                                          │
│  [feedback_collector] (post-delivery, async)     │
│       │                                          │
│  END ◄─────────────────────────────────────────  │
└──────────────────────────────────────────────────┘
```

---

## §4.5 LangGraph Node List and Edge Conditions

```python
from langgraph.graph import StateGraph, END
from typing import Literal

NODES: list[str] = [
    "preflight", "budget_estimator", "planner", "await_outline",
    "researcher", "citation_manager", "citation_verifier",
    "source_sanitizer", "source_synthesizer",
    "writer_a", "writer_b", "writer_c",          # MoW proposers
    "jury_multi_draft", "fusor",                  # MoW synthesis
    "writer_single",                              # non-MoW or iter>=2
    "post_draft_analyzer", "researcher_targeted",
    "style_linter", "style_fixer",
    "metrics_collector",
    "jury",                                       # runs jury_R, jury_F, jury_S in gather
    "aggregator",
    "reflector", "span_editor", "diff_merger",
    "oscillation_check",
    "panel_discussion",
    "context_compressor", "coherence_guard",
    "section_checkpoint",
    "await_human",
    "budget_controller",
    "post_qa",
    "length_adjuster",                            # Phase C: direct word-count correction
    "publisher",
    "feedback_collector",
]

# --- Edge condition functions (pure, no side effects) ---

def route_outline_approval(state: "DocumentState") -> Literal["approved", "rejected"]:
    return "approved" if state["outline_approved"] else "rejected"

def route_mow(state: "DocumentState") -> Literal["mow", "single"]:
    preset = state["config"]["user"]["quality_preset"]
    sec = state["outline"][state["current_section_idx"]]
    if preset == "economy":
        return "single"
    if sec["target_words"] < 400:
        return "single"
    if state.get("human_intervention_required"):
        return "single"
    if state["current_iteration"] > 1:
        return "single"
    return "mow"

def route_post_draft_gap(state: "DocumentState") -> Literal["gap", "no_gap"]:
    return "gap" if state.get("post_draft_gaps") else "no_gap"

def route_style_lint(state: "DocumentState") -> Literal["violation", "clean"]:
    return "violation" if state.get("style_lint_violations") else "clean"

# NOTE: route_after_aggregator() canonical definition is in §9.4.
# The LangGraph edges below reference the return literals from that definition.
# Return values: "approved", "fail_reflector", "fail_style", "panel",
#                "veto", "fail_missing_ev", "budget_hard_stop", "force_approve"

def route_after_oscillation(state: "DocumentState") -> Literal[
    "continue", "escalate_human"
]:
    # Budget threshold warnings are handled by the BudgetController node,
    # which runs before every Writer/Jury call. The oscillation detector
    # only determines whether the section loop can continue or must escalate.
    if state.get("oscillation_detected"):
        return "escalate_human"
    return "continue"

def route_after_coherence(state: "DocumentState") -> Literal[
    "no_conflict", "soft_conflict", "hard_conflict"
]:
    conflicts = state.get("coherence_conflicts", [])
    if not conflicts:
        return "no_conflict"
    if any(c["level"] == "HARD" for c in conflicts):
        return "hard_conflict"
    return "soft_conflict"

def route_next_section(state: "DocumentState") -> Literal["next_section", "all_done"]:
    next_idx = state["current_section_idx"] + 1
    return "all_done" if next_idx >= state["total_sections"] else "next_section"

# route_after_reflector() is defined in §12.5 and routes to span_editor or
# writer_single based on fresh reflector_output scope.

def route_post_qa(state: "DocumentState") -> Literal[
    "length_out_of_range", "conflicts", "ok"
]:
    # length_out_of_range routes to 'length_adjuster' (§5.22), NOT to 'reflector'.
    # The reflector requires all_verdicts_history for section-level context which
    # is unavailable in Phase C. length_adjuster invokes the Writer directly with
    # an explicit word-count instruction, bypassing the full jury/reflector loop.
    if not state.get("format_validated"):
        return "length_out_of_range"
    if state.get("coherence_conflicts"):
        return "conflicts"
    return "ok"


# --- LangGraph graph definition ---

def build_graph(checkpointer):
    g = StateGraph(DocumentState)

    # Register nodes
    for node_name in NODES:
        pass  # nodes registered via g.add_node(name, fn) in implementation

    g.set_entry_point("preflight")

    # Phase A: Setup
    g.add_edge("preflight", "budget_estimator")
    g.add_edge("budget_estimator", "planner")
    g.add_edge("planner", "await_outline")
    g.add_conditional_edges("await_outline", route_outline_approval,
        {"approved": "researcher", "rejected": "planner"})

    # Phase B: Section loop — research pipeline
    g.add_edge("researcher", "citation_manager")
    g.add_edge("citation_manager", "citation_verifier")
    g.add_edge("citation_verifier", "source_sanitizer")
    g.add_edge("source_sanitizer", "source_synthesizer")
    g.add_edge("source_synthesizer", "post_draft_analyzer")

    # MoW / single-writer branch (resolved at runtime via route_mow)
    # Both paths converge at style_linter
    g.add_edge("fusor", "style_linter")
    g.add_edge("writer_single", "style_linter")

    # Post-draft gap integration uses span_editor → diff_merger, then continues
    g.add_edge("researcher_targeted", "citation_manager")   # targeted re-research

    # Style gate
    g.add_conditional_edges("style_linter", route_style_lint,
        {"violation": "style_fixer", "clean": "metrics_collector"})
    g.add_edge("style_fixer", "style_linter")   # re-lint after fix

    # Jury
    g.add_edge("metrics_collector", "jury")
    g.add_edge("jury", "aggregator")

    # Canonical routing: return literals from §9.4 route_after_aggregator()
    g.add_conditional_edges("aggregator", route_after_aggregator, {
        "approved":          "context_compressor",
        "force_approve":     "context_compressor",   # force_approve checked first in §9.4
        "fail_reflector":    "reflector",
        "fail_style":        "style_fixer",
        "panel":             "panel_discussion",
        "veto":              "reflector",
        "fail_missing_ev":   "researcher_targeted",
        "budget_hard_stop":  "publisher",
    })

    # Span editor pipeline (SURGICAL scope from reflector — see §12.5)
    g.add_edge("span_editor", "diff_merger")
    g.add_edge("diff_merger", "style_linter")   # re-lint after surgical edits

    # Reflector → oscillation check → writer or escalate
    g.add_edge("reflector", "oscillation_check")
    g.add_conditional_edges("oscillation_check", route_after_oscillation, {
        "continue":       "writer_single",
        "escalate_human": "await_human",
    })

    g.add_edge("panel_discussion", "aggregator")

    # Section approval pipeline
    g.add_edge("context_compressor", "coherence_guard")
    g.add_conditional_edges("coherence_guard", route_after_coherence, {
        "no_conflict":   "section_checkpoint",
        "soft_conflict": "section_checkpoint",
        "hard_conflict": "await_human",
    })
    g.add_conditional_edges("section_checkpoint", route_next_section, {
        "next_section": "researcher",
        "all_done":     "post_qa",
    })

    # Phase C: Post-QA
    g.add_conditional_edges("post_qa", route_post_qa, {
        "length_out_of_range": "length_adjuster",
        "conflicts":           "await_human",
        "ok":                  "publisher",
    })
    g.add_edge("length_adjuster", "publisher")

    # Phase D
    g.add_edge("publisher", END)

    return g.compile(checkpointer=checkpointer)
```

---

## §4.6 DocumentState TypedDict

```python
from __future__ import annotations
from typing import TypedDict, Annotated, Any
from langgraph.graph.message import add_messages

class BudgetState(TypedDict):
    max_dollars: float
    spent_dollars: float
    projected_final: float
    regime: Literal["Economy", "Balanced", "Premium"]
    css_content_threshold: float      # 0.65 | 0.50 | 0.45  (per regime)
    css_panel_threshold: float        # always 0.50 — triggers Panel Discussion
    css_style_threshold: float        # always 0.80
    css_approved_strong: float        # always 0.85 — strong approval, no notes
    css_approved_with_notes: float    # always 0.70 — approved with dissent logged
    max_iterations: int               # 2 | 4 | 8
    jury_size: int                    # 1 | 2 | 3
    warn_pct: float                   # 0.70
    alert_pct: float                  # 0.90

class OutlineSection(TypedDict):
    idx: int
    title: str
    scope: str
    target_words: int
    dependencies: list[int]           # indices of prerequisite sections

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
    reliability_score: float          # 0.0–1.0
    abstract: str | None
    nli_entailment: float | None      # DeBERTa score 0.0–1.0
    http_verified: bool
    ghost_flag: bool

class JudgeVerdict(TypedDict):
    judge_slot: Literal["R1","R2","R3","F1","F2","F3","S1","S2","S3"]
    model: str
    dimension_scores: dict[str, float]   # factual/reasoning/style/citation 0–10
    pass_fail: bool
    veto_category: Literal[
        "fabricated_source","factual_error",
        "logical_contradiction","plagiarism"
    ] | None
    confidence: Literal["low", "medium", "high"]
    motivation: str
    failed_claims: list[str]
    missing_evidence: list[str]
    external_sources_consulted: list[str]   # Judge F micro-search only
    css_contribution: float

class AggregatorVerdict(TypedDict):
    verdict_type: Literal[
        "APPROVED","VETO","MISSING_EVIDENCE",
        "FAIL_CONTENT","FAIL_STYLE","PANEL_REQUIRED"
    ]
    css_content: float           # 0.0–1.0
    css_style: float             # 0.0–1.0
    css_final: float             # weighted average for Run Report
    dissenting_reasons: list[str]
    best_elements: list[dict]    # for Fusor: {judge_slot, text_excerpt, rationale}

class ReflectorOutput(TypedDict):
    scope: Literal["SURGICAL", "PARTIAL", "FULL"]
    feedback_items: list[dict]   # {id, severity, category, affected_text,
                                 #  context_before, context_after, action,
                                 #  replacement_length_hint, priority}

class StyleLintViolation(TypedDict):
    rule_id: str
    level: Literal["L1", "L2"]
    category: str
    position: int                # char offset in draft
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

class DocumentState(TypedDict):
    # ── Identifiers ──────────────────────────────────────────────────────────
    doc_id: str
    thread_id: str
    user_id: str
    status: Literal[
        "initializing","running","paused",
        "awaiting_approval","completed","failed","cancelled"
    ]

    # ── Config (frozen after preflight) ──────────────────────────────────────
    config: dict[str, Any]         # validated DocumentConfig (see §29)
    style_profile: dict[str, Any]  # frozen ruleset (see §26)
    style_exemplar: str | None     # §3B.2: approved sample paragraph
    quality_preset: Literal["Economy", "Balanced", "Premium"]

    # ── Outline (Phase A) ────────────────────────────────────────────────────
    outline: list[OutlineSection]
    outline_approved: bool

    # ── Section loop control ─────────────────────────────────────────────────
    current_section_idx: int
    total_sections: int

    # ── Current section state (reset each section) ───────────────────────────
    current_sources: list[Source]
    synthesized_sources: str       # Source Synthesizer output (§5.6)
    current_draft: str
    current_iteration: int         # resets to 1 each new section
    post_draft_gaps: list[dict]    # §5.11: [{category, description, query}]
    style_lint_violations: list[StyleLintViolation]
    jury_verdicts: list[JudgeVerdict]   # latest round
    all_verdicts_history: list[list[JudgeVerdict]]  # all rounds this section
    aggregator_verdict: AggregatorVerdict
    reflector_output: ReflectorOutput | None
    css_history: list[float]       # css_final per iteration this section
    draft_embeddings: list[list[float]]  # for semantic oscillation check §13.2

    # ── Force-approve flag (set by §19.5 when current_iteration >= max_iterations) ──
    force_approve: bool            # checked first in route_after_aggregator (§9.4)
                                   # routes to 'approved' with WARNING log entry

    # ── MoW state ────────────────────────────────────────────────────────────
    mow_drafts: list[str]          # [draft_A, draft_B, draft_C]
    mow_css_per_draft: list[float]
    fusor_draft: str | None

    # ── Approved sections store ───────────────────────────────────────────────
    approved_sections: list[dict]  # {idx, title, content, css_final,
                                   #  sources, warnings, verdicts_history,
                                   #  approved_at}
    compressed_context: str        # Context Compressor output §5.16

    # ── Writer Memory (§5.18, persists across sections) ─────────────────────
    writer_memory: dict[str, Any]  # {recurring_forbidden, glossary,
                                   #  citation_tendency, style_drift_index}

    # ── Budget (§19) ─────────────────────────────────────────────────────────
    budget: BudgetState

    # ── Oscillation (§13) ────────────────────────────────────────────────────
    oscillation_detected: bool
    oscillation_type: Literal["CSS", "SEMANTIC", "WHACK_A_MOLE"] | None

    # ── Panel Discussion (§11) ───────────────────────────────────────────────
    panel_active: bool
    panel_round: int               # max 2; see §11.2
    panel_anonymized_log: list[dict]

    # ── Coherence / Post-QA ──────────────────────────────────────────────────
    coherence_conflicts: list[CoherenceConflict]
    format_validated: bool

    # ── Human-in-the-loop ────────────────────────────────────────────────────
    human_intervention_required: bool
    active_escalation: dict | None  # {type, trigger, options}

    # ── Run Companion (§6) ───────────────────────────────────────────────────
    companion_messages: Annotated[list, add_messages]

    # ── Output ───────────────────────────────────────────────────────────────
    output_paths: dict[str, str]   # {format: s3_url}
    run_metrics: dict[str, Any]    # full Run Report payload §30.4
```

---

**Phase summary:**

| Phase | Entry condition | Exit condition |
|-------|----------------|----------------|
| A | run created | `outline_approved == True` |
| B | Phase A complete | `current_section_idx == total_sections` |
| C | Phase B complete | `format_validated == True` |
| D | Phase C complete | `output_paths` populated → `END` |

**Cross-refs:** agents §5, jury §8, aggregator §9, budget §19, oscillation §13, coherence §15, MoW §7, panel §11, reflector §12, style linter/fixer §5.9–5.10, context compressor §14, section_checkpoint §5.21, jury_multi_draft §7.5, length_adjuster §5.22.

<!-- SPEC_COMPLETE -->