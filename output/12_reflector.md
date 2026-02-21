# §12 Reflector

## §12.0 Overview

Reflector synthesizes jury verdict history into structured, prioritized feedback and assigns rewrite scope to route the next action (Span Editor, Writer, or human escalation).

---

## §12.1 FeedbackItem Schema

```python
from typing import Literal
from pydantic import BaseModel, Field

Severity   = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
Category   = Literal[
    "factual_error", "logical_contradiction", "missing_evidence",
    "fabricated_source", "style_violation", "structural_error",
    "citation_mismatch", "temporal_inconsistency"
]
ScopeType  = Literal["SURGICAL", "PARTIAL", "FULL"]

class FeedbackItem(BaseModel):
    id: str                          # f{n:03d} — sequential within ReflectorOutput
    severity: Severity
    category: Category
    affected_text: str               # verbatim quote from current draft, exact match required
    context_before: str              # ≤1 sentence preceding affected_text, immutable
    context_after: str               # ≤1 sentence following affected_text, immutable
    action: str                      # imperative verb phrase: what Span Editor / Writer must do
    scope: ScopeType                 # see §12.2
    priority: int                    # 1 = highest; unique within ReflectorOutput
    replacement_length_hint: Literal["SHORTER", "SAME", "LONGER"]
    source_ids: list[str]            # citation IDs from DocumentState.current_sources

class ReflectorOutput(BaseModel):
    section_idx: int
    iteration: int
    items: list[FeedbackItem]        # sorted by priority ascending
    dominant_scope: ScopeType        # see §12.2 — drives routing
    conflict_resolution_log: list[str]  # one entry per resolved conflict, see §12.3
```

---

## §12.2 Scope Determination Rules

`dominant_scope` is computed from `items` **after** conflict resolution (§12.3).

**Paragraph boundary definition**: A paragraph is a text block delimited by two or more consecutive newline characters (`\n\n`). If `current_draft` contains no such delimiters, treat the entire draft as one paragraph.

| `dominant_scope` | Condition | Routing |
|---|---|---|
| `SURGICAL` | ALL of: `len(items) ≤ 4`, all `affected_text` in distinct paragraphs, `iteration ≤ 2`, no `category == "structural_error"`, no scope-FULL item present | → oscillation_check → span_editor (§5.12) if no oscillation and iteration ≤ 2 |
| `PARTIAL` | ANY of: `len(items) > 4`, items share a paragraph, `iteration > 2`, ≥1 `structural_error` present, but no FULL condition | → oscillation_check → writer (§5.7) if no oscillation |
| `FULL` | ANY of: dominant `category == "logical_contradiction"` spanning ≥3 paragraphs, ≥1 `severity == "CRITICAL"` with `category == "structural_error"`, Coherence Guard flagged HARD conflict in current section (§15.1) | → await_human directly, bypassing oscillation_check |

Individual `FeedbackItem.scope` follows same rules applied to that item alone. `dominant_scope` = most restrictive scope across all items:
`FULL > PARTIAL > SURGICAL`.

### Two-Stage Routing for SURGICAL and PARTIAL

After `route_after_reflector()` returns `"oscillation_check"` (for both SURGICAL and PARTIAL),
the `oscillation_check` node runs and `route_after_oscillation()` dispatches based on scope:

```
SURGICAL, no oscillation, iteration ≤ 2  →  span_editor  (§5.12)
PARTIAL,  no oscillation                  →  writer        (§5.7)
SURGICAL, no oscillation, iteration > 2   →  writer        (§5.7)
any scope, oscillation_detected           →  await_human   (§13.4)
FULL                                      →  await_human   (direct, skips oscillation_check)
```

### Scope Examples

