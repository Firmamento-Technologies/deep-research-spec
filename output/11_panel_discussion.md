Looking at the two issues to fix:

1. **LOGIC_ERROR**: §11.3 has a conflicting `route_after_panel_internal()` that returns `'context_compressor'` when CSS >= css_panel_threshold, but §9.5's canonical definition should return `'aggregator'` for exhausted rounds and `'panel_discussion'` for self-loop. Need to remove the duplicate and align with §9.5.

2. **AMBIGUITY**: §2.7 says "EXACTLY these 2 checkpoints" but there are 4-5 await_human trigger paths. Need to clarify the distinction between planned and emergency checkpoints.

For issue 1: The file doesn't contain a §2.7 or §9.5 directly, but §11.3 has two routing functions. Per the fix instruction: keep only the version consistent with §9.5 (returns `'panel_discussion'` for self-loop, `'aggregator'` for exhausted rounds), remove `route_after_panel_internal()` and its conflicting edge mapping, update `route_after_panel()` to match, and update the graph edge registration.

For issue 2: The file doesn't have a §2.7 section directly, but the Panel Discussion Agent block references the routing. I need to add the clarifying note where human-in-the-loop is referenced.

```markdown
# 11. Panel Discussion

## 11.1 Activation Condition

```python
from typing import Literal, TypedDict, Optional

PANEL_APPROVED_STRONG_THRESHOLD: float = 0.85   # approved (strong consensus)
PANEL_APPROVED_NOTES_THRESHOLD: float = 0.70    # approved_with_notes (moderate consensus)

PanelExitRoute = Literal[
    "approved",           # CSS_content >= PANEL_APPROVED_STRONG_THRESHOLD after panel
    "approved_with_notes",# CSS_content >= PANEL_APPROVED_NOTES_THRESHOLD but < PANEL_APPROVED_STRONG_THRESHOLD after panel
    "escalate_human",     # CSS_content < css_panel_threshold after max rounds
    "budget_hard_stop"    # budget.spent_dollars >= budget.max_dollars
]

PanelTriggerCondition = Literal["css_below_threshold", "jury_0_of_3"]
```

**Trigger**: `CSS_content < css_panel_threshold` (default `0.50`) after a standard jury round.
`css_panel_threshold` is read from `state["budget"]["css_panel_threshold"]` (see §19.2 for regime overrides).

Panel is NOT triggered if:
- `state["current_iteration"] >= state["budget"]["max_iterations"]` → route directly to `escalate_human`
- `state["budget"]["spent_dollars"] >= state["budget"]["max_dollars"] * 1.0` → route to `budget_hard_stop`
- `quality_preset == "Economy"` → skip panel, route directly to `escalate_human`

**Human-in-the-Loop note**: The `escalate_human` exit from panel routes to `await_human`. This is an unplanned emergency interruption, distinct from the 2 scheduled human checkpoints (outline approval and user-initiated escalation intervention). See §2.7: emergency `await_human` calls (coherence hard conflict, budget anomaly, oscillation, panel exhaustion) are unplanned interruptions and do not count against the 2 planned checkpoints.

---

## 11.2 Mechanism

### Step 1 — Anonymization

```python
class AnonymizedJudgeComment(TypedDict):
    comment_id: str            # "C001", "C002", ... positional, not model-linked
    mini_jury: Literal["R", "F", "S"]
    verdict: Literal["PASS", "FAIL", "VETO"]
    veto_category: Optional[str]  # see §10.1 for valid categories
    motivation: str
    dimension_scores: dict[str, float]
    confidence: Literal["low", "medium", "high"]

class PanelRoundInput(TypedDict):
    round_number: int          # 1 or 2
    draft: str
    anonymized_comments: list[AnonymizedJudgeComment]
    css_before_panel: float
    section_title: str
    style_profile: str
    forbidden_patterns: list[str]
