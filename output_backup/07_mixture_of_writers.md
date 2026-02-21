# 07_mixture_of_writers.md
## §7 — Mixture-of-Writers (MoW) + Fusor Agent

---

### §7.1 Activation Conditions

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

When `mow_active == False`: single Writer executes (see §5.7).

---

### §7.2 Writer Proposer Table

| ID | Role | Model | Temp | Angle injected in prompt |
|----|------|-------|------|--------------------------|
| W-A | Coverage | `anthropic/claude-opus-4-5` | 0.30 | Completeness, scope coverage, explicit argumentative structure |
| W-B | Argumentation | `anthropic/claude-opus-4-5` | 0.60 | Logical soundness, argument hierarchy, central thesis clarity |
| W-C | Readability | `anthropic/claude-opus-4-5` | 0.80 | Narrative fluency, syntactic variety, accessibility |

All three run in `asyncio.gather()`. Same model, different temperature + angle = semantic diversity (see Rethinking MoA, Self-MoA result).

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
ERROR_HANDLING:
  parse_failure -> retry once with simplified prompt -> fallback to base_draft verbatim
  all_models_fail -> return base_draft, set fused=False in state
CONSUMES: [current_draft_proposals, jury_best_elements, compressed_context, style_exemplar]
PRODUCES: [current_draft] -> DocumentState
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

### §7.5 Jury Multi-Draft Evaluation Sequence

Two sequential phases:

**Phase 1 — Selection + Integration** (`jury_multi_draft` node; see §4.5):

Phase 1 uses all 9 judges (same mini-jury composition as standard jury: 3 × Reasoning, 3 × Factual, 3 × Style). Each judge evaluates all 3 MoW drafts sequentially, producing 27 total LLM calls (9 judges × 3 drafts). Cascading tiers apply per draft independently: each draft's tier1→tier2→tier3 escalation is resolved before moving to the next draft within the same judge slot. A VETO on draft X does not affect evaluation of drafts Y and Z; each draft's verdict is fully independent.

```
AGENT: JuryMultiDraft [§7.5]
RESPONSIBILITY: evaluate all 3 MoW proposer drafts, extract best_elements,
                select base_draft for Fusor
MODEL: same model assignments as standard jury (§8.1–§8.3) / TEMP: per slot
MAX_TOKENS: per slot (same as standard jury)
INPUT:
  drafts: list[tuple[Literal["W-A","W-B","W-C"], str]]  # (id, text)
  compressed_context: str
  style_exemplar: str
  section_metadata: dict  # title, scope, target_words
INVOCATION:
  - 9 judges × 3 drafts = 27 total LLM calls
  - Each judge evaluates drafts W-A, W-B, W-C in sequence (order randomized
    per judge to prevent position bias)
  - Cascading tiers (tier1→tier2→tier3) apply per draft independently within
    each mini-jury slot (same logic as §8.5)
  - All 3 mini-juries run in asyncio.gather() across drafts; within each
    mini-jury, the 3 draft evaluations are sequential per judge
OUTPUT:
  per_draft_verdicts: list[PerDraftVerdict]   # one entry per draft (3 total)
  best_elements: list[BestElement]            # from non-winning drafts only
  base_draft_id: Literal["W-A","W-B","W-C"]  # argmax(css_individual)
CONSTRAINTS:
  VETO on draft X does NOT affect evaluation of drafts Y and Z
  VETO category "fabricated_source" renders entire draft unusable
    (best_elements from that draft are discarded)
  VETO category other → draft excluded as base; best_elements still usable
  base_draft selection: argmax(css_individual) across all 9 judges per draft
  tie-break: mini-jury F (Factual) individual CSS wins
  Phase 1 CSS values stored in run_metrics ONLY; do NOT enter css_history
    (css_history receives only Phase 2 fused-draft CSS; see §9.1)
ERROR_HANDLING:
  judge_call_failure -> retry once -> fallback to next tier model
  all_tiers_fail for one judge slot -> proceed with 2/3 judges, set
    JURY_DEGRADED flag, log warning
  all_drafts_vetoed_fabricated_source -> abort MoW, fall back to single
    Writer as if mow_active == False, log MULTI_DRAFT_ABORT event
PRODUCES:
  [per_draft_verdicts, best_elements, base_draft_id] -> Fusor input
  [run_metrics.jury_multi_draft] -> stored Phase 1 CSS values
```

