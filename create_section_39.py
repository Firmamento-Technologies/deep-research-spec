#!/usr/bin/env python3
"""
create_section_39.py — Creates output/39_spec_review_loop.md
Run: python create_section_39.py
"""
from pathlib import Path

CONTENT = '''# 39. Spec Review & Self-Validation Loop

## 39.1 Rationale

The DRS production pipeline applies iterative quality loops (Writer → Jury → Reflector → Writer)
to document sections. The same principle MUST apply to the specification files themselves before
any code generation begins. Without a formal spec review loop, an AI builder receives contradictory
thresholds, missing agent specs, and unreachable graph states — producing broken implementations
that are hard to debug post-hoc.

The Spec Review Loop is a pre-production gate: code generation is BLOCKED until
`critical_issues == 0` in the review report.

---

## 39.2 Position in the Pipeline

```
[Spec Files Generated] → SPEC REVIEW AGENT → architecture_review.json
                                ↓
                        critical_issues > 0?
                           YES ↓         NO ↓
                      SPEC FIXER     CODE GENERATION
                      AGENT          (Planner → ...)
                           ↓
                      [files patched]
                           ↓
                      SPEC REVIEW AGENT  (re-run)
                           ↓
                      loop until critical_issues == 0
                      hard stop: max 3 iterations
```

This loop runs ONCE before Phase A (Pre-Flight). It is NOT part of the per-section
Writer/Jury loop. It operates on .md spec files, not on document drafts.

---

## 39.3 Spec Review Agent

```python
AGENT: SpecReviewAgent
RESPONSIBILITY: Identify logic errors, inconsistencies, missing components,
                unreachable states, and ambiguities across all spec files.

INPUT:
  - spec_files: list[str]        # all output/*.md files, concatenated and compressed
  - max_tokens_input: int        # hard cap: 200_000 tokens (skip files if exceeded,
                                 # log skipped filenames in report)

OUTPUT: ArchitectureReviewReport
  {
    "review_summary": str,       # 3 sentences max
    "issues": list[Issue],
    "missing_components": list[str],
    "positive_observations": list[str]  # max 3
  }

Issue schema:
  {
    "type": Literal["LOGIC_ERROR", "MISSING_COMPONENT",
                    "INCONSISTENCY", "UNREACHABLE_STATE", "AMBIGUITY"],
    "severity": Literal["CRITICAL", "HIGH", "MEDIUM"],
    "files_affected": list[str],
    "description": str,          # precise, implementable description
    "fix_suggestion": str        # 1-2 sentences, concrete action
  }

MODEL: anthropic/claude-sonnet-4-6
  Rationale: large context window (200k), strong architectural reasoning,
             reliable JSON output with json_repair fallback.

CONSTRAINTS:
  - Output MUST be valid JSON (use json_repair as fallback parser)
  - NEVER emit severity=CRITICAL for stylistic preferences
  - CRITICAL reserved for: broken graph edges, contradictory literal values
    used in routing logic, missing required State fields, impossible inputs
  - Save raw response to raw_response_debug.txt on JSONDecodeError

ERROR HANDLING:
  - JSONDecodeError → json_repair fallback → if still fails, raise ValueError
  - Empty response   → retry once with temperature=0 → if still empty, abort
  - Truncated output → increase MAX_TOKENS by 2000, retry once
```

---

## 39.4 Spec Fixer Agent

```python
AGENT: SpecFixerAgent
RESPONSIBILITY: Regenerate ONLY the sections of affected spec files
                that contain identified CRITICAL or HIGH issues.
                NEVER rewrite correct sections.

INPUT:
  - filename: str
  - issues: list[Issue]          # only CRITICAL and HIGH for this file
  - original_content: str        # current file content
  - source_material: str         # source/*.md ground truth

OUTPUT:
  - fixed_content: str           # patched file ending with <!-- SPEC_COMPLETE -->

MODEL: anthropic/claude-sonnet-4-6
  MAX_TOKENS: 16_000

CONSTRAINTS:
  - Fix ALL listed issues in a single call (no partial fixes)
  - Preserve file structure, headers, and correct sections verbatim
  - All thresholds must be explicit literal values (no ranges, no "TBD")
  - End output with exactly: <!-- SPEC_COMPLETE -->
  - NEVER add meta-comments like "# FIXED:" in the output

PRE-FIX:
  - Backup original file to output_backup/{filename} before overwriting

POST-FIX VALIDATION:
  - Verify <!-- SPEC_COMPLETE --> tag present (truncation guard)
  - Log WARNING if tag is missing, do NOT save truncated content

ERROR HANDLING:
  - Missing tag   → retry once with MAX_TOKENS + 2000
  - API error     → exponential backoff 2s → 4s → 8s, max 3 retries
  - Still failing → skip file, add to failed_files list, continue
```

---

## 39.5 Loop Controller

```python
LOOP: SpecReviewLoop
MAX_ITERATIONS: 3
STOP_CONDITION: critical_issues == 0

STATE:
  iteration: int                 # current loop iteration (1-based)
  review_history: list[ArchitectureReviewReport]  # one per iteration
  fixed_files: list[str]         # files patched across all iterations
  failed_files: list[str]        # files that could not be fixed

ALGORITHM:
  for iteration in range(1, MAX_ITERATIONS + 1):
    report = SpecReviewAgent.run(all_spec_files)
    review_history.append(report)

    critical = [i for i in report.issues if i.severity == "CRITICAL"]

    if len(critical) == 0:
      log(f"✅ Spec validation passed at iteration {iteration}")
      PROCEED to Phase A (Planner)
      break

    if iteration == MAX_ITERATIONS:
      log(f"❌ {len(critical)} CRITICAL issues remain after {MAX_ITERATIONS} iterations")
      BLOCK code generation
      NOTIFY human with final report
      break

    SpecFixerAgent.run(files_affected_by=critical + high_issues)

  save review_history to spec_review_history.json

CONVERGENCE EXPECTATION:
  - Iteration 1: identifies all issues
  - Iteration 2: resolves CRITICAL (target: 0 CRITICAL, some HIGH remain)
  - Iteration 3: resolves remaining HIGH (safety net)
  If CRITICAL > 0 after iteration 3: human intervention required.
```

---

## 39.6 Integration with DocumentState

```python
# Fields added to DocumentState (§4.6):
class SpecValidationState(TypedDict):
    spec_review_completed: bool           # True only when critical_issues == 0
    spec_review_iterations: int           # how many iterations were needed
    spec_critical_issues_found: int       # total CRITICAL found in iteration 1
    spec_review_history_path: str         # path to spec_review_history.json
    spec_fixed_files: list[str]           # files patched by SpecFixerAgent
    spec_failed_files: list[str]          # files that could not be auto-fixed

# Gate in preflight_node (§4.1):
def preflight_node(state: DocumentState) -> DocumentState:
    ...
    if not state["spec_review_completed"]:
        raise RuntimeError(
            "Spec validation not complete. Run python fix_specs.py first."
        )
    ...
```

---

## 39.7 Observability

```
Prometheus metrics:
  drs_spec_review_iterations_total    counter   # times loop ran
  drs_spec_critical_issues_gauge      gauge     # CRITICAL count per iteration
  drs_spec_fix_success_rate           gauge     # files fixed / files attempted

Log entries (structured JSON):
  { "event": "spec_review_started",   "iteration": 1, "files_count": 39 }
  { "event": "spec_review_complete",  "iteration": 1, "critical": 7, "high": 18 }
  { "event": "spec_fix_applied",      "file": "09_css_aggregator.md", "issues_fixed": 2 }
  { "event": "spec_validation_passed","iteration": 2, "critical": 0 }

Alert:
  - CRITICAL issues > 0 after MAX_ITERATIONS → Slack alert + block deploy
```

---

## 39.8 Files Produced

| File | Content |
|------|---------|
| `architecture_review.json` | Latest review report (overwritten each iteration) |
| `spec_review_history.json` | All iterations, for audit trail |
| `output_backup/*.md` | Pre-fix backups of all patched files |
| `raw_response_debug.txt` | Raw LLM response on JSON parse failure |

<!-- SPEC_COMPLETE -->
'''

output_path = Path("output") / "39_spec_review_loop.md"
output_path.mkdir(parents=True, exist_ok=True) if False else None
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(CONTENT, encoding="utf-8")
print(f"✅ Created: {output_path}")
print(f"   Size: {len(CONTENT):,} chars")