```json
// SURGICAL — 2 isolated span fixes, iteration 1
{
  "dominant_scope": "SURGICAL",
  "items": [
    {
      "id": "f001", "severity": "HIGH", "category": "factual_error",
      "affected_text": "increased by 34% in 2021",
      "context_before": "Revenue growth was stable.",
      "context_after": "Analysts attributed this to supply chain recovery.",
      "action": "Replace statistic with verified figure 28% (source_id: src_003)",
      "scope": "SURGICAL", "priority": 1, "replacement_length_hint": "SAME",
      "source_ids": ["src_003"]
    },
    {
      "id": "f002", "severity": "MEDIUM", "category": "citation_mismatch",
      "affected_text": "as confirmed by WHO (2019)",
      "context_before": "The mortality rate dropped significantly,",
      "context_after": "a pattern observed across developing nations.",
      "action": "Update citation year to 2020; DOI verified src_007",
      "scope": "SURGICAL", "priority": 2, "replacement_length_hint": "SAME",
      "source_ids": ["src_007"]
    }
  ]
}

// PARTIAL — 6 items, iteration 2
{
  "dominant_scope": "PARTIAL",
  "items": [
    {"id": "f001", "severity": "HIGH", "category": "missing_evidence",
     "affected_text": "broadly accepted by the scientific community",
     "action": "Replace vague claim with specific study citations from src_list",
     "scope": "PARTIAL", "priority": 1}
  ]
}

// FULL — structural contradiction, CRITICAL severity
{
  "dominant_scope": "FULL",
  "items": [
    {"id": "f001", "severity": "CRITICAL", "category": "logical_contradiction",
     "affected_text": "Therefore, decentralization reduces systemic risk ... however centralized control is essential for stability",
     "action": "Resolve contradiction: choose one position or explicitly frame as debate",
     "scope": "FULL", "priority": 1, "replacement_length_hint": "LONGER",
     "source_ids": []}
  ]
}
```

---

## §12.3 Conflict Resolution Rule

Applied by Reflector **before** emitting `ReflectorOutput`.

1. **Severity precedence**: if two `FeedbackItem` conflict on the same `affected_text`, the item with higher severity survives; the other is dropped and logged in `conflict_resolution_log`.
2. **Category tie-break**: at equal severity, `category == "factual_error"` or `"fabricated_source"` (originating from Judge F) prevails over all other categories.
3. **Priority reassignment**: after conflict resolution, reassign `priority` 1..N sequentially, `CRITICAL` items first, then `HIGH`, `MEDIUM`, `LOW`; within same severity, Judge F findings ranked before Judge R, before Judge S.
4. **Scope re-evaluation**: recompute `dominant_scope` on surviving items only.

```python
SEVERITY_RANK: dict[Severity, int] = {
    "CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1
}
CATEGORY_TIEBREAK_RANK: dict[Category, int] = {
    "fabricated_source": 10, "factual_error": 9,
    "logical_contradiction": 8, "missing_evidence": 7,
    "citation_mismatch": 6, "temporal_inconsistency": 5,
    "structural_error": 4, "style_violation": 3
}
```

---

## §12.4 Agent Specification

```
AGENT: Reflector [§12]
RESPONSIBILITY: synthesize verdict history into prioritized FeedbackItem list with scope
MODEL: openai/o3 / TEMP: 0.2 / MAX_TOKENS: 2048
FALLBACK: openai/o3-mini

INPUT:
  current_draft: str
  all_verdicts_history: list[dict]   # all JuryRound records for current section
  current_iteration: int
  section_idx: int
  coherence_guard_flags: list[dict]  # from §15.1, may be empty

OUTPUT: ReflectorOutput

CONSTRAINTS:
  MUST quote affected_text verbatim from current_draft (exact substring match enforced by Diff Merger)
  MUST assign unique priority integers 1..N
  MUST apply conflict resolution (§12.3) before emitting output
  MUST set dominant_scope = FULL if coherence_guard_flags contains any HARD entry
  NEVER emit FeedbackItem.scope = SURGICAL on iteration >= 3
  NEVER include affected_text longer than 80 words
  ALWAYS populate context_before and context_after even if empty string

ERROR_HANDLING:
  parse_error (output not valid ReflectorOutput JSON) ->
    retry once with simplified prompt (max 4 items) ->
    fallback to o3-mini; if still fails -> dominant_scope = PARTIAL, items = []
  affected_text not found in draft (substring mismatch) ->
    drop that FeedbackItem, log to conflict_resolution_log ->
    recompute dominant_scope on remaining items
  all_verdicts_history empty ->
    raise ValueError, abort node, escalate to human (§13.4)

CONSUMES:
  [current_draft, all_verdicts_history, current_iteration,
   section_idx, coherence_guard_flags, current_sources]
  from DocumentState

PRODUCES:
  [reflector_output, scope_reflector]
  -> DocumentState
```

