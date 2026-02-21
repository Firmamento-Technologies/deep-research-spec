# §31 Pipeline Orchestrator — DRS Chain for Software Specifications

## §31.0 Rationale: Why Three Sequential DRS Instances

Single-step generation fails for software specifications because:

1. **Scope entanglement**: mixing WHAT (requirements) with HOW (architecture) with EXECUTION (agent instructions) in one pass produces documents that satisfy none of the three audiences
2. **Traceability collapse**: no mechanism enforces that every acceptance criterion maps to an implementation mechanism
3. **Jury adaptation impossibility**: JudgeF checking factual accuracy in a functional spec must verify testability of ACs, not citation validity — a fundamentally different evaluation function requiring a distinct profile

Three sequential DRS instances each run the full internal pipeline (§4-§20) with different profiles, jury configurations, and input contracts.

---

## §31.1 Three Sequential Steps

```python
from typing import Literal, TypedDict, Optional

StepName = Literal["DRS#1", "DRS#2", "DRS#3"]
StepProfile = Literal["functional_spec", "technical_spec", "software_spec"]

STEP_PROFILE_MAP: dict[StepName, StepProfile] = {
    "DRS#1": "functional_spec",
    "DRS#2": "technical_spec",
    "DRS#3": "software_spec",
}
```

| Step | Profile | Produces | Primary Audience |
|------|---------|---------|-----------------|
| DRS#1 | `functional_spec` | PRD, user stories, ACs in Given/When/Then | Product/stakeholder |
| DRS#2 | `technical_spec` | `architecture.md`, `data_schema.sql`, `api_spec.yaml`, feature files | Engineers |
| DRS#3 | `software_spec` | Multi-file directory for coding agent (see §30.5) | AI coding agent |

### §31.1.1 DRS#1 — Functional Spec

```python
class DRS1Input(TypedDict):
    product_vision: str
    user_personas: list[dict]        # {name: str, description: str, primary_need: str}
    feature_list: list[str]
    non_functional_requirements: list[str]
    constraints: list[str]
    competitive_context: Optional[str]
    max_budget_dollars: float
    target_words: int

class DRS1Output(TypedDict):
    sections: list[str]              # approved section content
    acceptance_criteria: list[dict]  # {id: str, text: str, given: str, when: str, then: str}
    decision_log: "DecisionLog"      # see §31.3
    run_report: dict
```

**JudgeF adaptation**: replaces citation-validity check with AC-testability check.

```python
class JudgeFAdaptation_DRS1(TypedDict):
    """JudgeF verdict fields specific to functional_spec profile."""
    ac_testable: bool          # can this AC be verified by an automated test?
    ac_measurable: bool        # contains explicit threshold/metric?
    technology_leaked: bool    # FAIL if framework/library named (level-1 concern only)
    ambiguous_terms: list[str] # terms requiring definition before DRS#2
```

Forbidden in DRS#1 output: framework names, library names, language-specific constructs.
Required: every feature maps to ≥1 AC with Given/When/Then structure.

### §31.1.2 DRS#2 — Technical Spec

```python
class DRS2Input(TypedDict):
    functional_spec_sections: list[str]   # DRS#1 approved output
    decision_log: "DecisionLog"           # accumulated from DRS#1
    acceptance_criteria: list[dict]       # {id, text, given, when, then}
    tech_constraints: list[str]           # non-negotiable technology constraints
    existing_codebase_description: Optional[str]
    max_budget_dollars: float
    target_words: int

class DRS2Output(TypedDict):
    sections: list[str]
    traceability_matrix: list["TraceabilityEntry"]  # see §31.5
    decision_log: "DecisionLog"           # DRS#1 log + DRS#2 additions
    run_report: dict
```

**Planner behavior**: generates outline by analyzing `functional_spec_sections`, not user topic. Outline sections correspond to architecture artifacts, not document chapters.

**CoherenceGuard adaptation**: verifies traceability matrix completeness — every AC-id from DRS#1 must appear in ≥1 `TraceabilityEntry.satisfies`. See §31.5.

### §31.1.3 DRS#3 — Software Spec

```python
class DRS3Input(TypedDict):
    technical_spec_sections: list[str]
    functional_spec_sections: list[str]
    decision_log: "DecisionLog"
    traceability_matrix: list["TraceabilityEntry"]
    target_coding_agent: Literal["claude_code", "cursor", "copilot", "generic"]
    max_budget_dollars: float

class DRS3Output(TypedDict):
    files: list["OutputFile"]     # multi-file output, see §30.5
    run_report: dict
    decision_log: "DecisionLog"   # final accumulated log
```

