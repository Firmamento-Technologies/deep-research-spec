# 07_mixture_of_writers.md
## §7 — Mixture-of-Writers (MoW) + Fusor Agent

---

### §7.1 Activation Conditions

MoW is implemented **entirely internally** within the single `writer` graph node. When MoW
conditions are met, the writer node dispatches three proposer instances (W-A/W-B/W-C) via
`asyncio.gather`, runs an internal jury evaluation, and invokes Fusor — returning a single
fused draft to the graph. The graph sees only one `writer` node with one outbound edge
(`writer → post_draft_analyzer`). There are no separate external graph nodes for `writer_a`,
`writer_b`, `writer_c`, `jury_multi_draft`, or `fusor`.

```python
mow_active: bool = (
    quality_preset != "economy"
    AND section.estimated_words >= 400
    AND current_iteration == 1
    AND NOT human_escalation_occurred_this_section
)
```

| Condition | Type | Disables MoW |
|-----------|------|--------------|
| `quality_preset == "economy"` | `Literal["economy"]` | ✓ |
| `section.estimated_words < 400` | `int` | ✓ |
| `current_iteration > 1` | `int` | ✓ |
| `human_escalation_occurred_this_section` | `bool` | ✓ |

When `mow_active == False`: single Writer path executes (see §5.7).

---

### §7.2 Writer Proposer Table

| ID | Role | Model | Temp | Angle injected in prompt |
|----|------|-------|------|--------------------------|
| W-A | Coverage | `anthropic/claude-opus-4-5` | 0.30 | Completeness, scope coverage, explicit argumentative structure |
| W-B | Argumentation | `anthropic/claude-opus-4-5` | 0.60 | Logical soundness, argument hierarchy, central thesis clarity |
| W-C | Readability | `anthropic/claude-opus-4-5` | 0.80 | Narrative fluency, syntactic variety, accessibility |

All three run in `asyncio.gather()` inside the writer node. Same model, different temperature + angle = semantic diversity.

---

### §7.3 Angle Profiles per Style

```python
WRITER_ANGLES: dict[str, dict[Literal["W-A","W-B","W-C"], str]] = {
    "academic":        {"W-A": "citation coverage, IMRaD structure",
                        "W-B": "cautious phrasing, logical flow",
                        "W-C": "readability, zero redundant hedging"},
    "business":        {"W-A": "data-driven completeness, implicit exec summary",
                        "W-B": "insights hierarchy, actionable recommendations",
                        "W-C": "short sentences, jargon elimination"},
    "technical":       {"W-A": "terminological precision, definitions upfront",
                        "W-B": "specs→implementation→trade-offs, zero ambiguity",
                        "W-C": "concrete examples, specific metrics (no 'fast' without benchmark)"},
    "blog":            {"W-A": "strong lede, frequent subheadings, all angles",
                        "W-B": "clear thesis, linear argument, non-repetitive conclusion",
                        "W-C": "conversational tone, syntactic variety, natural inline links"},
    "software_spec":   {"W-A": "full feature coverage, typed contracts",
                        "W-B": "constraint logic, explicit error paths",
                        "W-C": "AI-agent readable, zero ambiguity"},
    "journalistic":    {"W-A": "inverted pyramid, all newsworthy angles",
                        "W-B": "primary source attribution, claim-evidence alignment",
                        "W-C": "lede strength, active voice"},
    "narrative_essay": {"W-A": "all sub-themes covered",
                        "W-B": "narrative arc, beginning/development/conclusion",
                        "W-C": "rhythmic variation, concrete openings"},
}
```

---

### §7.4 Fusor Agent

