# §27 Prompt Layer

## §27.0 Module Overview

Prompt Layer governs all LLM prompt construction, versioning, A/B testing, and anti-sycophancy enforcement across the DRS agent graph. Consumed by every agent that calls an LLM.

---

## §27.1 Three-Level Prompt Structure

Every prompt is assembled from three immutable layers in order:

```python
from typing import Literal, Optional
from dataclasses import dataclass

PromptLevel = Literal["system", "context", "task"]

@dataclass(frozen=True)
class PromptLayer:
    level: PromptLevel
    content: str
    mutable: bool  # False for system, True for context/task

@dataclass
class AssembledPrompt:
    system: str       # immutable: identity, role, absolute constraints, output schema
    context: str      # dynamic: State fields, compressed sections, sources, feedback
    task: str         # per-invocation: exact instruction, word budget, section target
    prompt_id: str    # e.g. "writer_v2.1.3"
    version: str      # semver
```

### §27.1.1 Layer Responsibilities

| Layer | Mutability | Content | Owner |
|-------|-----------|---------|-------|
| `system` | Frozen at run start | Role identity, output format schema, absolute NEVER/ALWAYS rules, anti-sycophancy directive (judges only) | PromptRegistry |
| `context` | Rebuilt per invocation | `approved_sections` (compressed, see §14), current sources, `writer_memory` (see §16), `reflector_output`, `style_exemplar` (see §3B.2) | State → `context_builder()` |
| `task` | Per-invocation | Section title, scope, word budget `±5%`, iteration number, specific constraint override | Caller node |

### §27.1.2 Annotated Placeholder Template

```yaml
# prompts/writer/v2/writer_v2.1.3.md
# metadata: see §27.3 schema

system: |
  You are a senior research writer producing section {{SECTION_INDEX}} of {{TOTAL_SECTIONS}}.
  Style profile: {{STYLE_PROFILE}}              # injected from config
  Forbidden patterns (L1): {{L1_FORBIDDEN_LIST}}  # from §26.1, Style Linter
  Output format: raw prose only. No markdown headers. No bullet lists unless profile=technical.
  ABSOLUTE RULE: never fabricate citations. If a claim lacks a source, omit the claim.

context: |
  ## Style Exemplar (reference register, do not copy):
  {{STYLE_EXEMPLAR}}                             # from State.style_exemplar, see §3B.2

  ## Approved sections summary (compressed):
  {{COMPRESSED_CONTEXT}}                         # from Context Compressor §14

  ## Sources for this section (verified):
  {{SYNTHESIZED_SOURCES}}                        # from Source Synthesizer §5.6

  ## Writer Memory (recurring errors to avoid):
  {{WRITER_MEMORY_WARNINGS}}                     # from WriterMemory §16.1

  ## Reflector feedback (iteration {{ITERATION}} only if iter > 1):
  {{REFLECTOR_FEEDBACK}}                         # from Reflector §12.1, empty string if iter=1

task: |
  Write section "{{SECTION_TITLE}}".
  Scope: {{SECTION_SCOPE}}
  Target: {{TARGET_WORDS}} words (±5%).
  Citation mapping: {{CITATION_MAP}}             # source_id → citation string
  Angle (MoW only): {{WRITER_ANGLE}}             # Coverage|Argumentation|Readability, see §7.2
```

```yaml
# prompts/judge_factual/v1/judge_factual_v1.2.0.md

system: |
  You are Judge Factual. Your role is adversarial verification, NOT validation.
  {{ANTI_SYCOPHANCY_BLOCK}}                      # see §27.2 — injected verbatim
  Output schema (strict JSON): see §8.6.
  NEVER return PASS without checking every cited claim against its source.
  confidence field is MANDATORY: Literal["low","medium","high"]

context: |
  ## Section under review:
  {{DRAFT_TEXT}}

  ## Verified sources pool:
  {{SOURCES_POOL}}

  ## Prior jury verdicts this section (for Panel Discussion only):
  {{PRIOR_VERDICTS}}                             # empty string in normal flow

task: |
  Evaluate the draft. Identify fabricated sources, unverified statistics,
  causal claims without evidence. Return JSON conforming to §8.6 schema.
  Section: {{SECTION_TITLE}} | Iteration: {{ITERATION}} | Run: {{RUN_ID}}
```

