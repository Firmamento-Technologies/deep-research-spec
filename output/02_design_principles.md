# 02_design_principles.md

## Overview

11 architectural principles governing every implementation decision in DRS. Each principle defines a NAME, binding contract, and antipattern. Violations are bugs, not style choices.

---

## Principle Table

| ID | Name | One-Line Definition |
|----|------|---------------------|
| §2.1 | Budget-First | Economic constraint is inviolable; system never exceeds `max_budget_dollars` |
| §2.2 | Section-Granularity | Each section runs an isolated loop; approved sections are immutable |
| §2.3 | Epistemic-Diversity | Jury uses architecturally decorrelated model families |
| §2.4 | Minority-Veto | One L1 veto or unanimous mini-jury failure blocks regardless of CSS |
| §2.5 | Economic-Cascading | Cheap tier first; premium models only on jury disagreement |
| §2.6 | Accumulated-Context | Context Compressor runs after every approval; context never grows unbounded |
| §2.7 | Human-in-the-Loop | Human intervention at exactly 2 scheduled checkpoints; emergency interruptions are distinct unplanned events |
| §2.8 | Observability | Logging, tracing, metrics emitted by design; never retrofitted |
| §2.9 | Zero-Downtime | Every API call has retry + circuit breaker + fallback chain |
| §2.10 | GDPR-Privacy | PII detection and data minimization before any external provider call |
| §2.11 | Testability-First | Every component injectable; no agent imports external clients directly |

---

## §2.1 Budget-First

```python
CONSTRAINT: Literal["MUST_NOT"] = "MUST_NOT"
# System MUST NOT execute any LLM call if:
# pre_run_estimate > max_budget_dollars * 0.80  →  block, propose alternatives
# accumulated_cost >= max_budget_dollars * 0.90 →  activate fallback regime
# accumulated_cost >= max_budget_dollars * 1.00 →  hard stop, emit partial document

# Budget Estimator runs BEFORE Planner output is consumed.
# BudgetController node runs BEFORE every Writer/Jury call.
```

**VIOLATED_BY:** Executing Writer on section N+1 without checking `accumulated_cost`; using `max_iterations` as convergence criterion instead of CSS.

---

## §2.2 Section-Granularity

```python
CONSTRAINT = """
MUST: Apply full loop (Researcher→Writer→Jury→Reflector) per section, not per document.
MUST: Mark section as approved_at timestamp in PostgreSQL Store before advancing current_section_idx.
MUST NOT: Re-process any section with section.status == 'approved' in subsequent iterations.
MUST NOT: Feed unapproved section content to Writer of section N+1.
"""
```

**VIOLATED_BY:** Running Writer on entire document draft; allowing Reflector to modify `approved_sections[i]` content.

---

## §2.3 Epistemic-Diversity

```python
from typing import Literal

JuryFamily = Literal["anthropic", "openai", "google", "mistral", "meta", "deepseek", "perplexity"]

CONSTRAINT = """
MUST: Each mini-jury slot uses a model from a DIFFERENT provider family.
MUST: No two slots within the same mini-jury share JuryFamily.
MUST NOT: Use the same model in Writer slot AND any Judge slot in same run.
"""

# Valid example (Jury Factual):
# slot_F1: perplexity/sonar     → family: perplexity
# slot_F2: google/gemini-flash  → family: google
# slot_F3: openai/gpt-4o-search → family: openai
```

**VIOLATED_BY:** Populating all 3 Reasoning slots with OpenAI models; using `claude-opus-4-5` as both Writer and Judge S1.

---

## §2.4 Minority-Veto

```python
VetoCategory = Literal["fabricated_source", "factual_error", "logical_contradiction", "plagiarism"]

CONSTRAINT = """
L1 VETO: Single judge emitting veto_category != None → section BLOCKED, CSS ignored.
L2 VETO: All 3 judges in one mini-jury return pass_fail=False → section BLOCKED, CSS ignored.
Rogue Judge: disagreement_rate > 0.70 on 3+ consecutive sections → emit ROGUE_JUDGE alert.
MUST NOT: Override L1/L2 veto by CSS threshold logic.
MUST NOT: Allow veto_category = None on FAIL verdict (veto and fail are distinct).
"""
```

**VIOLATED_BY:** Routing to `approved` branch when `CSS >= threshold` even if `veto_category` is set; treating L2 veto as equivalent to `FAIL` without blocking.

---

## §2.5 Economic-Cascading