```
AGENT: Fusor [§7.4]
RESPONSIBILITY: synthesize 3 proposer drafts into 1 superior fused draft
  (invoked internally by the writer node — never called directly from the graph)
MODEL: openai/o3 / TEMP: 0.2 / MAX_TOKENS: 6000
INPUT:
  drafts: list[tuple[Literal["W-A","W-B","W-C"], str, float]]  # (id, text, css_individual)
  best_elements: list[BestElement]  # see §7.5
  base_draft_id: Literal["W-A","W-B","W-C"]
  compressed_context: str  # see §14
  style_exemplar: str  # see §3B.2
OUTPUT: FusedDraft
CONSTRAINTS:
  MUST use draft with highest css_individual as structural base
  MUST integrate ≥1 best_element from each non-base draft if jury-identified
  NEVER add claims absent from all 3 input drafts
  NEVER optimize style (Writer handles style in subsequent iterations)
  ALWAYS produce invisible fusion (no detectable seams)
  ALWAYS invoked internally by writer node; NEVER appears as a separate graph node
ERROR_HANDLING:
  parse_failure -> retry once with simplified prompt -> fallback to base_draft verbatim
  all_models_fail -> return base_draft, set fused=False in state
CONSUMES: [current_draft_proposals, jury_best_elements, compressed_context, style_exemplar]
PRODUCES: [current_draft] -> DocumentState (via writer node return value)
```

```python
class BestElement(TypedDict):
    source_draft_id: Literal["W-A", "W-B", "W-C"]
    verbatim_text: str          # exact quote from non-winning draft
    reason: str                 # why jury flagged it
    category: Literal["evidence", "phrasing", "structure", "argument"]

class FusedDraft(TypedDict):
    text: str
    base_draft_id: Literal["W-A", "W-B", "W-C"]
    elements_integrated: list[BestElement]
    fused: bool                 # False if fallback triggered
```

Fusor runs **exactly once per section, first iteration only**. Because `mow_active` is gated on `current_iteration == 1` (§7.1), the Fusor is structurally never reachable after iteration 1. If the fused draft fails Phase 2 jury evaluation, the flow transitions to `reflector` → single `writer` (standard loop) for all subsequent iterations; Fusor is not re-invoked.

---

### §7.5 Internal MoW Jury Evaluation Sequence

The MoW jury evaluation is **internal to the writer node**. It is not a separate graph node.
The writer node implements it as follows when `mow_active == True`:

**Phase 1 — Selection + Integration** (internal to writer node):

Uses all 9 judges (same mini-jury composition as standard jury: 3 × Reasoning, 3 × Factual, 3 × Style). Each judge evaluates all 3 MoW drafts sequentially, producing 27 total LLM calls (9 judges × 3 drafts). Cascading tiers apply per draft independently. A VETO on draft X does not affect evaluation of drafts Y and Z.

```python
class PerDraftVerdict(TypedDict):
    draft_id: Literal["W-A", "W-B", "W-C"]
    css_individual: float       # 0.0–1.0; computed same as §9.1 but scoped
                                # to this draft's 9-judge panel
    pass_fail: bool
    veto_category: Optional[Literal["fabricated_source","factual_error",
                                    "logical_contradiction","plagiarism"]]
    best_elements: list[BestElement]  # from non-winning drafts only
```

```python
def select_base_draft(
    per_draft_verdicts: list[PerDraftVerdict],
) -> tuple[Literal["W-A","W-B","W-C"], list[BestElement]]:
    # Exclude drafts vetoed with fabricated_source entirely
    eligible = [
        v for v in per_draft_verdicts
        if v["veto_category"] != "fabricated_source"
    ]
    if not eligible:
        # All drafts vetoed: fall back to single-writer path
        raise MultiDraftAbortError("all drafts vetoed with fabricated_source")

    # argmax css_individual among eligible drafts
    base = max(eligible, key=lambda v: v["css_individual"])

    # Collect best_elements from all non-base drafts that are usable
    best_elements: list[BestElement] = []
    for v in eligible:
        if v["draft_id"] != base["draft_id"]:
            best_elements.extend(v["best_elements"])

    return base["draft_id"], best_elements
```

**Phase 1 CSS values are stored in `run_metrics.jury_multi_draft` only. They do NOT enter `css_history`.** `css_history` receives only Phase 2 (fused draft) CSS values.

**Phase 2 — Fused Draft Approval**: after Fusor produces the fused draft, the writer node returns it as `current_draft`. The standard graph path (`writer → post_draft_analyzer → style_linter → metrics_collector → budget_controller → jury → aggregator`) then runs as normal. CSS from the standard jury in Phase 2 enters `css_history`.

