Looking at the issue: `route_after_oscillation()` returns `'budget_warn'` which routes to a `budget_controller` node, but this route is undefined in the spec and conflicts with how budget warnings actually work (handled by `BudgetController` node running before every Writer/Jury call). The fix is to remove `'budget_warn'` from the return type and the function body.

```markdown
# §13 — Oscillation Detector

## 13.0 Overview

Stateful component invoked after every `reflector` node. Reads `css_history` and `current_draft` embeddings from `DocumentState`, classifies oscillation type, emits early-warning or escalation signals.

```python
OscillationType = Literal["CSS_OSCILLATION", "SEMANTIC_OSCILLATION", "WHACK_A_MOLE"]
OscillationSeverity = Literal["EARLY_WARNING", "ESCALATE"]

class OscillationResult(TypedDict):
    detected: bool
    oscillation_type: OscillationType | None
    severity: OscillationSeverity | None
    evidence: dict            # type-specific diagnostic payload
    ui_data: "EscalationUIData | None"
```

---

## 13.1 CSS Oscillation

**Condition**: `variance(css_history[-N:]) < VAR_THRESHOLD` where `N >= 4`.

```python
CSS_WINDOW: int = 4           # minimum iterations required
VAR_THRESHOLD: float = 0.0025 # variance < this → oscillation
                               # derived: std_dev < 0.05
```

**Formula**:
```python
import statistics

def detect_css_oscillation(css_history: list[float]) -> bool:
    if len(css_history) < CSS_WINDOW:
        return False
    window = css_history[-CSS_WINDOW:]
    return statistics.variance(window) < VAR_THRESHOLD
```

**Evidence payload**:
```python
class CSSEvidence(TypedDict):
    window: list[float]        # last CSS_WINDOW values
    variance: float
    mean: float
    threshold_used: float
```

**Early warning**: triggered at `N == 3` (one iteration before hard condition) if `variance(css_history[-3:]) < VAR_THRESHOLD * 2.0`.

---

## 13.2 Semantic Oscillation

**Condition**: `cosine_sim(embed(draft_N), embed(draft_{N-2})) >= SEM_SIM_THRESHOLD` AND `cosine_sim(embed(draft_N), embed(draft_{N-1})) < SEM_SIM_THRESHOLD`.

```python
SEM_SIM_THRESHOLD: float = 0.85   # cosine similarity ≥ this = near-identical
MIN_ITER_SEMANTIC: int = 3         # need at least 3 drafts in history
```

**Formula**:
```python
from numpy import dot
from numpy.linalg import norm

def cosine_sim(a: list[float], b: list[float]) -> float:
    return float(dot(a, b) / (norm(a) * norm(b)))

def detect_semantic_oscillation(embeddings: list[list[float]]) -> bool:
    if len(embeddings) < MIN_ITER_SEMANTIC:
        return False
    N, N1, N2 = embeddings[-1], embeddings[-2], embeddings[-3]
    sim_N_N2 = cosine_sim(N, N2)
    sim_N_N1 = cosine_sim(N, N1)
    return sim_N_N2 >= SEM_SIM_THRESHOLD and sim_N_N1 < SEM_SIM_THRESHOLD
```

**Embedding model**: `sentence-transformers/all-MiniLM-L6-v2` (local, zero API cost). Computed by `oscillation_detector` node; stored in `DocumentState.draft_embeddings`.

**Evidence payload**:
```python
class SemanticEvidence(TypedDict):
    sim_N_N2: float    # should be >= SEM_SIM_THRESHOLD
    sim_N_N1: float    # should be < SEM_SIM_THRESHOLD
    threshold: float
```

**Early warning**: triggered if `sim_N_N2 >= 0.75` (below threshold but trending toward repetition) after `MIN_ITER_SEMANTIC` drafts.

---

## 13.3 Whack-a-Mole Detection

**Condition**: error categories produced by Reflector change completely across `WAM_WINDOW` consecutive iterations, with zero category overlap between iteration `N` and `N-1`.

```python
WAM_WINDOW: int = 3        # evaluate last N iterations of reflector feedback
WAM_OVERLAP_MAX: int = 0   # max shared categories before NOT flagging
WAM_ESCALATE_AFTER: int = 3  # escalate after this many WAM cycles
```

**Error categories** (from Reflector output, see §12.1):
```python
FeedbackCategory = Literal[
    "factual_error", "logical_contradiction", "missing_evidence",
    "style_violation", "citation_missing", "structural_issue",
    "fabricated_source", "plagiarism"
]
```

**Formula**:
```python
def detect_whack_a_mole(
    category_history: list[set[FeedbackCategory]]
) -> bool:
    if len(category_history) < WAM_WINDOW:
        return False
    recent = category_history[-WAM_WINDOW:]
    # check zero overlap between each consecutive pair
    for i in range(len(recent) - 1):
        overlap = len(recent[i] & recent[i+1])
        if overlap > WAM_OVERLAP_MAX:
            return False
    return True
