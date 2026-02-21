# 19 — Budget Controller

## 19.0 Pre-Run Formula

```python
from typing import Literal
from dataclasses import dataclass

Regime = Literal["Economy", "Balanced", "Premium"]

@dataclass
class BudgetEstimate:
    estimated_total_usd: float
    cost_per_section: float
    regime: Regime
    budget_per_word: float
    blocked: bool          # True if estimated_total > max_budget * 0.80
    block_reason: str | None

def estimate_run_cost(
    n_sections: int,
    target_words: int,
    max_budget_usd: float,
    avg_iter: float = 2.5,
    # $/M tokens (input, output)
    price_writer_out:   float = 75.0,   # claude-opus-4-5
    price_jury_t1_out:  float = 1.10,   # tier1 avg (qwq-32b/sonar/llama)
    price_jury_t2_out:  float = 12.0,   # tier2 avg (o3-mini/gemini-flash/mistral-l)
    price_reflector_out:float = 40.0,   # o3
    price_researcher_out:float = 1.0,   # sonar
    mow_enabled: bool = True,
) -> BudgetEstimate:
    words_per_sec   = target_words / n_sections
    tok_writer_out  = words_per_sec * 1.5
    tok_researcher  = 800.0
    tok_reflector   = 800.0

    # Jury cascading: tier1 always (9 calls); tier2 only on ~40% disagreement
    jury_t1_cost = tok_writer_out * 0.4 * price_jury_t1_out / 1_000_000 * 9
    jury_t2_cost = tok_writer_out * 0.4 * price_jury_t2_out / 1_000_000 * 3 * 0.40

    writer_cost     = tok_writer_out * price_writer_out / 1_000_000
    reflector_cost  = tok_reflector  * price_reflector_out / 1_000_000
    researcher_cost = tok_researcher * price_researcher_out / 1_000_000

    iter_cost = writer_cost + jury_t1_cost + jury_t2_cost + reflector_cost + researcher_cost
    if mow_enabled:
        iter_cost *= 1.4   # MoW adds ~3 Writer calls in iter 1; amortised over avg_iter

    cost_per_section = iter_cost * avg_iter
    estimated_total  = cost_per_section * n_sections
    budget_per_word  = max_budget_usd / target_words
    regime           = _derive_regime(budget_per_word)
    blocked = estimated_total > max_budget_usd * 0.80

    return BudgetEstimate(
        estimated_total_usd=round(estimated_total, 4),
        cost_per_section=round(cost_per_section, 4),
        regime=regime,
        budget_per_word=round(budget_per_word, 6),
        blocked=blocked,
        block_reason=f"Estimated ${estimated_total:.2f} > 80% cap ${max_budget_usd*0.80:.2f}" if blocked else None,
    )

def _derive_regime(budget_per_word: float) -> Regime:
    if budget_per_word < 0.002:  return "Economy"
    if budget_per_word <= 0.005: return "Balanced"
    return "Premium"
```

## 19.1 Pre-Run Budget Estimator

```
AGENT: BudgetEstimator [§19.1]
RESPONSIBILITY: block run before first LLM call if projected cost exceeds 80% of cap
MODEL: deterministic (no LLM) / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  outline:         list[dict]      # from §4.1 Planner output
  target_words:    int             # ≥ 1000
  max_budget_usd:  float           # > 0.0
  quality_preset:  Regime
  mow_enabled:     bool
OUTPUT: BudgetEstimate             # see §19.0 dataclass
CONSTRAINTS:
  MUST call estimate_run_cost() from §19.0 with actual n_sections
  MUST set state["budget"]["blocked"] = True and halt graph if BudgetEstimate.blocked
  MUST emit structured log: {agent:"budget_estimator", estimated_usd, regime, blocked}
  MUST call populate_budget_thresholds() (§9.3) to write css_content_threshold,
    css_style_threshold, and css_panel_threshold into BudgetState from THRESHOLD_TABLE
  NEVER start researcher/writer if blocked
ERROR_HANDLING:
  missing price data -> use conservative defaults from §19.0 -> log WARNING
  n_sections == 0 -> raise ValueError("outline empty") -> halt
CONSUMES: [outline, target_words, max_budget_usd, quality_preset] from DocumentState
PRODUCES: [budget.estimated_total_usd, budget.regime, budget.blocked,
           budget.css_content_threshold, budget.css_style_threshold,
           budget.css_panel_threshold, budget.max_iterations, budget.jury_size] -> DocumentState
```