```yaml
# prompts/reflector/v1/reflector_v1.0.4.md

system: |
  You are the Reflector. You synthesize jury verdicts into actionable writer instructions.
  Output: structured JSON with fields: scope, feedback_items[], iteration_summary.
  scope MUST be one of: Literal["SURGICAL","PARTIAL","FULL"]
  SURGICAL: ≤4 isolated spans, no argument restructuring required.
  PARTIAL: many spans or interdependent issues → Writer rewrites affected paragraphs.
  FULL: argument structure broken → escalate to human (§13.4).

context: |
  ## All jury verdicts this section (all iterations):
  {{ALL_VERDICTS_HISTORY}}

  ## Current draft:
  {{CURRENT_DRAFT}}

  ## Writer Memory (recurring patterns):
  {{WRITER_MEMORY_WARNINGS}}

task: |
  Identify root cause of failure. Produce prioritized feedback_items.
  Each item: severity (CRITICAL|HIGH|MEDIUM|LOW), category, affected_text (exact quote),
  action (imperative instruction), replacement_length_hint (SHORTER|SAME|LONGER).
  Conflict rule: highest severity wins; ties → FACTUAL overrides STYLE (see §12.3).
```

---

## §27.2 Anti-Sycophancy Formulation

The `{{ANTI_SYCOPHANCY_BLOCK}}` placeholder resolves to this exact string, injected verbatim into all Judge system prompts (R, F, S):

```python
ANTI_SYCOPHANCY_BLOCK: str = """\
ADVERSARIAL MANDATE: Your task is falsification, not validation.
Assume the draft contains at least one error. Actively search for evidence that it is wrong.
Do NOT award PASS because you cannot find a flaw — absence of obvious errors is insufficient.
Bias toward FAIL when uncertain. A false FAIL costs one iteration. A false PASS ships a defect.
If you find yourself writing "the draft is well-written" — stop. That is not your evaluation axis.
Evaluate: (1) are all factual claims supported by the provided sources?
          (2) are the sources real, accessible, and correctly represented?
          (3) does the logic hold under adversarial scrutiny?
NEVER soften a negative verdict because the draft is "mostly good".
Report the worst finding at full severity.\
"""
```

Usage constraint: `ANTI_SYCOPHANCY_BLOCK` is injected **only** into Judge system prompts. It MUST NOT appear in Writer, Reflector, Fusor, or Planner prompts.

---

## §27.3 Prompt Versioning

### §27.3.1 File Naming Convention

```
prompts/{agent_slug}/{vMAJOR}/{agent_slug}_v{MAJOR}.{MINOR}.{PATCH}.md
```

Examples:
```
prompts/writer/v2/writer_v2.1.3.md
prompts/judge_factual/v1/judge_factual_v1.2.0.md
prompts/reflector/v1/reflector_v1.0.4.md
prompts/judge_reasoning/v1/judge_reasoning_v1.1.0.md
prompts/judge_style/v1/judge_style_v1.0.2.md
```

Semver semantics:
- `MAJOR`: output schema change or behavior change requiring node code update → manual deploy
- `MINOR`: behavior improvement, same schema → auto-deploy if Golden Set passes
- `PATCH`: typo/wording fix → auto-deploy if smoke subset passes

### §27.3.2 Prompt File Schema

```yaml
# Required front-matter block in every prompt file
metadata:
  id: str                        # "writer_v2.1.3"
  agent: str                     # "writer"
  version: str                   # "2.1.3"
  model_family: str              # "claude-opus-4-5"
  last_tested: str               # ISO date "2026-03-01"
  owner: str                     # "prompt-team"
  golden_set_pass_rate: float    # 0.0–1.0, updated by CI
  avg_css_delta: float           # vs previous MINOR, updated by CI
  variables:                     # declared template variables
    required: list[str]
    optional: list[str]
  changelog:
    - version: str
      date: str
      change: str
      reason: str
      tested_on_golden_set: bool
      css_delta: float           # positive = improvement
```

