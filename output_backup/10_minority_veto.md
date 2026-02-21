Looking at the identified issue, I need to fix the L2 veto filter in `§9.4 route_after_aggregator()` within the `check_l2_veto` function. The current code uses string values `'reasoning'` and `'factual'` to filter `jury_slot`, but `§4.6 JudgeVerdict` defines `judge_slot` as `Literal['R1','R2','R3','F1','F2','F3','S1','S2','S3']`. The fix requires using `startswith('R')`, `startswith('F')`, and `startswith('S')` instead.

Looking at the current file, the `check_l2_veto` function in `§10.2` takes pre-separated verdict lists as parameters, so the filtering issue must be in how these lists are populated in `route_after_aggregator()` (referenced in §9.4). The `check_l2_veto` function itself is fine — the bug is in the caller that splits verdicts before passing them. I need to fix the filter logic to use correct slot prefixes.

```markdown
# 10_minority_veto.md

## Overview

Two-level veto system protecting against majority consensus errors, plus automatic detection of systematically aberrant judges.

---

## 10.1 Level 1 — Individual Veto

Any single judge in any mini-jury may issue a veto independently of the CSS value. A valid L1 veto **overrides any CSS outcome** and immediately routes to the Reflector (see §12).

### veto_category Enum

```python
from typing import Literal

VetoCategory = Literal[
    "fabricated_source",
    "factual_error",
    "logical_contradiction",
    "plagiarism"
]
```

### Category Definitions and System Behavior

```python
VETO_CATEGORY_SPEC: dict[VetoCategory, dict] = {
    "fabricated_source": {
        "definition": "DOI, URL, or author attribution does not correspond to any verifiable real-world source. Ghost citation confirmed.",
        "system_behavior": {
            "route": "reflector",
            "researcher_reactivated": True,
            "fusor_best_elements_usable": False,
            "section_blocked_until": "new_sources_verified",
            "log_level": "CRITICAL",
            "writer_memory_update": "increment_ghost_citation_count"
        }
    },
    "factual_error": {
        "definition": "A specific claim in the draft is directly contradicted by the cited source or by an external source retrieved via Judge F micro-search (see §8.2.1).",
        "system_behavior": {
            "route": "reflector",
            "researcher_reactivated": False,
            "fusor_best_elements_usable": True,
            "section_blocked_until": "claim_corrected_or_removed",
            "log_level": "ERROR",
            "writer_memory_update": "flag_claim_pattern"
        }
    },
    "logical_contradiction": {
        "definition": "The draft contains an internal logical inconsistency: a conclusion does not follow from stated premises, or two statements within the section are mutually exclusive.",
        "system_behavior": {
            "route": "reflector",
            "researcher_reactivated": False,
            "fusor_best_elements_usable": True,
            "section_blocked_until": "contradiction_resolved",
            "log_level": "ERROR",
            "reflector_scope_floor": "PARTIAL",
            "writer_memory_update": "flag_argument_structure"
        }
    },
    "plagiarism": {
        "definition": "More than 50 consecutive words match a single external source verbatim without quotation attribution (see §22.7 copyright rule).",
        "system_behavior": {
            "route": "reflector",
            "researcher_reactivated": False,
            "fusor_best_elements_usable": False,
            "section_blocked_until": "verbatim_removed_or_attributed",
            "log_level": "ERROR",
            "writer_memory_update": "flag_verbatim_tendency"
        }
    }
}
```

### L1 Veto Verdict Schema

```python
class L1VetoVerdict(TypedDict):
    judge_slot: str                  # e.g. "R1", "F2", "S3"
    model: str
    veto_category: VetoCategory
    affected_text: str               # verbatim quote from draft, max 200 chars
    evidence: str                    # justification, max 400 chars
    external_source_url: str | None  # required if veto_category == "fabricated_source" or "factual_error"
    confidence: Literal["low", "medium", "high"]
    timestamp: str                   # ISO 8601