```python
CONSTRAINT = """
MUST: Call tier1 models for all jury slots first (parallel async).
MUST: Proceed to tier2/tier3 ONLY if tier1 produces split verdict (not unanimous).
MUST NOT: Call premium tier models when tier1 is unanimous PASS or unanimous FAIL.
Expected cost reduction: 0.60-0.70 vs calling all tiers unconditionally.

JURY SIZE RULE:
  When jury_size < 3 (e.g. jury_size=1 in Economy regime or jury_size=2 in Balanced
  regime as set by BudgetController), cascading is DISABLED entirely.
  Tier1 results are final — tier2 and tier3 are never called regardless of verdict.
  CSS is computed on the available judges only (jury_size judges, not 3).
  Rationale: with fewer than 3 judges there is no well-defined 'split' that warrants
  escalation; the unanimous/split distinction requires at least 3 voters.
"""

# Tier mapping: see §19 (BudgetController YAML section)
# Cascading applies per mini-jury independently.
# See also §8.5 and §19.5 for per-regime jury_size values.
```

**VIOLATED_BY:** Always calling all 3 tiers sequentially; calling tier3 model when tier1+tier2 agree; attempting cascading when `jury_size < 3`.

---

## §2.6 Accumulated-Context

```python
CONSTRAINT = """
MUST: Invoke Context Compressor AFTER each section approval, BEFORE advancing to section N+1.
MUST: Apply compression by position using DISTANCE, defined as:
        distance = current_section_idx - approved_section_idx
      where current_section_idx is the 0-based index of the section NOW BEING WRITTEN,
      and approved_section_idx is the 0-based index of the already-approved section.
      The immediately preceding approved section has distance=1 (NOT distance=0).

  Compression tiers by distance:
  - distance 1 or 2  (i.e. the last 2 approved sections): verbatim
  - distance 3 to 5  (i.e. sections[-3] to sections[-5]):  structured summary
                      (80-120 words each)
  - distance >= 6    (i.e. sections[:-5]):                  thematic extract
                      (key claims + citations only)

MUST NOT: Pass full approved section text for sections at distance > 5 to Writer.
MUST: Preserve load-bearing claims (referenced by outline of future sections) verbatim
      regardless of distance.
Model: qwen/qwen3-7b (lightweight extraction task).

NOTE ON INDEXING: distance is always >= 1 for any approved section relative to the
section being written. distance=0 would mean a section compared with itself and is
never a valid input to the compression logic.
"""
```

**VIOLATED_BY:** Concatenating all approved sections as-is into Writer context; skipping Compressor invocation for short documents; treating the immediately preceding section as distance=0.

---

## §2.7 Human-in-the-Loop

```python
HumanCheckpoint = Literal["outline_approval", "escalation_intervention"]

CONSTRAINT = """
SCHEDULED CHECKPOINTS (exactly 2):
  The system has exactly 2 planned, predictable checkpoints where human approval
  is part of the normal workflow:
  1. outline_approval: after Planner output, before first Researcher call
  2. escalation_intervention: after Oscillation Detector triggers or FULL scope Reflector

MUST NOT: Add additional SCHEDULED blocking human checkpoints outside these 2.
MUST NOT: Proceed past outline_approval without explicit human confirmation.
MUST: Provide structured escalation interface (CSS history, draft log, action options).

EMERGENCY await_human CALLS (unplanned interruptions, distinct from the 2 above):
  The following are unplanned system-safety interruptions that invoke await_human
  outside the 2 scheduled checkpoints. They are NOT violations of this principle;
  they are circuit-breaker events that must never be suppressed:
  - CoherenceGuard HARD conflict (§15.1): cross-section factual contradiction
    detected before section approval → await_human with diff visualization.
  - Budget anomaly (§19): single section exceeds budget_per_section_max threshold
    → await_human with cost breakdown and continue/skip/abort options.
  - Panel Discussion exhaustion (§11.3): CSS still < css_panel_threshold after
    max panel rounds → escalate_human → await_human.
  - Oscillation hard-limit reached (§13): draft oscillation unresolved after
    hard_limit iterations → escalate_human → await_human.

  These emergency calls are unplanned interruptions distinct from the 2 scheduled
  checkpoints. They arise from runtime anomalies and cannot be predicted at run start.
  Implementation MUST NOT conflate them with the scheduled checkpoint count.
"""
```

**VIOLATED_BY:** Auto-approving outline when `quality_preset == "economy"`; adding per-section human approval gates; suppressing emergency await_human calls in the name of enforcing the '2 checkpoint' rule.

---

## §2.8 Observability