### §27.3.3 Failure Log

Failures written to `prompt_failure_log` table (PostgreSQL):

```python
class PromptFailureLog(Base):
    __tablename__ = "prompt_failure_log"
    id: UUID
    prompt_id: str               # "writer_v2.1.3"
    run_id: str
    section_idx: int
    iteration: int
    failure_type: Literal[
        "json_parse_error",
        "missing_required_field",
        "instruction_ignored",
        "output_truncated",
        "schema_mismatch"
    ]
    raw_output_snippet: str      # first 500 chars
    timestamp: datetime
```

Any `prompt_id` accumulating ≥5 failures of the same `failure_type` within 24h triggers `DRIFT_ALERT` (see §27.3.4).

### §27.3.4 Review Schedule

| Event | Action | Threshold |
|-------|--------|-----------|
| Weekly CI job | Full Golden Set run on prod prompts | `hard_pass_rate` drop ≥0.05 → `DRIFT_ALERT` |
| Weekly CI job | Full Golden Set run on prod prompts | `hard_pass_rate` drop ≥0.10 → `DRIFT_CRITICAL`, block deploy |
| Weekly CI job | Soft metrics vs baseline | drop ≥0.08 → `DRIFT_WARNING` |
| Model provider update | Re-run Golden Set within 48h | Any regression → evaluate fallback |
| DRIFT_CRITICAL | Mandatory review Monday | Assign owner, create fix PR within 5 days |

---

## §27.4 PromptRegistry and A/B Testing

### §27.4.1 PromptRegistry Schema

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class PromptVersionMetrics(BaseModel):
    version: str
    golden_set_hard_pass_rate: float          # 0.0–1.0
    golden_set_soft_metrics_avg: float        # 0.0–1.0
    avg_css_contribution: float               # mean CSS delta attributed to this prompt
    avg_iterations_to_approval: float
    failure_rate_24h: float                   # prompt_failure_log hits / invocations
    total_invocations: int
    last_evaluated: datetime

class PromptRecord(BaseModel):
    agent: str
    active_version: str                       # version serving 100% traffic (or control)
    candidate_version: Optional[str]          # version in A/B test (treatment arm)
    ab_test_id: Optional[str]
    versions: dict[str, PromptVersionMetrics] # keyed by version string
    rollback_version: str                     # last known-good before active
    auto_rollback_enabled: bool = True

class PromptRegistry(BaseModel):
    prompts: dict[str, PromptRecord]          # keyed by agent slug
    schema_version: str = "1.0"
    last_updated: datetime
```

### §27.4.2 A/B Testing Framework

```python
class ABTestConfig(BaseModel):
    test_id: str
    agent: str
    control_version: str
    treatment_version: str
    traffic_split: float                      # 0.0–1.0, fraction to treatment
    min_runs_per_arm: int = 30
    significance_level: float = 0.05
    primary_metric: Literal[
        "avg_css_contribution",
        "avg_iterations_to_approval",
        "golden_set_hard_pass_rate"
    ]
    auto_promote_threshold: float             # treatment must exceed control by this delta
    auto_rollback_threshold: float            # rollback if treatment degrades by this delta
    started_at: datetime
    status: Literal["running", "completed", "rolled_back", "promoted"]
```

**Assignment logic**: deterministic per `(run_id, agent)` via `hash(run_id + agent) % 100 < traffic_split * 100`. Ensures one run always sees the same prompt version.

**Auto-promote condition**: after `min_runs_per_arm` runs per arm:
- `treatment.primary_metric - control.primary_metric >= auto_promote_threshold` AND
- `treatment.failure_rate_24h <= control.failure_rate_24h + 0.02`
→ treatment becomes `active_version`, test status = `"promoted"`

**Auto-rollback condition** (checked after every 10 treatment invocations):
- `control.primary_metric - treatment.primary_metric >= auto_rollback_threshold` OR
- `treatment.failure_rate_24h > 0.10`
→ treatment traffic → 0%, `active_version` remains control, status = `"rolled_back"`, `DRIFT_ALERT` emitted

```python
# Default thresholds — override per agent in registry
DEFAULT_AUTO_PROMOTE_THRESHOLD: float = 0.05   # +5pp on primary metric
DEFAULT_AUTO_ROLLBACK_THRESHOLD: float = 0.05  # -5pp vs control
```

### §27.4.3 Variable Injection and Sanitization

```python
def inject_variables(template: str, variables: dict[str, str]) -> str:
    """
    Resolves {{VARIABLE_NAME}} placeholders.
    Raises PromptVariableError if required variable missing.
    Sanitizes each value: strips patterns matching INJECTION_PATTERNS before injection.
    """