```

Each judge receives `anonymized_comments` from all 9 judges. Judge identity (`model`, `slot`) is stripped; only `comment_id` and `mini_jury` category remain. Anonymization is deterministic: comments sorted by `mini_jury` (R→F→S) then by verdict severity (VETO→FAIL→PASS), assigned sequential IDs.

### Step 2 — Comment Exchange Format

```python
class PanelRevote(TypedDict):
    judge_slot: str            # e.g. "R1", "F2", "S3"
    model: str
    comment_id_agreed_with: list[str]   # IDs from anonymized_comments
    comment_id_disagreed_with: list[str]
    revised_verdict: Literal["PASS", "FAIL", "VETO"]
    revised_veto_category: Optional[str]
    revised_dimension_scores: dict[str, float]
    revised_confidence: Literal["low", "medium", "high"]
    reasoning: str             # why verdict changed or held

class PanelRoundOutput(TypedDict):
    round_number: int
    revotes: list[PanelRevote]
    css_after_round: float
    panel_exit_triggered: bool
```

Each judge call receives the full `PanelRoundInput` via the standard LLM client (see §20.2). All 9 judges revote in `asyncio.gather` (parallel). CSS is recalculated by the Aggregator using the revised verdicts with formula from §9.1.

### Step 3 — Revote and Round Limit

```python
PANEL_MAX_ROUNDS: int = 2  # immutable, not overridable by budget regime
```

- Round 1: all 9 judges receive anonymized comments → revote → Aggregator recalculates CSS.
- If `CSS_content >= css_panel_threshold` after round 1 → exit `approved` or `approved_with_notes`.
- If `CSS_content < css_panel_threshold` after round 1 AND `panel_round < 2` → execute round 2.
- After round 2 regardless of CSS → exit `escalate_human` if still below threshold.

VETO from §10.1 cast during panel revote has identical blocking power as in standard jury. A revoked VETO (judge changes from VETO to FAIL/PASS) is accepted without special handling.

---

## 11.3 Exits and Routing

The canonical conditional edge for `panel_discussion` is defined in §9.5. The single authoritative routing function is reproduced here for reference and must remain identical to §9.5. There is no separate `route_after_panel_internal`; the function below is the only registered edge handler for this node.

```python
def route_after_panel(state: "DocumentState") -> Literal[
    "panel_discussion", "aggregator", "await_human", "publisher"
]:
    """
    Canonical conditional edge handler for 'panel_discussion' node (defined in §9.5).
    Returns 'panel_discussion' for self-loop when additional rounds remain.
    Returns 'aggregator' when CSS threshold is met (rounds resolved).
    Returns 'await_human' when rounds are exhausted without reaching threshold.
    Returns 'publisher' on budget hard stop.

    This is the single authoritative implementation. Do not duplicate or override.
    """
    budget = state["budget"]
    if budget["spent_dollars"] >= budget["max_dollars"]:
        return "publisher"

    css = state["panel_anonymized_log"][-1]["css_after_round"]
    panel_round = state["panel_round"]

    if css >= budget["css_panel_threshold"]:
        # CSS threshold met — return to aggregator for final approved/approved_with_notes routing
        return "aggregator"
    elif panel_round >= PANEL_MAX_ROUNDS:
        # Rounds exhausted without consensus — emergency human escalation
        return "await_human"
    else:
        # More rounds remain — self-loop back to panel_discussion node
        return "panel_discussion"
