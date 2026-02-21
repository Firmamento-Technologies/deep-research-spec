Looking at the identified issue, I need to:

1. Fix `§15.3` Format Validator's "Length Routing Sub-Rule" to replace `routing = "reflector"` for `delta < -0.10` with `"length_adjuster"`
2. Fix `§15.4` `route_post_qa()` to replace `"reflector"` in the priority list with `"length_adjuster"`
3. Add a `FormatFailure` literal and routing for `length_adjuster`
4. Define the `length_adjuster` node behavior
5. Update `§15.0` types to include `"length_adjuster"` in the `FormatIssue.routing` literal
6. Update `§15.6` cross-references

Here is the fixed file:

```markdown
# 15_coherence_guard.md
## §15 — Coherence Guard, Contradiction Detector, Format Validator

---

## §15.0 Shared Types

```python
from typing import Literal, Optional
from pydantic import BaseModel

ConflictLevel = Literal["SOFT", "HARD"]
ConflictCategory = Literal[
    "factual_contradiction",
    "quantitative_mismatch",
    "temporal_inconsistency",
    "causal_reversal",
    "definition_conflict",
]
RoutingDecision = Literal["no_conflict", "soft_conflict", "hard_conflict"]
FormatFailure = Literal[
    "missing_reference",
    "section_absent",
    "length_out_of_range",
    "l1_violation",
    "citation_no_entry",
]

class ClaimConflict(BaseModel):
    section_a_idx: int
    section_b_idx: int
    claim_a: str            # verbatim excerpt ≤ 120 chars
    claim_b: str            # verbatim excerpt ≤ 120 chars
    category: ConflictCategory
    level: ConflictLevel
    resolution_hint: str    # one actionable sentence

class ContradictionReport(BaseModel):
    doc_id: str
    conflicts: list[ClaimConflict]
    hard_count: int
    soft_count: int

class FormatIssue(BaseModel):
    failure_type: FormatFailure
    location: str           # e.g. "§3 para 2" or "bibliography"
    detail: str
    routing: Literal["length_adjuster", "style_fixer", "publisher_retry", "human"]

class FormatValidationReport(BaseModel):
    doc_id: str
    issues: list[FormatIssue]
    word_count_actual: int
    word_count_target: int
    word_count_delta_pct: float
    passed: bool
```

---

## §15.1 Coherence Guard

### Purpose
Cross-section factual conflict detection **before final approval** of each new section. Executes after Context Compressor (§14), before `section_checkpoint` node.

### Classification Rules

| Condition | Level | Action |
|-----------|-------|--------|
| Direct factual negation between sections | HARD | Escalate to human via `await_human` |
| Quantitative mismatch (same metric, different value ≥ 10%) | HARD | Escalate |
| Temporal inconsistency (event ordering reversed) | HARD | Escalate |
| Causal reversal (A causes B vs B causes A) | HARD | Escalate |
| Partial ambiguity (different framing, not direct negation) | SOFT | Log + continue |
| Definitional nuance between sections | SOFT | Log + continue |

```python
class CoherenceGuardInput(BaseModel):
    doc_id: str
    section_idx: int            # newly approved section index
    approved_section_content: str
    prior_sections: list[dict]  # ApprovedSection list from DocumentState
    compressed_context: str     # from §14

class CoherenceGuardOutput(BaseModel):
    routing: RoutingDecision
    conflicts: list[ClaimConflict]
    diff_visual: Optional[str]  # populated only when routing == "hard_conflict"