INJECTION_PATTERNS: list[str] = [
    r"ignore previous instructions",
    r"disregard system prompt",
    r"<instructions>",
    r"\[SYSTEM\]",
    r"you are now",
    r"OVERRIDE:",
    r"forget everything",
]
```

---

## §27.5 Agent Specifications

### AGENT: PromptBuilder [§27.1]
RESPONSIBILITY: Assemble three-layer prompt for any agent invocation

MODEL: deterministic / TEMP: N/A / MAX_TOKENS: N/A

INPUT:
```python
agent: str
version: str                     # resolved by PromptRegistry
state_fields: dict[str, Any]     # subset of DocumentState (see §4.6)
task_overrides: dict[str, str]   # per-invocation variables
```

OUTPUT:
```python
class AssembledPrompt(TypedDict):
    system: str
    context: str
    task: str
    prompt_id: str
    resolved_variables: dict[str, str]
```

CONSTRAINTS:
- MUST resolve all `required` variables declared in prompt metadata; raise `PromptVariableError` if any missing
- MUST sanitize all variable values via `INJECTION_PATTERNS` before injection (see §22.4)
- MUST inject `ANTI_SYCOPHANCY_BLOCK` into `system` for agents: `["judge_reasoning","judge_factual","judge_style"]` ONLY
- NEVER copy `system` layer content into `context` or `task`
- ALWAYS truncate any single variable value exceeding 50,000 characters with suffix `[TRUNCATED]`

ERROR_HANDLING:
- `PromptVariableError` → log to `prompt_failure_log` with `failure_type="missing_required_field"` → raise, caller node must abort invocation
- Sanitization match found → truncate at match position, log `failure_type="instruction_ignored"`, continue
- Template file not found → `fallback: load rollback_version from PromptRegistry`

CONSUMES: `[style_exemplar, compressed_context, writer_memory, reflector_output, current_sources]` from DocumentState
PRODUCES: `[]` → DocumentState (stateless, returns assembled prompt only)

---

### AGENT: PromptRegistryManager [§27.4]
RESPONSIBILITY: Route prompt version per agent invocation and evaluate A/B test outcomes

MODEL: deterministic / TEMP: N/A / MAX_TOKENS: N/A

INPUT:
```python
agent: str
run_id: str
ab_test_config: Optional[ABTestConfig]
```

OUTPUT:
```python
class VersionResolution(TypedDict):
    agent: str
    resolved_version: str
    arm: Literal["control", "treatment", "single"]
    test_id: Optional[str]
```

CONSTRAINTS:
- MUST use deterministic assignment `hash(run_id + agent) % 100` for A/B split; NEVER random per-call
- MUST check auto-rollback condition after every 10 treatment invocations
- MUST emit `DRIFT_ALERT` event to observability stack (§23) on auto-rollback
- NEVER serve a `candidate_version` with `failure_rate_24h > 0.10`
- ALWAYS log version used to `prompt_failure_log` table for every invocation (success or failure)

ERROR_HANDLING:
- Registry load failure → serve `rollback_version` for all agents → alert ops
- A/B config invalid (e.g. `traffic_split > 1.0`) → reject config, serve control only
- `candidate_version` file missing → auto-rollback immediately, status = `"rolled_back"`

CONSUMES: `[]` from DocumentState
PRODUCES: `[]` → DocumentState (returns `VersionResolution` only)

<!-- SPEC_COMPLETE -->