**JudgeS adaptation** (AI-Readability Judge):

```python
class JudgeSAdaptation_DRS3(TypedDict):
    """JudgeS verdict fields for software_spec profile."""
    no_ambiguity: bool          # zero vague terms (see §26.7 forbidden list)
    no_tbd: bool                # zero TBD/to-be-defined occurrences
    example_per_behavior: bool  # every constraint has concrete example
    consequence_stated: bool    # every rule violation has stated consequence
    agent_target_optimized: bool  # format matches target_coding_agent conventions
```

---

## §31.2 Pipeline Orchestrator

**Zero-LLM pure logic component.** No model calls. No inference.

```python
class PipelineOrchestratorConfig(TypedDict):
    mode: Literal["functional_only", "technical_only", "full_pipeline"]
    checkpoint_required: bool    # always True in production
    approval_timeout_seconds: int  # 0 = no timeout (manual approval required)
    summary_model: str           # model for inter-step summary, see §31.4

class PipelineOrchestrator:
    """
    Coordinates DRS#1 → DRS#2 → DRS#3 execution.
    Contains zero LLM calls. All decisions are deterministic state transitions.
    """

    def run(
        self,
        drs1_input: DRS1Input,
        config: PipelineOrchestratorConfig,
    ) -> PipelineResult: ...

    def _await_human_approval(self, summary: "InterStepSummary") -> ApprovalDecision: ...
    def _build_drs2_input(self, drs1_out: DRS1Output, approval: ApprovalDecision) -> DRS2Input: ...
    def _build_drs3_input(self, drs1_out: DRS1Output, drs2_out: DRS2Output) -> DRS3Input: ...
    def _checkpoint(self, step: StepName, output: dict) -> None: ...

class PipelineResult(TypedDict):
    drs1_output: DRS1Output
    drs2_output: DRS2Output
    drs3_output: DRS3Output
    total_cost_usd: float
    pipeline_decision_log: "DecisionLog"

class ApprovalDecision(TypedDict):
    approved: bool
    modifications: list[str]    # freetext user modifications applied before next step
    timestamp_iso: str
    approver_id: str
```

**Checkpoint behavior**: after each step, `_checkpoint` persists full step output to PostgreSQL (see §21). If orchestrator restarts, it resumes from last completed step using `thread_id`.

**Inter-step data flow**:
```
DRS#1.output.sections + DRS#1.decision_log
    ↓ [human approval gate]
DRS#2.input (functional_spec_sections + decision_log)
    ↓
DRS#2.output.sections + DRS#2.traceability_matrix + accumulated DecisionLog
    ↓ [human approval gate]
DRS#3.input
```

---

## §31.3 Decision Log Schema

Accumulated JSON produced by the Reflector across all iterations of a DRS step. Passed to the next DRS as read-only context.

```python
class DecisionEntry(TypedDict):
    id: str                     # "D-{step}-{seq:03d}", e.g. "D-1-007"
    step: StepName
    section_title: str
    iteration: int
    decision: str               # what was decided (1 sentence max)
    rationale: str              # why (2 sentences max)
    alternative_rejected: str   # what was considered and discarded
    judge_source: Literal["JudgeR", "JudgeF", "JudgeS", "Reflector", "Human"]
    timestamp_iso: str

class DecisionLog(TypedDict):
    entries: list[DecisionEntry]
    step_completed: StepName
    total_entries: int
```

**Reflector writes** one `DecisionEntry` per non-obvious decision (defined as: any Reflector feedback that caused scope change, structural rewrite, or AC reformulation). Trivial style corrections are NOT logged.

**Next DRS reads** the full log as additional context injected into the Writer system prompt:

```python
DECISION_LOG_INJECTION_TEMPLATE = """
## Prior Design Decisions (read-only, do not contradict without flagging)
{formatted_entries}
Any contradiction with logged decisions must be flagged as CHAIN_CONFLICT 
and escalated to human approval before proceeding.
"""
```

---

## §31.4 Inter-Step Summary

Generated by a lightweight model (not the Writer) for human approval. Target: human reads and decides in ≤5 minutes.