```python
CONSTRAINT = """
MUST: Every LLM call emits OpenTelemetry span with attributes:
  {run_id, section_idx, iteration, agent, model, tokens_in, tokens_out, cost_usd, latency_ms, outcome}
MUST: Every log line is structured JSON with fields:
  {timestamp_iso, level, run_id, section_idx, iteration, agent, event, trace_id}
MUST NOT: Use unstructured string logging (print, f-string log) in production code.
MUST: Emit Prometheus counter drs_llm_calls_total{agent, model, outcome} on every call.
MUST NOT: Add observability as post-hoc wrapper; instrument at call site.
"""
```

**VIOLATED_BY:** `logger.info(f"Writer done for section {i}")`; adding Prometheus metrics only to FastAPI routes, not agent nodes.

---

## §2.9 Zero-Downtime

```python
CONSTRAINT = """
MUST: Every external API call (LLM, search, DOI) wrapped with:
  - Retry: exponential backoff 2s→4s→8s, max 3 attempts (tenacity)
  - Circuit Breaker: OPEN after 3 failures in 60s, HALF-OPEN after 300s
  - Fallback chain: per-slot fallback list in YAML, tried in order after circuit opens
MUST: Persist LangGraph checkpoint to PostgreSQL after every super-step.
MUST NOT: Let a single API 429/500 abort the run.
MUST: Resume from last checkpoint on process restart via thread_id.
Graceful degradation: jury operable with 1/3 judges; emit JURY_DEGRADED warning.
"""
```

**VIOLATED_BY:** Raising unhandled `httpx.TimeoutException` in Researcher node; not saving thread_id until after first iteration completes.

---

## §2.10 GDPR-Privacy

```python
PrivacyMode = Literal["standard", "enhanced", "strict", "self_hosted"]

CONSTRAINT = """
MUST: Run PII detection (regex + spaCy NER) on every uploaded_source and web-scraped content
      BEFORE content enters DocumentState or is sent to any LLM provider.
MUST: Replace PII with typed placeholders: [EMAIL_001], [PERSON_001], etc.
MUST NOT: Send uploaded_sources to cloud LLM providers when privacy_mode != 'standard'.
MUST: Delete PII mapping table at run completion (privacy_mode in ['strict', 'self_hosted']).
MUST: Expose DELETE /users/{user_id}/data endpoint (GDPR Art. 17).
Data retention defaults: draft_sections=30d, approved_sections=365d, logs=90d.
"""
```

**VIOLATED_BY:** Passing raw uploaded PDF text directly to Writer prompt; logging section content (not just metadata) in structured JSON.

---

## §2.11 Testability-First

```python
CONSTRAINT = """
MUST: Every agent class accepts LLMClient, SearchClient, DBClient as constructor parameters.
MUST NOT: Import openai, anthropic, httpx, requests directly in src/agents/*.
MUST: MockLLMClient substitutable for real client with zero code change in agent logic.
MUST: Each MVP phase has a smoke suite runnable via 'make test-phaseN' completing in <120s.
MUST NOT: Advance to phase N+1 until phase N smoke suite passes 100%.
MUST: Every conditional edge in LangGraph graph testable with MockLLMClient at zero API cost.
"""

# Dependency injection pattern (mandatory for all agents):
# class WriterAgent:
#     def __init__(self, llm: LLMClient, db: DBClient): ...
#     async def run(self, state: DocumentState) -> DocumentState: ...
```

**VIOLATED_BY:** `client = AsyncOpenAI(api_key=os.environ["OPENROUTER_API_KEY"])` inside agent `run()` method; smoke suite requiring live API keys.

---

## Principle Enforcement Matrix

```python
# Maps principle → component responsible for enforcement
ENFORCEMENT: dict[str, list[str]] = {
    "Budget-First":         ["BudgetEstimatorNode", "BudgetControllerNode"],
    "Section-Granularity":  ["SectionCheckpointNode", "RouteNextSection"],
    "Epistemic-Diversity":  ["ConfigValidator (Pydantic)", "PreflightNode"],
    "Minority-Veto":        ["AggregatorNode"],
    "Economic-Cascading":   ["JuryNode (per mini-jury)"],
    "Accumulated-Context":  ["ContextCompressorNode"],
    "Human-in-the-Loop":    ["AwaitOutlineNode", "AwaitHumanNode"],
    "Observability":        ["LLMClient wrapper", "every agent node"],
    "Zero-Downtime":        ["LLMClient (tenacity)", "CircuitBreaker", "CheckpointSaver"],
    "GDPR-Privacy":         ["SourceSanitizerNode", "PIIDetector"],
    "Testability-First":    ["All Agent constructors", "CI smoke suite"],
}
```

<!-- SPEC_COMPLETE -->