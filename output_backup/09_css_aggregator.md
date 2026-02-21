# 09_css_aggregator.md

## §9 — Aggregator and CSS Formula

---

### §9.1 Consensus Strength Score (CSS)

Two separate scores computed independently; never merged before routing.

```python
# CSS_content: weighted combination of Reasoning + Factual mini-juries
# CSS_style:   Style mini-jury only
# All inputs are BINARY per judge: 1 = PASS, 0 = FAIL

# NOTE: The 0.44/0.56 split for CSS_content is derived from the composite jury weights
# defined in §9.2 by normalizing only the reasoning and factual components:
#   normalized_reasoning = 0.35 / (0.35 + 0.45) = 0.35 / 0.80 = 0.4375 ≈ 0.44
#   normalized_factual   = 0.45 / (0.35 + 0.45) = 0.45 / 0.80 = 0.5625 ≈ 0.56
# This makes the content-only weights fully derivable from JURY_WEIGHTS and verifiable.

CSS_content: float = 0.44 * (pass_R / n_R) + 0.56 * (pass_F / n_F)
CSS_style:   float = pass_S / n_S

# Range: [0.0, 1.0] for both scores
# CSS_content = 1.0 → all R and F judges PASS
# CSS_style   = 0.0 → all S judges FAIL

# Composite for Run Report only (NOT used for routing):
CSS_composite: float = 0.35 * (pass_R / n_R) + 0.45 * (pass_F / n_F) + 0.20 * (pass_S / n_S)
```

**Variable definitions:**

| Symbol | Type | Source |
|--------|------|--------|
| `pass_R` | `int` | Count of PASS verdicts from mini-jury R (Reasoning) |
| `n_R` | `int` | Active judges in R after circuit-breaker exclusions; min=1 |
| `pass_F` | `int` | Count of PASS verdicts from mini-jury F (Factual) |
| `n_F` | `int` | Active judges in F; min=1 |
| `pass_S` | `int` | Count of PASS verdicts from mini-jury S (Style) |
| `n_S` | `int` | Active judges in S; min=1 |

If a judge is excluded by circuit-breaker, `n_x` decrements; denominator never 0 (see §20.5).

---

### §9.2 Jury Weights

```python
JURY_WEIGHTS: dict[str, float] = {
    "reasoning": 0.35,
    "factual":   0.45,
    "style":     0.20,
}
# Invariant: sum(JURY_WEIGHTS.values()) == 1.0
# Used only in CSS_composite (Run Report). Routing uses CSS_content and CSS_style directly.
# The 0.44/0.56 split in CSS_content is derived from these weights; see §9.1 derivation note.
# Override via convergence.jury_weights in YAML (see §29.3). Pydantic enforces sum=1.0.
```

---

### §9.3 Sequential Approval Phases

Two phases execute in strict order. Phase 2 only runs if Phase 1 passes.

```
Phase 1 — CONTENT GATE
  Inputs:  CSS_content (from R + F juries)
  Passes:  CSS_content >= css_content_threshold
  Failure: route to Reflector / Panel / Veto (see §9.4)

Phase 2 — STYLE PASS
  Inputs:  CSS_style (from S jury only)
  Passes:  CSS_style >= css_style_threshold
  Failure: route to Style Fixer ONLY — Writer is NOT invoked
```

**Threshold table by `quality_preset` (SINGLE SOURCE OF TRUTH for all threshold values):**

```python
THRESHOLD_TABLE: dict[str, dict[str, float]] = {
    "economy": {
        "css_content_threshold": 0.65,
        "css_style_threshold":   0.75,
        "css_panel_trigger":     0.40,
    },
    "balanced": {
        "css_content_threshold": 0.70,
        "css_style_threshold":   0.80,
        "css_panel_trigger":     0.50,
    },
    "premium": {
        "css_content_threshold": 0.78,
        "css_style_threshold":   0.85,
        "css_panel_trigger":     0.55,
    },
}
# Budget regime overrides quality_preset at runtime (see §19.2).
# Style threshold always >= content threshold; enforced by Pydantic validator.
# §1.4.1 DerivedParams and §19.2 REGIME_PARAMS must match these values exactly.
```

Both thresholds are reported separately in the Run Report (`css_content_final`, `css_style_final`).