## 19.2 Regime Table

The css_threshold values below match §9.3 THRESHOLD_TABLE exactly. §9.3 is the single
source of truth; this table summarises the css_content_threshold column for quick reference.

| Regime | budget_per_word ($/word) | css_content_threshold | max_iter | jury_size | MoW | models per slot |
|---|---|---|---|---|---|---|
| `Economy` | < $0.002 | 0.65 | 2 | 1 of 3 | disabled | tier1 only |
| `Balanced` | $0.002–$0.005 | 0.70 | 4 | 2 of 3 | enabled | tier1 + tier2 on disagree |
| `Premium` | > $0.005 | 0.78 | 8 | 3 of 3 | enabled | all tiers always |

```python
# css_threshold here refers to css_content_threshold (Phase 1 Content Gate).
# css_style_threshold is also regime-dependent and set from §9.3 THRESHOLD_TABLE:
#   Economy → 0.75 | Balanced → 0.80 | Premium → 0.85
# BudgetController calls populate_budget_thresholds() (§9.3) to resolve both
# thresholds from THRESHOLD_TABLE and write them into BudgetState at runtime.
REGIME_PARAMS: dict[Regime, dict] = {
    "Economy":  {"css_threshold": 0.65, "max_iterations": 2,
                 "jury_size": 1, "mow_enabled": False,
                 "tier1_only": True},
    "Balanced": {"css_threshold": 0.70, "max_iterations": 4,
                 "jury_size": 2, "mow_enabled": True,
                 "tier1_only": False},
    "Premium":  {"css_threshold": 0.78, "max_iterations": 8,
                 "jury_size": 3, "mow_enabled": True,
                 "tier1_only": False},
}
```

## 19.3 Real-Time Cost Tracker

### Counter schema

```python
class CostEntry(TypedDict):
    doc_id:       str
    section_idx:  int
    iteration:    int
    agent:        Literal["planner","researcher","writer","fusor",
                          "jury_r","jury_f","jury_s","reflector",
                          "span_editor","compressor","post_draft"]
    model:        str
    tokens_in:    int
    tokens_out:   int
    cost_usd:     float
    latency_ms:   int
    timestamp:    str   # ISO-8601

class BudgetState(TypedDict):
    max_dollars:            float
    spent_dollars:          float
    projected_final:        float
    regime:                 Regime
    # Threshold fields — populated by BudgetController via populate_budget_thresholds() (§9.3).
    # Values are read from §9.3 THRESHOLD_TABLE based on the active regime.
    # MUST NOT be hardcoded; always reflect the runtime-resolved regime.
    css_content_threshold:  float   # 0.65 (Economy) | 0.70 (Balanced) | 0.78 (Premium)
    css_style_threshold:    float   # 0.75 (Economy) | 0.80 (Balanced) | 0.85 (Premium)
    css_panel_threshold:    float   # 0.40 (Economy) | 0.50 (Balanced) | 0.55 (Premium)
    max_iterations:         int
    jury_size:              int
    mow_enabled:            bool
    alarm_70_fired:         bool
    alarm_90_fired:         bool
    hard_stop_fired:        bool
```

### Alarm texts (exact strings emitted to log + SSE)

| Threshold | Alarm text |
|---|---|
| spent ≥ 70% | `"BUDGET_WARN_70: ${spent:.4f} of ${max:.2f} used ({pct:.1f}%). Downgrading models for remaining {remaining} sections."` |
| spent ≥ 90% | `"BUDGET_ALERT_90: ${spent:.4f} of ${max:.2f} used ({pct:.1f}%). Forcing jury_size=1, css_threshold=0.65, max_iterations=1."` |
| spent ≥ 100% | `"BUDGET_HARD_STOP: ${spent:.4f} exceeds cap ${max:.2f}. Saving checkpoint. Returning partial document ({n_approved} sections approved)."` |

### Tracker node