---

## §12.5 Routing Post-Reflector

After the Reflector node runs and writes fresh `reflector_output` to `DocumentState`, the
`route_after_reflector()` function reads the new output and dispatches to the correct next
node. The aggregator node emits only `"fail_reflector"` on non-approval (or `"veto"`); it
does **not** perform surgical/partial/full routing — that distinction belongs exclusively
here, where `reflector_output` is guaranteed to be current.

**Two-stage routing architecture:**

1. `route_after_reflector()` — first stage, runs immediately after Reflector node:
   - `FULL` → `await_human` directly (argument structurally broken; oscillation detection irrelevant)
   - `SURGICAL` or `PARTIAL` → `oscillation_check`

2. `route_after_oscillation()` — second stage, runs after oscillation_check node:
   - oscillation detected (any scope) → `await_human`
   - `SURGICAL` + iteration ≤ 2, no oscillation → `span_editor`
   - `PARTIAL` or (`SURGICAL` + iteration > 2), no oscillation → `writer`

This two-stage design ensures:
- FULL scope bypasses oscillation detection entirely (irrelevant for structural rewrites)
- SURGICAL scope reaches span_editor only when oscillation has been confirmed absent AND iteration allows it
- The graph edges in §4.5 wire `oscillation_check` with three outbound routes: `span_editor`, `writer`, `escalate_human`

```python
def route_after_reflector(state: DocumentState) -> str:
    scope = state["reflector_output"]["dominant_scope"]

    if scope == "FULL":
        return "await_human"          # bypass oscillation_check entirely;
                                      # argument is structurally broken
    return "oscillation_check"        # covers both SURGICAL and PARTIAL;
                                      # oscillation_check dispatches to span_editor,
                                      # writer, or await_human via route_after_oscillation


def route_after_oscillation(state: DocumentState) -> str:
    """
    Scope-aware routing from oscillation_check node (§4.5, §5.15).
    Called after OscillationDetector has run and set oscillation_detected.

    Priority:
      oscillation detected (any scope) → escalate_human
      SURGICAL + iteration <= 2       → span_editor
      all other cases                 → writer
    """
    if state.get("oscillation_detected"):
        return "escalate_human"       # §13.4 — human intervention required

    scope = state["reflector_output"]["dominant_scope"]
    iteration = state.get("current_iteration", 1)

    if scope == "SURGICAL" and iteration <= 2:
        return "span_editor"          # §5.12 surgical path

    return "writer"                   # §5.7 — PARTIAL, or SURGICAL on iter > 2
```

**Graph edges implementing this routing (from §4.5 build_graph):**

```python
# Stage 1: reflector → route_after_reflector → oscillation_check | await_human
g.add_conditional_edges("reflector", route_after_reflector, {
    "oscillation_check": "oscillation_check",
    "await_human":       "await_human",
})

# Stage 2: oscillation_check → route_after_oscillation → span_editor | writer | await_human
g.add_conditional_edges("oscillation_check", route_after_oscillation, {
    "span_editor":    "span_editor",
    "writer":         "writer",
    "escalate_human": "await_human",
})
```

<!-- SPEC_COMPLETE -->