---

### §9.4 Routing After Aggregator

**CANONICAL IMPLEMENTATION** — this is the single authoritative definition of
`route_after_aggregator()`. The §4.5 LangGraph edge definitions reference the
return literals defined here. Do not define this function elsewhere.

```python
from typing import Literal

AggregatorRoute = Literal[
    "approved",
    "fail_style",
    "fail_missing_ev",
    "fail_reflector",
    "panel",
    "veto",
    "budget_hard_stop",
]

def route_after_aggregator(state: "DocumentState") -> AggregatorRoute:
    """
    Executed by Aggregator node after collecting all jury verdicts.
    Priority order: budget_hard_stop > veto > panel > missing_ev > approved > fail_style > fail_reflector

    CANONICAL: §4.5 LangGraph conditional edges use this function and its return literals.
    """
    budget = state["budget"]
    verdicts = state["jury_verdicts"]  # list[JuryVerdict] for current iteration
    css_content = state["css_content_current"]
    css_style   = state["css_style_current"]
    thresholds  = _get_thresholds(state["config"])

    # ── Priority 1: Budget Hard Stop ─────────────────────────────────────
    if budget["spent_dollars"] >= budget["max_dollars"]:
        return "budget_hard_stop"  # → publisher with partial output

    # ── Priority 2: Minority Veto L1 (individual judge) ──────────────────
    # Any single judge with a valid veto_category blocks unconditionally.
    veto_categories_l1: set[str] = {
        "fabricated_source",
        "factual_error",
        "logical_contradiction",
        "plagiarism",
    }
    for v in verdicts:
        if v["veto_category"] in veto_categories_l1:
            return "veto"  # → Reflector with dissenting_reasons (see §10.1)

    # ── Priority 3: Minority Veto L2 (full mini-jury unanimous FAIL) ──────
    # 0/n_x PASS in any single mini-jury → block regardless of CSS_content.
    # Uses judge_slot prefixes R/F/S as defined in §4.6 JudgeVerdict
    # (Literal['R1','R2','R3','F1','F2','F3','S1','S2','S3']).
    r_verdicts = [v for v in verdicts if v["judge_slot"].startswith("R")]
    f_verdicts = [v for v in verdicts if v["judge_slot"].startswith("F")]
    if all(v["pass_fail"] is False for v in r_verdicts) \
    or all(v["pass_fail"] is False for v in f_verdicts):
        return "veto"  # → Reflector (see §10.2)

    # ── Priority 4: Panel Discussion Trigger ─────────────────────────────
    # Weak consensus on content: neither veto nor clear majority.
    panel_max_rounds: int = state["config"]["convergence"].get("panel_max_rounds", 2)
    if css_content < thresholds["css_panel_trigger"] \
    and state["panel_round"] < panel_max_rounds:
        return "panel"  # → panel_discussion node (see §11)

    # ── Priority 5: Content Gate PASS check ──────────────────────────────
    content_passes = css_content >= thresholds["css_content_threshold"]

    if not content_passes:
        # Check if Judge F flagged missing_evidence specifically
        missing_ev_flags = [
            v for v in f_verdicts
            if v.get("missing_evidence") and not v["pass_fail"]
        ]
        if missing_ev_flags:
            return "fail_missing_ev"  # → researcher_rerun node (see §5.2)
        return "fail_reflector"  # → reflector node (see §12)

    # ── Priority 6: Style Pass check ─────────────────────────────────────
    # Content Gate passed. Now evaluate Style independently.
    style_passes = css_style >= thresholds["css_style_threshold"]

    if not style_passes:
        return "fail_style"  # → style_fixer node (see §5.10); Writer NOT invoked

    # ── All gates cleared ─────────────────────────────────────────────────
    return "approved"  # → context_compressor → coherence_guard → section_checkpoint


def _get_thresholds(config: dict) -> dict[str, float]:
    """Reads from budget-adjusted state; falls back to quality_preset table."""
    budget_override = config.get("_budget_thresholds")
    if budget_override:
        return budget_override
    preset: str = config["user"]["quality_preset"]
    return THRESHOLD_TABLE[preset]
```

---

### §9.5 Panel Discussion Self-Loop Edge