```
AGENT: RealTimeCostTracker [§19.3]
RESPONSIBILITY: update BudgetState after every LLM call and trigger alarms
MODEL: deterministic / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  entry: CostEntry
  current_budget: BudgetState
OUTPUT: BudgetState            # updated
CONSTRAINTS:
  MUST write CostEntry to PostgreSQL costs table (see §21.1) atomically
  MUST update Redis key run:{doc_id}:spent_usd atomically (INCRBYFLOAT)
  MUST check thresholds in order: 100% first, then 90%, then 70%
  MUST fire each alarm exactly once per run (alarm_*_fired flags)
  NEVER allow spent_dollars to exceed max_dollars without hard_stop
ERROR_HANDLING:
  Redis unavailable -> write to PostgreSQL only -> log WARNING "redis_fallback"
  cost_usd < 0 -> clamp to 0.0 -> log ERROR "negative_cost"
CONSUMES: [budget] from DocumentState
PRODUCES: [budget] -> DocumentState
```

## 19.4 Dynamic Savings Strategies

| Trigger | Action |
|---|---|
| `spent ≥ 0.70 × max` | Downgrade Writer: `claude-opus-4-5` → fallback[0] (see §28.1); jury_size -= 1 (min 1); emit BUDGET_WARN_70 |
| `spent ≥ 0.90 × max` | `css_content_threshold = 0.65`; `css_style_threshold = 0.75`; `max_iterations = 1`; `jury_size = 1`; disable MoW; emit BUDGET_ALERT_90 |
| `spent ≥ 1.00 × max` | Hard stop: save LangGraph checkpoint; return partial doc from Store (§21.1); emit BUDGET_HARD_STOP |
| Single section cost > $15.00 | Pause run; emit `BUDGET_SECTION_ANOMALY`; await human via §24.3 `/approve` — this is an unplanned emergency interruption distinct from the 2 scheduled checkpoints defined in §2.7 |
| Researcher cache hit (cosine ≥ 0.90) | Skip API call; log `cache_hit`; cost_usd = 0 for entry |
| All 3 tier-1 jurors agree unanimously | Skip tier-2/tier-3 calls; saves ~60-70% jury cost |

```python
def apply_dynamic_savings(budget: BudgetState) -> BudgetState:
    pct = budget["spent_dollars"] / budget["max_dollars"]
    b = dict(budget)

    if pct >= 1.00 and not b["hard_stop_fired"]:
        b["hard_stop_fired"] = True
        # graph router reads this flag -> routes to publisher immediately

    elif pct >= 0.90 and not b["alarm_90_fired"]:
        b["alarm_90_fired"] = True
        b["css_content_threshold"] = 0.65   # Economy floor from §9.3 THRESHOLD_TABLE
        b["css_style_threshold"]   = 0.75   # Economy floor from §9.3 THRESHOLD_TABLE
        b["max_iterations"] = 1
        b["jury_size"]      = 1
        b["mow_enabled"]    = False

    elif pct >= 0.70 and not b["alarm_70_fired"]:
        b["alarm_70_fired"] = True
        b["jury_size"]      = max(1, b["jury_size"] - 1)
        # model downgrade applied by llm/client.py fallback chain

    return BudgetState(**b)
```

## 19.5 Adaptive Parameters as Levers

These fields in `BudgetState` are the control surface; all agents read from `state["budget"]` at call time.
Threshold values match §9.3 THRESHOLD_TABLE exactly.

| Lever | Type | Economy | Balanced | Premium | Mutated at |
|---|---|---|---|---|---|
| `css_content_threshold` | float | 0.65 | 0.70 | 0.78 | init (from §9.3) + 90% alarm |
| `css_style_threshold` | float | 0.75 | 0.80 | 0.85 | init (from §9.3) + 90% alarm |
| `css_panel_threshold` | float | 0.40 | 0.50 | 0.55 | init (from §9.3) |
| `max_iterations` | int | 2 | 4 | 8 | init + 90% alarm |
| `jury_size` | int | 1 | 2 | 3 | init + 70% + 90% alarm |
| `mow_enabled` | bool | False | True | True | init + 90% alarm |
| `tier1_only` | bool | True | False | False | 70% alarm forces True |