```

---

AGENT: CoherenceGuard [§15.1]
RESPONSIBILITY: Detect factual conflicts between a newly approved section and all prior approved sections
MODEL: google/gemini-2.5-pro / TEMP: 0.1 / MAX_TOKENS: 2048
INPUT:
  input: CoherenceGuardInput
OUTPUT: CoherenceGuardOutput
CONSTRAINTS:
  MUST compare every claim in `approved_section_content` against `prior_sections` content
  MUST classify each conflict as SOFT or HARD per §15.0 rules table
  MUST populate `diff_visual` (unified-diff format, ≤ 40 lines) when any HARD conflict found
  MUST emit `routing = "no_conflict"` when `conflicts` is empty
  MUST emit `routing = "hard_conflict"` when `hard_count >= 1`
  MUST emit `routing = "soft_conflict"` when `hard_count == 0` and `soft_count >= 1`
  NEVER modify section content
  NEVER flag stylistic differences as conflicts
  ALWAYS include verbatim excerpts ≤ 120 chars for claim_a and claim_b
ERROR_HANDLING:
  LLM parse failure -> retry once with simplified prompt -> if still fails: emit routing="soft_conflict" with conflicts=[] and log WARN
  Context overflow -> truncate prior_sections to last 8 sections -> retry
  Model unavailable -> fallback to anthropic/claude-sonnet-4 -> if also down: emit routing="soft_conflict", log WARN
CONSUMES: [current_draft, approved_sections, compressed_context] from DocumentState
PRODUCES: [coherence_conflicts, current_section_routing] -> DocumentState

---

### LangGraph Routing

```python
def route_after_coherence(state: DocumentState) -> str:
    routing = state["coherence_conflicts_routing"]
    # routing: RoutingDecision
    if routing == "no_conflict":
        return "section_checkpoint"
    elif routing == "soft_conflict":
        # log only, continue
        return "section_checkpoint"
    else:  # hard_conflict
        return "await_human"
    # await_human presents diff_visual + conflict list to operator
```

Human response at `await_human`: `Literal["override_approve", "reopen_section", "reopen_prior"]`

---

## §15.2 Contradiction Detector

### Purpose
Post-assembly full-document scan after all sections are approved and assembled. Runs in **Fase C** (§4.3) as part of `post_qa` node. Catches conflicts undetectable during incremental approval (e.g., sections 2 and 9 approved weeks apart).

```python
class ContradictionDetectorInput(BaseModel):
    doc_id: str
    assembled_sections: list[dict]   # full content, all sections in order
    section_count: int

class ContradictionDetectorOutput(BaseModel):
    report: ContradictionReport
    routing: Literal["pass", "human_review"]
    # routing = "human_review" when report.hard_count >= 1
    # routing = "pass" when hard_count == 0 (soft conflicts logged only)
```

---

AGENT: ContradictionDetector [§15.2]
RESPONSIBILITY: Full cross-section contradiction scan on the assembled document post-production
MODEL: openai/o3 / TEMP: 0.1 / MAX_TOKENS: 4096
INPUT:
  input: ContradictionDetectorInput
OUTPUT: ContradictionDetectorOutput
CONSTRAINTS:
  MUST scan all section pairs (N×(N-1)/2 pairs) for contradictions
  MUST use same ConflictCategory taxonomy as §15.0
  MUST set routing="human_review" if hard_count >= 1
  MUST set routing="pass" if hard_count == 0
  NEVER halt on soft conflicts; always include them in report and continue
  ALWAYS emit ContradictionReport even if conflicts=[]
  NEVER re-evaluate style or citation issues (see §15.3)
ERROR_HANDLING:
  Context overflow (large doc) -> split into overlapping section-pair batches of 6 sections, merge reports -> no information loss
  LLM failure after 2 retries -> fallback to anthropic/claude-opus-4-5 -> if down: emit routing="pass" with WARN log, flag run_report
  JSON parse error -> retry with schema-enforced prompt -> fallback as above
CONSUMES: [approved_sections] from DocumentState
PRODUCES: [post_qa_contradiction_report] -> DocumentState

---

## §15.3 Format Validator

### Purpose
Deterministic (non-LLM) post-assembly validation. Executes in `post_qa` node after ContradictionDetector. Checks four conditions and routes failures to the appropriate fix node.

### Checks and Routing Table

| Check | Condition | Failure Type | Routing |
|-------|-----------|--------------|---------|
| Referenced sections exist | `§N.M` cross-refs in text point to actual section titles | `missing_reference` | `publisher_retry` |
| Length within range | `abs(actual - target) / target <= 0.10` | `length_out_of_range` | `length_adjuster` or `style_fixer` |
| Zero L1 violations | Style Linter (§5.9) regex scan on final assembled text | `l1_violation` | `style_fixer` |
| All citations have bibliography entry | Every `[AuthorYear]` or `(Author, Year)` maps to bibliography | `citation_no_entry` | `publisher_retry` |

```python
class FormatValidatorInput(BaseModel):
    doc_id: str
    assembled_text: str
    bibliography: dict[str, str]    # citation_id -> formatted_entry
    target_words: int
    section_titles: list[str]
    style_profile: str              # passed to Style Linter