```

**Graph edge registration in §4.5**:
```python
g.add_conditional_edges(
    "panel_discussion",
    route_after_panel,
    {
        "panel_discussion": "panel_discussion",   # self-loop for next round
        "aggregator":       "aggregator",         # CSS threshold met, re-enter aggregator
        "await_human":      "await_human",        # rounds exhausted, emergency escalation
        "publisher":        "publisher",          # budget hard stop
    }
)
```

| Exit Route | CSS Condition | Action |
|---|---|---|
| `aggregator` (→ `approved`) | `>= css_panel_threshold` AND `>= PANEL_APPROVED_STRONG_THRESHOLD (0.85)` | Section marked approved, → §14 Context Compressor |
| `aggregator` (→ `approved_with_notes`) | `>= css_panel_threshold` AND `>= PANEL_APPROVED_NOTES_THRESHOLD (0.70)` AND `< PANEL_APPROVED_STRONG_THRESHOLD (0.85)` | Approved; dissent log attached to section record |
| `await_human` | `< css_panel_threshold` after round 2 | → §13.4 Human Escalation Interface (unplanned emergency interrupt; see §2.7) |
| `publisher` | budget exhausted | → Publisher with partial document |

`approved_with_notes` appends `panel_dissent_summary` to the `Section` store record (see §21.1). The dissent summary is included in the Run Report (see §30.4) but does not block publication.

---

## 11.2.4 PostgreSQL Log Schema

```sql
CREATE TABLE panel_discussion_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id      UUID NOT NULL REFERENCES sections(id),
    run_id          UUID NOT NULL REFERENCES runs(id),
    section_index   INTEGER NOT NULL,
    iteration       INTEGER NOT NULL,
    round_number    INTEGER NOT NULL CHECK (round_number IN (1, 2)),
    css_before      DECIMAL(4, 3) NOT NULL,
    css_after       DECIMAL(4, 3) NOT NULL,
    anonymized_input  JSONB NOT NULL,  -- PanelRoundInput (no model identity)
    revotes           JSONB NOT NULL,  -- list[PanelRevote]
    exit_route      TEXT NOT NULL,     -- PanelExitRoute value
    panel_duration_ms INTEGER,
    cost_usd        DECIMAL(8, 4),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_panel_log_section ON panel_discussion_log(section_id);
CREATE INDEX idx_panel_log_run ON panel_discussion_log(run_id);
```

`anonymized_input` stores comment IDs only — no `model` or `judge_slot` fields. Raw model identity is NOT persisted in this table; it is available in `jury_rounds` (see §21.1) correlated by `section_id + iteration`.

---

## Panel Discussion Agent

```
AGENT: PanelDiscussion [§11]
RESPONSIBILITY: coordinate anonymized multi-round judge revote on low-CSS sections
MODEL: anthropic/claude-opus-4-5 / TEMP: 0.2 / MAX_TOKENS: 2048
INPUT:
  draft: str
  anonymized_comments: list[AnonymizedJudgeComment]
  round_number: int
  css_before_panel: float
  section_title: str
  style_preset: dict
  budget: dict
OUTPUT: PanelRoundOutput
CONSTRAINTS:
  MUST strip model identity before distributing comments to judges
  MUST run all 9 judge revotes in asyncio.gather (parallel)
  MUST cap execution at PANEL_MAX_ROUNDS = 2
  MUST pass revised verdicts to Aggregator for CSS recalculation via §9.1 formula
  MUST log each round to panel_discussion_log before routing
  MUST use css_panel_threshold from state['budget']['css_panel_threshold'] for all threshold comparisons
  MUST use PANEL_APPROVED_STRONG_THRESHOLD (0.85) and PANEL_APPROVED_NOTES_THRESHOLD (0.70) as named constants for approved/approved_with_notes routing
  NEVER allow panel in quality_preset == "Economy"
  NEVER allow PANEL_MAX_ROUNDS override via config
  ALWAYS persist anonymized_input without model identity
ERROR_HANDLING:
  judge_call_failure (>=1 of 9) -> use available revotes -> recalculate CSS on n_available judges with JURY_DEGRADED flag (see §20.5)
  all_judges_fail -> abort panel -> route "await_human" -> log PANEL_ABORTED
  parse_error on revote JSON -> default revised_verdict = original verdict unchanged -> continue
  budget_exhausted mid-panel -> stop immediately -> route "publisher"
CONSUMES: [current_draft, jury_verdicts, css_history, panel_round, budget] from DocumentState
PRODUCES: [panel_anonymized_log, panel_round, panel_active] -> DocumentState
LOOPING: managed by self-loop graph edge via route_after_panel (see §4.5 and §9.5); panel_discussion node does NOT implement internal loops
HUMAN_CHECKPOINTS: escalate_human exit is an unplanned emergency await_human call, not one of the 2 scheduled human checkpoints (see §2.7)
```

<!-- SPEC_COMPLETE -->