```

**Evidence payload**:
```python
class WhackAMoleEvidence(TypedDict):
    category_history: list[list[FeedbackCategory]]   # last WAM_WINDOW
    overlap_counts: list[int]                        # overlap per pair
```

**Early warning**: triggered after `WAM_ESCALATE_AFTER - 1 = 2` cycles with zero overlap.

---

## 13.4 Escalation UI Data

Produced only when `severity == "ESCALATE"`. Passed to `await_human` node (see §4.5).

```python
class CSSHistoryEntry(TypedDict):
    iteration: int
    css_content: float
    css_style: float
    verdict_summary: str   # one-line: e.g. "FAIL: factual(2), style(1)"

class DraftLogEntry(TypedDict):
    iteration: int
    draft_hash: str        # sha256[:8] for identification
    word_count: int
    reflector_scope: Literal["SURGICAL", "PARTIAL", "FULL"]
    categories: list[FeedbackCategory]

class EscalationUIData(TypedDict):
    section_idx: int
    section_title: str
    oscillation_type: OscillationType
    css_history: list[CSSHistoryEntry]
    draft_log: list[DraftLogEntry]
    problem_summary: str   # ≤ 280 chars, human-readable root cause
    available_actions: list[EscalationAction]

EscalationAction = Literal[
    "add_writer_instructions",   # user provides free-text guidance
    "approve_with_warning",      # force approve current draft, log warning
    "skip_section",              # mark section as SKIPPED, continue
    "modify_section_scope",      # edit outline entry for this section
    "abort_run"                  # terminate run, return partial document
]
```

---

## 13.5 Agent Specification

```
AGENT: OscillationDetector [§13]
RESPONSIBILITY: classify oscillation type from css_history, draft embeddings, and reflector category history
MODEL: deterministic (no LLM) / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
    css_history: list[float]                        # from DocumentState
    draft_embeddings: list[list[float]]             # from DocumentState
    reflector_category_history: list[set[FeedbackCategory]]  # accumulated per section
    current_iteration: int                          # from DocumentState
    section_idx: int
    section_title: str
    css_history_entries: list[CSSHistoryEntry]      # for UI data
    draft_log_entries: list[DraftLogEntry]          # for UI data
OUTPUT: OscillationResult
CONSTRAINTS:
    MUST evaluate all three oscillation types on every invocation
    MUST emit EARLY_WARNING before ESCALATE (no direct escalation without prior warning)
    MUST set oscillation_type = None when detected = False
    NEVER modify DocumentState fields other than those in PRODUCES
    ALWAYS compute embeddings locally via sentence-transformers (no external API)
    MUST include ui_data when severity == "ESCALATE"
    MUST set ui_data = None when severity != "ESCALATE"
ERROR_HANDLING:
    embedding_computation_fails -> log warning, skip SEMANTIC check, continue with CSS + WAM -> no fallback needed
    css_history length < CSS_WINDOW -> detected=False for CSS type, continue
    reflector_category_history length < WAM_WINDOW -> detected=False for WAM type, continue
CONSUMES:
    [css_history, draft_embeddings, current_iteration] from DocumentState
PRODUCES:
    [oscillation_detected, oscillation_type, human_intervention_required] -> DocumentState
```

---

## 13.6 Priority and Routing

When multiple oscillation types detected simultaneously, priority:

```python
OSCILLATION_PRIORITY: dict[OscillationType, int] = {
    "SEMANTIC_OSCILLATION": 1,   # highest — silent, hardest to fix
    "CSS_OSCILLATION": 2,
    "WHACK_A_MOLE": 3
}
```

Routing after `oscillation_check` node (see §4.5):

```python
def route_after_oscillation(state: DocumentState) -> Literal["continue", "escalate_human"]:
    if not state["oscillation_detected"]:
        return "continue"            # -> writer node
    result = state.get("_oscillation_result")
    if result["severity"] == "EARLY_WARNING":
        return "continue"            # writer gets warning injected via WriterMemory
    # severity == ESCALATE
    return "escalate_human"          # -> await_human node
```

Early warning injection: `OscillationDetector` writes a structured warning into `WriterMemory` (see §16) with the detected pattern, so the next Writer iteration receives explicit guidance without pausing the run.

```python
class OscillationWarning(TypedDict):
    warning_type: OscillationType
    message: str      # ≤ 150 chars injected into Writer context
    iteration: int
```

<!-- SPEC_COMPLETE -->
```