class FormatValidatorOutput(BaseModel):
    report: FormatValidationReport
    routing_actions: list[tuple[FormatFailure, Literal[
        "length_adjuster", "style_fixer", "publisher_retry", "human"
    ]]]
    # empty list = all checks passed -> proceed to publisher
    all_passed: bool
```

### Length Routing Sub-Rule
```python
# When length_out_of_range:
delta = (actual - target) / target
if delta > 0.10:
    routing = "style_fixer"       # compress: Revisor with token budget
elif delta < -0.10:
    routing = "length_adjuster"   # expand: Writer invoked directly with
                                  # explicit word count instruction,
                                  # bypassing jury/reflector loop
```

---

AGENT: FormatValidator [§15.3]
RESPONSIBILITY: Deterministic post-assembly validation of structure, length, L1 compliance, and citation completeness
MODEL: none — deterministic / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  input: FormatValidatorInput
OUTPUT: FormatValidatorOutput
CONSTRAINTS:
  MUST run Style Linter regex (§5.9 L1 rules) on assembled_text before emitting report
  MUST flag every unresolved `§N.M` reference not matching any entry in section_titles
  MUST compute word_count_delta_pct = (actual - target) / target; flag if abs() > 0.10
  MUST cross-check every in-text citation token against bibliography keys
  MUST emit routing_action ("length_out_of_range", "length_adjuster") when delta < -0.10
  MUST emit routing_action ("length_out_of_range", "style_fixer") when delta > 0.10
  NEVER call any LLM
  NEVER modify content — validation only
  ALWAYS emit all failures found; do not short-circuit on first failure
  ALWAYS set all_passed=True only when routing_actions is empty
ERROR_HANDLING:
  Malformed assembled_text (encoding error) -> log ERROR, emit all_passed=False with routing human -> abort publisher
  Missing bibliography dict -> treat all citations as citation_no_entry failures -> route publisher_retry
  Style Linter import failure -> log CRITICAL, emit l1_violation for entire doc -> route style_fixer
CONSUMES: [approved_sections, bibliography, target_words, style_profile] from DocumentState
PRODUCES: [format_validation_report, format_validated] -> DocumentState

---

## §15.4 Post-QA Node Sequence

```
post_qa node execution order (Fase C):
  1. ContradictionDetector  → updates post_qa_contradiction_report
  2. FormatValidator        → updates format_validation_report, format_validated
  3. route_post_qa()        → determines next node
```

```python
def route_post_qa(state: DocumentState) -> str:
    contradiction_routing = state["post_qa_contradiction_report"].routing
    format_actions = state["format_validation_report"].routing_actions

    if contradiction_routing == "human_review":
        return "await_human"

    if not state["format_validated"]:
        # pick highest-priority routing from format_actions
        # priority: human > style_fixer > length_adjuster > publisher_retry
        priorities = ["human", "style_fixer", "length_adjuster", "publisher_retry"]
        for p in priorities:
            if any(r == p for _, r in format_actions):
                return p

    return "publisher"
```

---

## §15.4.1 Length Adjuster Node

### Purpose
Handles `length_out_of_range` failures where the assembled document is **shorter** than target
(`delta < -0.10`). Invokes the Writer directly with an explicit word count instruction on the
identified short sections, bypassing the full jury/reflector loop. Compression failures
(`delta > 0.10`) are handled by `style_fixer` (§5.10), not this node.

```python
class LengthAdjusterInput(BaseModel):
    doc_id: str
    assembled_text: str
    word_count_actual: int
    word_count_target: int
    word_count_delta_pct: float     # negative value; abs() > 0.10
    approved_sections: list[dict]   # ApprovedSection list from DocumentState
    style_profile: str
    compressed_context: str         # from DocumentState