```

### L1 Activation Rule

```python
# Pseudocode — implemented in aggregator node (see §9.4)
def check_l1_veto(verdicts: list[JudgeVerdict]) -> L1VetoVerdict | None:
    for v in verdicts:
        if v.get("veto_category") is not None:
            # First veto wins; multiple vetos all logged but routing triggered on first
            return v  # route to reflector immediately
    return None
```

**CONSTRAINT**: L1 veto triggers regardless of CSS value. A section with CSS = 0.99 and one L1 veto is **BLOCKED**.

---

## 10.2 Level 2 — Unanimous Mini-Jury Veto

If all 3 judges within a single mini-jury return `pass_fail = False` (0/3 pass), the section is blocked independently of the global CSS.

### Activation Condition

```python
def check_l2_veto(
    verdicts_r: list[JudgeVerdict],   # 3 items, judge_slot startswith 'R'
    verdicts_f: list[JudgeVerdict],   # 3 items, judge_slot startswith 'F'
    verdicts_s: list[JudgeVerdict],   # 3 items, judge_slot startswith 'S'
) -> bool:
    for group in [verdicts_r, verdicts_f, verdicts_s]:
        pass_count = sum(1 for v in group if v["pass_fail"] is True)
        if pass_count == 0:           # unanimous failure in one mini-jury
            return True
    return False


# Caller — splits verdicts by judge_slot prefix before invoking check_l2_veto
def split_verdicts_by_jury(verdicts: list[JudgeVerdict]) -> tuple[
    list[JudgeVerdict],  # R-slot verdicts
    list[JudgeVerdict],  # F-slot verdicts
    list[JudgeVerdict],  # S-slot verdicts
]:
    r_verdicts = [v for v in verdicts if v['judge_slot'].startswith('R')]
    f_verdicts = [v for v in verdicts if v['judge_slot'].startswith('F')]
    s_verdicts = [v for v in verdicts if v['judge_slot'].startswith('S')]
    return r_verdicts, f_verdicts, s_verdicts
```

### L2 Behavior

| Triggered mini-jury | Route | Researcher reactivated |
|---|---|---|
| R (Reasoning) | reflector, scope floor = PARTIAL | False |
| F (Factual) | reflector + researcher targeted | True |
| S (Style) | style_fixer (see §9.3) | False |

**CONSTRAINT**: L2 veto is **independent** of L1. Both can trigger simultaneously; L1 veto category takes precedence in the Reflector input.

---

## 10.3 Rogue Judge Detector

AGENT: RogueJudgeDetector [§10.3]
RESPONSIBILITY: Detect judges with systematic disagreement and initiate temporary replacement
MODEL: deterministic (no LLM) / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  verdicts_history: list[dict]   # all JuryRound rows for current document, see §21.1
  current_section_idx: int
  min_sections_evaluated: int    # minimum sections before detection activates = 3
OUTPUT: RogueJudgeReport
CONSTRAINTS:
  MUST evaluate only after min_sections_evaluated >= 3 completed sections
  MUST compute disagreement_rate per judge_slot as fraction of sections where judge voted opposite to supermajority (≥6/9 other judges)
  NEVER flag a judge on fewer than 3 evaluated sections
  ALWAYS emit one RogueJudgeReport per invocation (empty flags list if no rogue detected)
  MUST use disagreement_threshold = 0.70 (>70% disagreement rate over 3+ sections)
ERROR_HANDLING:
  missing verdicts_history -> skip detection -> log WARNING "insufficient_history"
  parse error on JuryRound row -> skip malformed row -> continue on remaining rows
CONSUMES: [all_verdicts_history, current_section_idx] from DocumentState
PRODUCES: [rogue_judge_flags, circuit_breaker_states] -> DocumentState

### RogueJudgeReport Schema

```python
class RogueJudgeFlag(TypedDict):
    judge_slot: str              # e.g. "F2"
    model: str
    disagreement_rate: float     # 0.0 - 1.0; trigger threshold = 0.70
    sections_evaluated: int      # must be >= 3
    action: Literal["temporary_replacement", "monitor"]
    replacement_model: str       # from fallback chain in YAML (see §29.2)