```python
class PerDraftVerdict(TypedDict):
    draft_id: Literal["W-A", "W-B", "W-C"]
    css_individual: float       # 0.0–1.0; computed same as §9.1 but scoped
                                # to this draft's 9-judge panel
    pass_fail: bool
    veto_category: Optional[Literal["fabricated_source","factual_error",
                                    "logical_contradiction","plagiarism"]]
    best_elements: list[BestElement]  # from non-winning drafts only;
                                      # empty if this draft wins or is vetoed
                                      # with fabricated_source
```

**base_draft selection logic:**

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

**Phase 2 — Fused Draft Approval**: standard jury flow (see §8). CSS from Phase 2 only enters `css_history`. Phase 1 CSS values are stored in `run_metrics.jury_multi_draft` but do NOT feed Oscillation Detector.

---

### §4.5 Graph Nodes — MoW Extension

The following nodes are added to the LangGraph definition to support the MoW path. They integrate with the standard graph defined in §4.5 of the main architecture spec.

```
NODES (MoW-specific additions):

  jury_multi_draft   [§7.5]
    Invoked when mow_active == True (current_iteration == 1, not economy,
    section.estimated_words >= 400, no human escalation).
    Evaluates all 3 proposer drafts from asyncio.gather(W-A, W-B, W-C).
    Produces: per_draft_verdicts, best_elements, base_draft_id.
    EDGES:
      → fusor          (default: base_draft selected, best_elements collected)
      → writer_single  (fallback: all drafts vetoed fabricated_source →
                        MULTI_DRAFT_ABORT; treat as mow_active == False)

  fusor              [§7.4]
    Receives output of jury_multi_draft.
    Produces: FusedDraft (current_draft in DocumentState).
    EDGES:
      → metrics_collector  (fused draft enters standard pipeline)

EDGE INTEGRATION WITH STANDARD GRAPH:

  After fusor → metrics_collector → style_linter → jury (Phase 2, standard)
  The jury (Phase 2) node is the SAME standard jury node used for
  single-writer iterations. CSS produced here enters css_history normally.

  If Phase 2 jury fails (CSS < threshold, no VETO escalation):
    → reflector → oscillation_check → writer  (single Writer, iteration 2+)
    MoW path is NOT re-entered on iteration > 1 (gated by §7.1 condition).

COMPLETE MoW SUBGRAPH:

  [writer_mow_gather]          # asyncio.gather(W-A, W-B, W-C)
       ↓
  [jury_multi_draft]           # Phase 1: 27 calls, per_draft_verdicts
       ↓ (all_fabricated_source → writer_single)
  [fusor]                      # Phase 2 input preparation
       ↓
  [metrics_collector]          # standard node, fused draft
       ↓
  [style_linter]               # standard node
       ↓
  [jury]                       # Phase 2: standard jury, CSS → css_history
       ↓
  CSS >= threshold?
    YES → [context_compressor] → [coherence_guard] → [section_checkpoint]
    NO  → [reflector] → [oscillation_check] → [writer]  # single writer
                                                          # iteration++ 
                                                          # MoW NOT re-activated
```

---

### §7.6 Budget Impact and Break-Even

**Cost multiplier, first iteration:**