class LengthAdjusterOutput(BaseModel):
    expanded_sections: list[dict]   # sections rewritten with additional content
    word_count_new: int
    sections_modified: list[int]    # section indices that were expanded
```

### Expansion Logic
```python
# Identify sections to expand (proportional deficit distribution):
words_needed = word_count_target - word_count_actual
# Distribute expansion proportionally across all sections by current length.
# Each section receives an explicit target_words instruction:
#   section_new_target = section_current_words + round(
#       words_needed * (section_current_words / word_count_actual)
#   )
# Writer is called once per section that requires expansion with:
#   - Current section content
#   - Explicit instruction: "Expand this section to approximately {section_new_target} words.
#     Add supporting detail, elaboration of existing arguments, and concrete examples.
#     Do NOT introduce new claims unsupported by the section's existing citations.
#     Do NOT alter any citation keys or factual figures already present."
#   - style_profile and Style Exemplar (from DocumentState)
#   - compressed_context (surrounding approved sections for coherence)
# No jury evaluation, no Reflector invocation, no CSS computation.
# The expanded assembled text is re-evaluated by FormatValidator once.
# If still length_out_of_range after one length_adjuster pass -> route "human".
```

---

NODE: LengthAdjuster [§15.4.1]
RESPONSIBILITY: Expand a post-QA assembled document that is more than 10% shorter than target
  by invoking the Writer directly with explicit per-section word count instructions
MODEL: anthropic/claude-opus-4-5 / TEMP: 0.3 / MAX_TOKENS: 4096
INPUT:
  input: LengthAdjusterInput
OUTPUT: LengthAdjusterOutput
CONSTRAINTS:
  MUST compute per-section expansion targets proportionally to current section length
  MUST pass explicit numeric word count target in Writer instruction for each expanded section
  MUST include style_profile, Style Exemplar, and compressed_context in every Writer call
  MUST instruct Writer to not introduce claims unsupported by existing section citations
  MUST instruct Writer to preserve all existing citation keys and factual figures verbatim
  MUST re-invoke FormatValidator after expansion to confirm length compliance
  MUST route to "human" if assembled text remains length_out_of_range after one expansion pass
  NEVER invoke jury nodes (jury, aggregator, panel_discussion)
  NEVER invoke reflector node
  NEVER invoke coherence_guard (expansion is content-preserving, not claim-altering)
  NEVER expand sections already within ±5% of their individual word budget
ERROR_HANDLING:
  Writer LLM failure -> retry once with simplified prompt -> if still fails: log ERROR,
    emit sections_modified=[], route to "human"
  Expanded word_count_new still < target * 0.90 after one pass -> route to "human", log WARN
  Model unavailable -> fallback to anthropic/claude-sonnet-4 -> if also down: route "human"
CONSUMES: [assembled_text, approved_sections, word_count_target, style_profile,
           compressed_context] from DocumentState
PRODUCES: [expanded_sections, format_validation_report (re-run)] -> DocumentState

---

## §15.5 DocumentState Fields Produced

```python
# Fields written by §15 agents into DocumentState
coherence_conflicts: list[ClaimConflict]          # §15.1
coherence_conflicts_routing: RoutingDecision       # §15.1
post_qa_contradiction_report: ContradictionReport  # §15.2
format_validation_report: FormatValidationReport   # §15.3
format_validated: bool                             # §15.3 — True only if all_passed
```

---

## §15.6 Cross-References

- L1 forbidden pattern definitions: see §26.1
- Style Linter regex implementation: see §5.9
- `await_human` node interface: see §32.4
- `section_checkpoint` node: see §4.2
- `post_qa` node placement in graph: see §4.3
- `style_fixer` routing target (compression): see §5.10
- `publisher` node: see §5.19
- `length_adjuster` node: see §15.4.1
- DocumentState full schema: see §4.6

<!-- SPEC_COMPLETE -->
```