The `panel_discussion` node executes a deliberation round and updates
`DocumentState` (incrementing `panel_round`). Because LangGraph does not
support internal loops within a single node, continued deliberation is
implemented as a self-loop graph edge defined in §4.5:

```python
# Defined in §4.5 alongside all other conditional edges:
g.add_conditional_edges(
    "panel_discussion",
    route_after_panel_internal,
    {
        "panel_discussion": "panel_discussion",  # self-loop: rounds remain
        "aggregator":       "aggregator",        # rounds exhausted → re-evaluate
    }
)

def route_after_panel_internal(state: "DocumentState") -> Literal["panel_discussion", "aggregator"]:
    """
    Called after each panel_discussion execution.
    Returns 'panel_discussion' if additional rounds remain, otherwise 'aggregator'
    to re-evaluate CSS with updated verdicts.
    """
    panel_max_rounds: int = state["config"]["convergence"].get("panel_max_rounds", 2)
    if state["panel_round"] < panel_max_rounds:
        return "panel_discussion"
    return "aggregator"
```

The value `'continue_panel'` is NOT a valid LangGraph edge or AggregatorRoute
literal. All panel looping is handled exclusively by the self-loop edge above.

---

### §9.6 Aggregator Agent

```
AGENT: Aggregator [§9]
RESPONSIBILITY: Compute CSS_content and CSS_style from jury verdicts and emit routing decision

MODEL: deterministic (no LLM call) / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  jury_verdicts:   list[JuryVerdict]   # from §8.6; all three mini-juries
  css_history:     list[float]         # css_content values; used by OscillationDetector
  budget:          BudgetState         # see §19.3
  panel_round:     int
  config:          dict

OUTPUT: AggregatorDecision
  css_content:     float               # [0.0, 1.0]
  css_style:       float               # [0.0, 1.0]
  css_composite:   float               # Run Report only
  route:           AggregatorRoute     # see §9.4
  dissenting_reasons: list[str]        # populated when route in {"veto","fail_reflector","panel"}
  missing_evidence_claims: list[str]   # populated when route == "fail_missing_ev"

CONSTRAINTS:
  MUST compute CSS before any routing check
  MUST apply priority order exactly as defined in §9.4
  MUST NOT invoke any LLM
  MUST emit css_content and css_style as separate fields; NEVER merge before routing
  MUST decrement n_x for circuit-broken judges before computing ratios
  NEVER set n_x < 1 (see §20.5 graceful degradation)
  ALWAYS append css_content to css_history before returning
  MUST filter verdicts by judge_slot prefix ('R', 'F', 'S') not by string label

ERROR_HANDLING:
  malformed JuryVerdict (missing required field) -> default pass_fail=False -> log WARNING with verdict id
  all judges in a slot circuit-broken -> n_x=1, pass_x=0 -> css_content degrades naturally -> route proceeds
  division by zero on n_x -> impossible if MUST above enforced; raise AggregatorError if violated

CONSUMES: [jury_verdicts, css_history, budget, panel_round, config] from DocumentState
PRODUCES: [css_content_current, css_style_current, css_composite_current, css_history, active_route] -> DocumentState
```

---

### §9.7 State Fields Produced

```python
# Fields written to DocumentState by Aggregator (see §4.6 for full schema)
css_content_current: float          # current section, current iteration
css_style_current:   float
css_composite_current: float        # Run Report only
css_history:         list[float]    # appended; consumed by OscillationDetector (§13)
active_route:        AggregatorRoute
dissenting_reasons:  list[str]      # forwarded to Reflector prompt
missing_evidence_claims: list[str]  # forwarded to researcher_rerun
```

---

### §9.8 Run Report Output

```python
class SectionCSSReport(TypedDict):
    section_idx:      int
    iteration:        int
    css_content:      float    # Phase 1 score
    css_style:        float    # Phase 2 score
    css_composite:    float
    n_r:              int      # active judges used
    n_f:              int
    n_s:              int
    pass_r:           int
    pass_f:           int
    pass_s:           int
    route_taken:      AggregatorRoute
    panel_triggered:  bool
    veto_triggered:   bool
    threshold_content: float   # threshold at time of evaluation
    threshold_style:   float
```

<!-- SPEC_COMPLETE -->