| Component | Baseline | MoW enabled |
|-----------|----------|-------------|
| Writer calls | 1× | 3× |
| Jury calls | cascading | multi-draft (27 calls) + Fusor (≈1.5× jury) |
| Fusor | — | 1× o3 call |
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
# i.e., iterations_saved > (3.5 - 1.0) = 2.5 / 1.0 = 2.5 ... 
# adjusted by cascading: break-even at ≈1.5 saved iterations
```

**Quality preset → strategy mapping:**

| `quality_preset` | First iteration strategy | Avg iterations expected |
|------------------|--------------------------|------------------------|
| `"economy"` | single Writer | 2.5 |
| `"balanced"` | MoW K=3 + Fusor | 1.8 (initial estimate) |
| `"premium"` | MoW K=3 + Fusor | 1.5 (initial estimate) |

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
    writer_cost = tokens * model_pricing["writer"] * 3  # 3 proposers
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
└─────────────────────────────────────────────────────────────────┘

[Source Synthesizer] ──────────────────────────────────────────┐
                                                               ▼
                          ┌──────────┐  ┌──────────┐  ┌──────────┐
                          │  W-A     │  │  W-B     │  │  W-C     │
                          │ temp=0.3 │  │ temp=0.6 │  │ temp=0.8 │
                          │ Coverage │  │ Argument │  │ Readab.  │
                          └────┬─────┘  └────┬─────┘  └────┬─────┘
                               └─────────────┼─────────────┘
                                       asyncio.gather
                                             ▼
                    ┌──────────────────────────────────────────────┐
                    │  jury_multi_draft node (§7.5 / §4.5)         │
                    │  Phase 1: 9 judges × 3 drafts = 27 LLM calls │
                    │  Cascading tiers per draft independently      │
                    │  VETO on draft X ≠ affect drafts Y, Z        │
                    │  → css_individual per draft                   │
                    │  → best_elements from non-winners            │
                    │  → base_draft = argmax(css_individual)       │
                    │    tie-break: mini-jury F CSS                 │
                    │  Phase 1 CSS → run_metrics only (not history)│
                    └────────────────┬─────────────────────────────┘
                                     │
                    all fabricated?  │  base selected
                         ↓           ▼
                    [writer_single] [Fusor Agent]
                    (fallback)      (o3, single run, never repeated)
                                             ▼
                                     [Fused Draft]
                                             ▼
                          [Metrics Collector] → [Style Linter]
                                             ▼
                    ┌──────────────────────────────────────────────┐
                    │  jury node — Phase 2 (standard approval)     │
                    │  CSS enters css_history (Phase 2 CSS only)   │
                    └────────────────┬─────────────────────────────┘
                                     ▼
                  ┌──── CSS ≥ threshold? ────┤
                  │ YES                       │ NO
                  ▼                           ▼
        [Context Compressor]         [Reflector] → scope?
        [Coherence Guard]            SURGICAL → [Span Editor]
        [Section approved]           PARTIAL  → [Single Writer] ◄──┐
                                     FULL     → [Human escalation]  │
                                                                     │
                                     iteration++ ─────────────────►─┘
                                     (MoW NOT re-activated;
                                      mow_active gated on
                                      current_iteration == 1)

┌─────────────────────────────────────────────────────────────────┐
│ SINGLE-WRITER PATH (economy / words<400 / iteration>1 / post-   │
│                     escalation)                                  │
└─────────────────────────────────────────────────────────────────┘

[Source Synthesizer]
        ▼
[Writer — single call]
        ▼
[Metrics Collector] → [Style Linter]
        ▼
[Jury — standard approval]
        ▼
  CSS ≥ threshold? → YES → [Section approved]
                  → NO  → [Reflector] → [Writer] (loop)
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
class MoWState(TypedDict):
    mow_active: bool
    draft_proposals: list[tuple[Literal["W-A","W-B","W-C"], str, float]]
    per_draft_verdicts: list[PerDraftVerdict]
    best_elements_collected: list[BestElement]
    fused_draft: Optional[FusedDraft]
    mow_iterations_saved: float     # updated post-section: avg_iter_single - actual_iter
```

Cross-refs: §5.7 (Writer), §5.13 (Fusor), §7.5 uses §8 jury machinery, §9.3 (CSS formula), §19.1 (Budget Estimator), §14 (Context Compressor feeds `compressed_context`), §3B.2 (Style Exemplar injection).

<!-- SPEC_COMPLETE -->