```python
class InterStepSummary(TypedDict):
    step_completed: StepName
    step_profile: StepProfile
    produced_artifacts: list[str]       # filenames or section titles
    word_count: int
    cost_usd: float
    iterations_per_section: list[int]
    key_decisions: list[dict]           # [{decision: str, rationale: str}], max 5 entries
    open_questions: list[str]           # max 3, questions next step must resolve
    css_avg: float
    warnings: list[str]                 # escalations, degradations, budget alerts

SUMMARY_AGENT_SPEC = {
    "model": "google/gemini-2.5-flash",
    "fallback": "meta/llama-3.3-70b-instruct",
    "temperature": 0.1,
    "max_tokens": 800,
    "input": ["approved_sections", "decision_log", "run_report"],
}
```

The summary is rendered in the Escalation Interface (§32.4) with diff-view of any user modifications before approval triggers the next step.

---

## §31.5 Traceability Matrix

CoherenceGuard in DRS#2 enforces completeness. Format:

```python
class TraceabilityEntry(TypedDict):
    ac_id: str              # e.g. "AC-007" — must exist in DRS1Output.acceptance_criteria
    satisfies: list[str]   # component/section names in technical_spec
    mechanism: str          # concrete measurable implementation detail
    verified_by: str        # test type or verification method

# Example:
EXAMPLE_ENTRY: TraceabilityEntry = {
    "ac_id": "AC-007",
    "satisfies": ["CitationVerifier", "§18.3 NLI Entailment Check"],
    "mechanism": "HTTP HEAD 3s timeout + DeBERTa NLI batch. P95 target: 4.2s",
    "verified_by": "integration_test_layer3",
}
```

**CoherenceGuard validation rule**:

```python
def validate_traceability(
    acceptance_criteria: list[dict],
    matrix: list[TraceabilityEntry],
) -> list[str]:
    """Returns list of uncovered AC ids. Empty list = PASS."""
    covered = {e["ac_id"] for e in matrix}
    all_ids = {ac["id"] for ac in acceptance_criteria}
    return list(all_ids - covered)  # any uncovered AC → HARD conflict
```

Uncovered AC → `HARD` CoherenceGuard conflict → human escalation before DRS#2 section approval.

---

## §31.6 Operative Modes

```python
OperativeMode = Literal["functional_only", "technical_only", "full_pipeline"]

MODE_BEHAVIOR: dict[OperativeMode, dict] = {
    "functional_only": {
        "steps": ["DRS#1"],
        "human_checkpoints": 0,
        "input_required": ["product_vision", "feature_list"],
    },
    "technical_only": {
        "steps": ["DRS#2"],
        "human_checkpoints": 0,
        "input_required": ["functional_spec_sections", "acceptance_criteria"],
        "note": "User supplies functional_spec_sections manually; reliability_score = 1.0",
    },
    "full_pipeline": {
        "steps": ["DRS#1", "DRS#2", "DRS#3"],
        "human_checkpoints": 2,   # after DRS#1 and after DRS#2
        "input_required": ["product_vision", "feature_list"],
    },
}
```

**Decision rule**: if `functional_spec_sections` requires >30 minutes of stakeholder review, use `full_pipeline` with `approval_timeout_seconds: 0`. Single-session contexts use `approval_timeout_seconds: 1800`.

**Chain source reliability**: when DRS#2 consumes DRS#1 output as source, `reliability_score = 1.0`. If JudgeF detects contradiction with chain source → `CHAIN_CONFLICT` flag → human approval required before proceeding (not standard FAIL routing).

```python
class ChainConflict(TypedDict):
    conflict_type: Literal["CHAIN_CONFLICT"]
    ac_id: str
    drs1_claim: str
    drs2_contradiction: str
    resolution: Literal["pending_human"]  # never auto-resolved
```

---

## §31 Agent Specification

```
AGENT: PipelineOrchestrator [§31.2]
RESPONSIBILITY: coordinate sequential DRS execution with human checkpoints
MODEL: none / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  drs1_input: DRS1Input
  config: PipelineOrchestratorConfig
OUTPUT: PipelineResult
CONSTRAINTS:
  NEVER calls any LLM directly
  MUST checkpoint after every completed step before awaiting approval
  MUST propagate full DecisionLog from step N to step N+1
  NEVER auto-approve human checkpoint regardless of CSS score
  ALWAYS validate traceability completeness before DRS#3 start
ERROR_HANDLING:
  step_failure -> checkpoint current state -> surface InterStepSummary to human -> await resume instruction
  checkpoint_write_failure -> retry 3x with exponential backoff -> abort with partial result delivery
  approval_timeout (if configured) -> pause run, notify user, await indefinitely
CONSUMES: [drs1_input, config] from caller
PRODUCES: [pipeline_result] -> caller; [checkpoint_data] -> PostgreSQL §21
```

<!-- SPEC_COMPLETE -->