**Fallback when all drafts vetoed with fabricated_source:**
The writer node catches `MultiDraftAbortError`, logs `MULTI_DRAFT_ABORT`, and falls back to invoking a single-writer call as if `mow_active == False`. The returned draft is identical in structure to the standard path. The graph is unaffected.

---

### §7.6 Graph Topology — Authoritative Statement

> **AUTHORITATIVE**: MoW is fully internal to the `writer` node. The graph topology
> defined in §4.5 is the single source of truth. The following external nodes do NOT
> exist as separate graph nodes and MUST NOT appear in `build_graph()`:
> - `writer_a`, `writer_b`, `writer_c` (proposers are internal asyncio tasks)
> - `writer_mow_gather` (the gather is internal to the writer node)
> - `jury_multi_draft` (Phase 1 jury is internal to the writer node)
> - `fusor` (Fusor is invoked internally by the writer node)
> - `route_after_writer` (no conditional edge exists between writer and post_draft_analyzer;
>   the edge is always `writer → post_draft_analyzer`)

The outbound edge from `writer` is unconditional:
```python
g.add_edge("writer", "post_draft_analyzer")
```

This single edge applies regardless of whether MoW was active internally. The writer node
always returns exactly one `current_draft` value to the graph.

---

### §7.7 Budget Impact and Break-Even

**Cost multiplier, first iteration:**

| Component | Baseline | MoW enabled |
|-----------|----------|-------------|
| Writer calls | 1× | 3× |
| Jury calls | cascading | internal Phase 1 (27 calls) + standard Phase 2 |
| Fusor | — | 1× o3 call (internal) |
| **Total first iter** | 1.0× | **3.5–4.0×** |

**Break-even formula:**

```
break_even_satisfied = (
    mow_iterations_saved >= 1.5
)

mow_net_cost_ratio = (
    cost_mow_first_iter / cost_single_writer_iter
) - mow_iterations_saved

# MoW profitable when mow_net_cost_ratio < 0
# i.e., iterations_saved > ~2.5; adjusted by cascading: break-even at ≈1.5 saved iterations
```

**Quality preset → strategy mapping:**

| `quality_preset` | First iteration strategy | Avg iterations expected |
|------------------|--------------------------|------------------------|
| `"economy"` | single Writer | 2.5 |
| `"balanced"` | MoW K=3 + Fusor (internal) | 1.8 (initial estimate) |
| `"premium"` | MoW K=3 + Fusor (internal) | 1.5 (initial estimate) |

Estimates auto-update after 50 runs: system tracks `iterations_per_section` keyed by `mow_enabled: bool` → implicit A/B test. Stored in `run_metrics.mow_calibration`.

**Budget Estimator integration (§19.1):**

```python
def estimate_section_cost_mow(
    words: int,
    model_pricing: dict[str, float],
    quality_preset: Literal["economy", "balanced", "premium"],
    avg_iter_mow: float = 1.8,
    avg_iter_single: float = 2.5,
) -> float:
    tokens = words * 1.5
    if quality_preset == "economy" or words < 400:
        return tokens * model_pricing["writer"] * avg_iter_single
    writer_cost = tokens * model_pricing["writer"] * 3  # 3 proposers (internal)
    fusor_cost = tokens * model_pricing["o3"]
    # 27 calls (9 judges × 3 drafts) with cascading reduces effective cost
    jury_cost = tokens * 0.4 * model_pricing["jury_avg"] * 9 * 1.5
    return (writer_cost + fusor_cost + jury_cost) * avg_iter_mow
```

---

### ASCII Flow: MoW vs Single-Writer