class RogueJudgeReport(TypedDict):
    doc_id: str
    evaluated_at_section: int
    flags: list[RogueJudgeFlag]  # empty list if no rogue detected
    notification_dispatched: bool
```

### Detection Algorithm

```python
DISAGREEMENT_THRESHOLD: float = 0.70
MIN_SECTIONS: int = 3

def detect_rogue_judges(
    verdicts_history: list[dict],
    current_section_idx: int
) -> RogueJudgeReport:
    if current_section_idx < MIN_SECTIONS:
        return RogueJudgeReport(flags=[], ...)

    # Group verdicts by judge_slot across all sections
    by_slot: dict[str, list[bool]] = defaultdict(list)
    for row in verdicts_history:
        # supermajority = ≥6 of 9 judges agree on pass/fail for that section+iteration
        supermajority_verdict = compute_supermajority(row["section_idx"], verdicts_history)
        by_slot[row["judge_slot"]].append(
            row["pass_fail"] != supermajority_verdict  # True = disagreed
        )

    flags: list[RogueJudgeFlag] = []
    for slot, disagreements in by_slot.items():
        if len(disagreements) < MIN_SECTIONS:
            continue
        rate = sum(disagreements) / len(disagreements)
        if rate > DISAGREEMENT_THRESHOLD:
            flags.append(RogueJudgeFlag(
                judge_slot=slot,
                disagreement_rate=rate,
                sections_evaluated=len(disagreements),
                action="temporary_replacement",
                replacement_model=get_fallback_model(slot)
            ))

    return RogueJudgeReport(flags=flags, ...)
```

### Notification Flow

```
RogueJudgeDetector emits RogueJudgeReport
    ↓ flags non-empty
Run Companion (see §6.5) dispatches proactive notification:
    type: "rogue_judge_detected"
    payload: {judge_slot, model, disagreement_rate, sections_evaluated, replacement_model}
    channel: SSE event ESCALATION_REQUIRED (see §23.5)
    ↓
User receives dashboard notification (no run interruption)
    ↓
Aggregator reads rogue_judge_flags from State:
    - Replaces flagged judge slot with replacement_model in circuit_breaker_states
    - Adds JURY_DEGRADED warning to run_metrics
    - Continues production without pause
```

**CONSTRAINT**: Rogue judge replacement is **temporary** (current document only). Does not modify YAML config. Flagged judge is logged in Run Report for post-run analysis.

### Rogue Judge Log Schema (PostgreSQL)

```python
# Stored in JuryRound table (see §21.1) — additional fields
class RogueJudgeLogEntry(TypedDict):
    doc_id: str
    judge_slot: str
    model: str
    disagreement_rate: float       # at time of detection
    sections_evaluated: int
    detected_at_section_idx: int
    replacement_model: str
    replacement_effective_from_section: int
    notification_sent_at: str      # ISO 8601
    user_acknowledged: bool
```

### Fallback Behavior During Replacement

```python
# CSS recalculated on active judges only (see §9.1)
# If replacement_model also fails circuit breaker → JURY_DEGRADED warning
# Minimum viable jury: 1 judge per mini-jury (graceful degradation, see §20.5)
# If all 3 judges in a mini-jury unavailable → L2 veto cannot be evaluated
#   → section routed to human escalation with flag "jury_unavailable"
```

---

## Cross-References

| Topic | Section |
|---|---|
| CSS formula and jury weights | §9.1, §9.2 |
| Aggregator routing post-veto | §9.4 |
| Judge F micro-search (external evidence for factual_error veto) | §8.2.1 |
| Reflector scope SURGICAL/PARTIAL/FULL | §12.2 |
| Style Fixer for Style unanimous fail | §5.10 |
| Run Companion proactive notifications | §6.5 |
| JuryRound table schema | §21.1 |
| Fallback chain configuration | §29.2 |
| Graceful degradation thresholds | §20.5 |
| Copyright 50-word verbatim rule | §22.7 |

<!-- SPEC_COMPLETE -->
```