```python
# Every jury node reads jury_size before submitting calls
async def run_jury(state: DocumentState) -> dict:
    jury_size: int = state["budget"]["jury_size"]
    css_content_threshold: float = state["budget"]["css_content_threshold"]
    max_iter: int = state["budget"]["max_iterations"]

    if state["current_iteration"] >= max_iter:
        # hard iteration cap reached: set force_approve flag; graph router
        # reads this in route_after_aggregator() and routes to 'force_approve'
        import logging
        logging.warning(
            "FORCE_APPROVE: section_idx=%s reached max_iterations=%s without "
            "CSS convergence. Forcing approval via force_approve flag.",
            state.get("current_section_idx"), max_iter,
        )
        return {"force_approve": True}

    judges_to_call = JURY_SLOTS[:jury_size]   # ordered by reliability
    ...
```

### Budget Controller Node (runtime adjuster)

```
AGENT: BudgetController [§19.5]
RESPONSIBILITY: adjust BudgetState levers after each section based on actual spend
MODEL: deterministic / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  budget: BudgetState
  section_cost_usd: float      # cost of section just completed
OUTPUT: BudgetState
CONSTRAINTS:
  MUST call apply_dynamic_savings() from §19.4
  MUST re-project final cost: projected_final = (spent / sections_done) * total_sections
  MUST call populate_budget_thresholds() (§9.3) after any regime change to refresh
    css_content_threshold, css_style_threshold, and css_panel_threshold in BudgetState
  MUST emit SSE event BUDGET_UPDATE after every section (see §23.5)
  NEVER reduce css_content_threshold below 0.45
  NEVER reduce css_style_threshold below 0.60
  NEVER reduce jury_size below 1
ERROR_HANDLING:
  sections_done == 0 -> skip projection -> return budget unchanged
  max_dollars == 0 -> raise ValueError -> halt preflight
CONSUMES: [budget, current_section_idx, total_sections] from DocumentState
PRODUCES: [budget] -> DocumentState
```

## 19.6 await_human Invocation Taxonomy

The system contains multiple code paths that call `await_human`. These fall into two distinct categories:

### 19.6.1 Scheduled Checkpoints (2 total, per §2.7)

These are the 2 planned, predictable human-in-the-loop pauses defined in §2.7. They occur in every normal run at deterministic points in the graph:

| Checkpoint ID | Trigger | Graph node | §2.7 label |
|---|---|---|---|
| `outline_approval` | Planner completes outline; run cannot proceed until human confirms structure | `await_outline` | outline_approval |
| `escalation_intervention` | User explicitly requests escalation via `/approve` endpoint or oscillation detector routes to human after exhausting automated recovery | `await_human` (oscillation path) | escalation_intervention |

### 19.6.2 Emergency await_human Calls (unplanned interruptions, NOT counted in the §2.7 "exactly 2")

These calls are defensive, event-driven interruptions. They are NOT scheduled and do NOT occur in every run. §2.7's "exactly 2 checkpoints" refers exclusively to the scheduled category above.

| Emergency trigger | Source section | Condition |
|---|---|---|
| `coherence_hard_conflict` | §15.1 CoherenceGuard | New section introduces a factual contradiction with an already-approved section that cannot be auto-resolved |
| `budget_section_anomaly` | §19.4 (this section) | Single section cost exceeds $15.00 |
| `panel_escalation` | §11.3 Panel Discussion | CSS remains below threshold after 2 panel rounds |
| `post_qa_conflict` | §4.3 Post-Flight QA | Contradiction Detector finds cross-section conflict in assembled document |

### 19.6.3 Canonical §2.7 Note

> **§2.7 clarification (normative):** The "EXACTLY 2 checkpoints" in §2.7 refers to the 2 scheduled, predictable human checkpoints present in every run: `outline_approval` and `escalation_intervention`. Emergency `await_human` calls (coherence hard conflict, budget section anomaly, panel escalation after max rounds, post-QA conflict) are unplanned defensive interruptions that occur only when specific failure conditions arise. They are architecturally distinct from the 2 scheduled checkpoints and do not contradict the §2.7 constraint.

<!-- SPEC_COMPLETE -->