```
┌─────────────────────────────────────────────────────────────────┐
│ MoW PATH (quality_preset ∈ {"balanced","premium"}, words ≥ 400, │
│           iteration == 1, no prior human escalation)            │
│ ALL of the following is INTERNAL to the 'writer' graph node.    │
└─────────────────────────────────────────────────────────────────┘

[writer node receives: compressed_corpus, citation_map, ...]
        │
        ▼  (mow_active == True — detected internally)
        │
  ┌─────┴──────────────────────────────────────────────────┐
  │  INTERNAL: asyncio.gather(W-A, W-B, W-C)              │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
  │  │  W-A     │  │  W-B     │  │  W-C     │             │
  │  │ temp=0.3 │  │ temp=0.6 │  │ temp=0.8 │             │
  │  │ Coverage │  │ Argument │  │ Readab.  │             │
  │  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
  │       └─────────────┼─────────────┘                    │
  │                     ▼                                   │
  │  INTERNAL: Phase 1 jury (27 LLM calls)                 │
  │    → css_individual per draft                           │
  │    → best_elements from non-winners                     │
  │    → base_draft = argmax(css_individual)                │
  │    → Phase 1 CSS → run_metrics only (NOT css_history)  │
  │                     │                                   │
  │  all fabricated?    │  base selected                    │
  │  ↓ (fallback)       ▼                                   │
  │  single_writer  [INTERNAL: Fusor (o3)]                  │
  │  path              ↓                                    │
  │              fused_draft                                │
  └────────────────────┬────────────────────────────────────┘
                       │
                       ▼
        [writer node returns: current_draft (fused)]
                       │
            (unconditional graph edge)
                       │
                       ▼
          [post_draft_analyzer]   ← standard graph continues
                       │
              [style_linter]
                       │
          [metrics_collector]
                       │
          [budget_controller]
                       │
              [jury]  ← Phase 2: standard jury
                       │        CSS → css_history
                       ▼
          CSS ≥ threshold?
            YES → [coherence_guard] → [context_compressor] → [section_checkpoint]
            NO  → [reflector] → route_after_reflector() →
                    SURGICAL/PARTIAL → [oscillation_check] → [span_editor] | [writer]
                    FULL            → [await_human]
                    (MoW NOT re-activated; mow_active gated on iteration == 1)

┌─────────────────────────────────────────────────────────────────┐
│ SINGLE-WRITER PATH (economy / words<400 / iteration>1 /         │
│                     post-escalation / MoW fallback)             │
│ Also internal to 'writer' node when mow_active == False.        │
└─────────────────────────────────────────────────────────────────┘

[writer node receives inputs]
        │
        ▼  (mow_active == False — single call)
[writer → single LLM call → current_draft]
        │
        ▼  (same unconditional edge)
[post_draft_analyzer] → ... → [jury] → [aggregator] → routing
```

---

### KPI Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| `mow_first_attempt_approval_rate` | > 0.55 | sections approved after fused draft / total MoW sections |
| `mow_vs_single_delta` | > +0.15 | approval_rate_mow - approval_rate_single |
| `iterations_saved_delta` | < -0.8 | avg_iter_mow - avg_iter_single |
| `fusor_integration_rate` | > 0.60 | sections where ≥2 proposers contributed elements |
| `break_even_satisfied_rate` | > 0.70 | runs where `mow_iterations_saved >= 1.5` |

Tracked in `run_metrics.mow_kpi` per run; aggregated in Grafana (see §23.3).

---

### DocumentState Fields (MoW-specific)

```python
# Fields added/consumed by MoW subsystem within DRSState (see §4.6)
# These are written by the writer node when MoW executes internally.
class MoWState(TypedDict):
    mow_active: bool
    mow_drafts: list[str]           # [draft_A, draft_B, draft_C] — stored for debugging
    mow_css_per_draft: list[float]  # Phase 1 css_individual values
    fusor_draft: Optional[str]      # fused draft before returning as current_draft
    mow_iterations_saved: float     # updated post-section: avg_iter_single - actual_iter
```

Cross-refs: §5.7 (Writer — single node containing MoW logic), §5.13 (Fusor — invoked internally),
§8.1–§8.3 (jury machinery reused for Phase 1 internal evaluation), §9.1 (CSS formula),
§9.3 (THRESHOLD_TABLE), §19.1 (Budget Estimator), §14 (Context Compressor → `compressed_context`),
§3B.2 (Style Exemplar injection).

<!-- SPEC_COMPLETE -->