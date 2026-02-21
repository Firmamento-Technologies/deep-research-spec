# 35_roadmap.md — Implementation Roadmap §35

## 35.0 Overview

```python
from typing import Literal
from dataclasses import dataclass

PhaseID = Literal["phase_1", "phase_2", "phase_3", "phase_4"]
Status = Literal["not_started", "in_progress", "complete", "blocked"]

@dataclass
class Phase:
    id: PhaseID
    name: str
    duration_weeks: int
    objective: str
    included: list[str]       # component IDs
    excluded: list[str]       # explicitly deferred
    completion_criteria: list[str]  # verifiable, not prose
    dependencies: list[PhaseID]
    smoke_suite_cmd: str
```

---

## 35.1 Phase 1 — MVP Core (4 weeks)

```python
PHASE_1 = Phase(
    id="phase_1",
    name="MVP Core",
    duration_weeks=4,
    objective="Validate Writer→Judge→Approval loop end-to-end",
    included=[
        "DocumentState (subset: topic, outline, current_draft, current_sources, "
        "budget.max_dollars, budget.spent_dollars)",
        "Pre-Flight Validator (API key check, budget cap enforcement)",
        "Budget Estimator (fixed regime: Economy, hard stop at 100% cap)",
        "Planner (manual outline input; no auto-generation)",
        "Researcher (Tavily only; max 10 sources/section)",
        "Citation Manager (APA only)",
        "Citation Verifier (HTTP 200 + DOI check; no NLI)",
        "Source Sanitizer (XML wrapping + regex injection guard Stage 1 only)",
        "Writer (claude-opus-4-5, single instance, no MoW)",
        "Judge F — single judge (perplexity/sonar, Tier1 only)",
        "Judge S — single judge (openai/gpt-4.5, Tier1 only)",
        "Aggregator (pass_F AND pass_S required; no CSS formula; binary)",
        "Publisher (Markdown output only)",
        "LangGraph graph (linear; no conditional branches except pass/fail)",
        "PostgreSQL checkpointing (AsyncPostgresSaver)",
        "Retry policy (tenacity, max_attempts=3, exponential backoff 2s→16s)",
        "Structured JSON logging (doc_id, section_idx, agent, timestamp_iso)",
        "MockLLMClient + DI architecture (see §25.10)",
        "Smoke suite Phase 1",
    ],
    excluded=[
        "MoW / Fusor (§7)", "Reflector (§12)", "Oscillation Detector (§13)",
        "Context Compressor (§14)", "Coherence Guard (§15)", "Writer Memory (§16)",
        "Panel Discussion (§11)", "Minority Veto (§10)", "CSS formula (§9.1)",
        "Judge R (§8.1)", "Style Linter / Style Fixer (§5.9, §5.10)",
        "Style Calibration Gate (§3B)", "NLI entailment (§18.3)",
        "Post-Draft Research Analyzer (§5.11)", "Span Editor (§5.12)",
        "Academic connectors: CrossRef, Semantic Scholar, arXiv (§17.1)",
        "DOCX/PDF/LaTeX output (§30.2)", "Web UI (§32)", "Celery queue (§33.4)",
        "OpenTelemetry / Prometheus / Grafana (§23)", "Run Companion (§6)",
        "DRS Chain / Pipeline Orchestrator (§31)", "Security audit",
        "Source Diversity Analyzer (§17.8)", "Micro-search Judge F (§8.2.1)",
    ],
    completion_criteria=[
        "smoke_suite phase_1 exits 0 on CI",
        "Writer produces JSON-parseable output on 5 sample topics",
        "Budget cap enforced: run aborts before exceeding max_budget_dollars",
        "Approved section persists in PostgreSQL after simulated worker kill + restart",
        "Retry triggers on mocked 429 (verified via MockLLMClient call log)",
        "End-to-end pipeline on sample topic completes in <15 min wall time",
        "Zero direct openai/requests imports in src/agents/* (linted via ruff)",
    ],
    dependencies=[],
    smoke_suite_cmd="make test-phase1",
)
```

**Max iterations per section:** 1 (hard-coded, no Reflector loop).  
**Budget cap:** fixed `max_budget_dollars` from YAML; no adaptive regime switching.

---

## 35.2 Phase 2 — Multi-Judge (4 weeks)

```python
PHASE_2 = Phase(
    id="phase_2",
    name="Multi-Judge",
    duration_weeks=4,
    objective="Validate multi-model consensus improves quality vs single-judge",
    included=[
        "Jury 3×3 full (Judge R: §8.1, Judge F: §8.2, Judge S: §8.3)",
        "Cascading economic tiers per jury (§8.5)",
        "CSS formula CSS_content + CSS_style (§9.1)",
        "Minority Veto L1 + L2 (§10.1, §10.2)",
        "Rogue Judge Detector (§10.3)",
        "Aggregator routing table full (§9.4)",
        "Reflector (o3, structured feedback §12.1, scope SURGICAL/PARTIAL/FULL §12.2)",
        "Oscillation Detector: CSS + Semantic types (§13.1, §13.2)",
        "Panel Discussion max 2 rounds (§11)",
        "Budget Controller adaptive regime: Economy/Balanced/Premium (§19.2)",
        "Budget real-time tracker WARN 70% / ALERT 90% / HARD STOP 100% (§19.3)",
        "PostgreSQL checkpointing full (resume from last approved section)",
        "Redis cache: sources TTL=24h, citation verdicts TTL=30d (§21.3)",
        "Style Linter L1 + L2 regex deterministici (§5.9)",
        "Content Gate / Style Pass separation (§9.3)",
        "Smoke suite Phase 2",
    ],
    excluded=[
        "MoW / Fusor (§7)", "Style Calibration Gate (§3B)",
        "Style Fixer (§5.10)", "Context Compressor (§14)",
        "Coherence Guard (§15)", "Writer Memory (§16)",
        "NLI entailment (§18.3)", "Post-Draft Research Analyzer (§5.11)",
        "Span Editor (§5.12)", "Academic connectors (§17.1)",
        "Micro-search Judge F (§8.2.1)", "DOCX/PDF output",
        "Web UI (§32)", "Celery (§33.4)", "OpenTelemetry (§23.1)",
        "Run Companion (§6)", "DRS Chain (§31)",
    ],
    completion_criteria=[
        "smoke_suite phase_2 exits 0",
        "Oscillation detected on synthetic oscillating input within oscillation_window=4 iter",
        "Minority Veto blocks section when fabricated_source veto_category set (mocked judge)",
        "Resume from crash: kill worker after section 2 approval; restart recovers section 3",
        "CSS >= css_approval_threshold on >=8/10 golden set sections",
        "Budget regime switches from Balanced→Economy at 70% spend threshold (integration test)",
        "Rogue judge alert fires when mock judge disagrees on 3+ consecutive sections",
        "Panel Discussion log stored in PostgreSQL after CSS_content < 0.50",
    ],
    dependencies=["phase_1"],
    smoke_suite_cmd="make test-phase2",
)
```

---

## 35.3 Phase 3 — Advanced Features (6 weeks)

```python
PHASE_3 = Phase(
    id="phase_3",
    name="Advanced Features",
    duration_weeks=6,
    objective="Complete agent set; production-quality output formats",
    included=[
        "Planner auto-generation (gemini-2.5-pro, §5.1)",
        "Researcher full: CrossRef + Semantic Scholar + arXiv (§17.1)",
        "Source Diversity Analyzer (§17.8; max 40% same publisher)",
        "Citation Verifier NLI: DeBERTa entailment + temporal + quantitative (§18.3)",
        "Source Synthesizer (§5.6; ≥60% compression, max 2 sources bypass)",
        "Context Compressor (qwen3-7b; verbatim/summary/extract by position §14.1)",
        "Coherence Guard SOFT + HARD levels (§15.1)",
        "Style Calibration Gate (§3B; Style Exemplar saved to State)",
        "Style Fixer (claude-sonnet-4, max 2 iter/section §5.10)",
        "Writer Memory (§16; forbidden pattern tracking, glossary, citation tendency)",
        "MoW: 3× Writer proposer W-A/B/C parallel (§7.2)",
        "Fusor Agent (o3, §5.13; first iteration only)",
        "Post-Draft Research Analyzer (gemini-2.5-flash, §5.11; first iter only)",
        "Span Editor (claude-sonnet-4, §5.12; disabled iter>=3)",
        "Diff Merger deterministic (§5.12)",
        "Micro-search Judge F (§8.2.1; Balanced=low-confidence-only, Premium=all)",
        "Judge Calibration + Normalization (§8.4)",
        "Whack-a-Mole Oscillation type (§13.3)",
        "DOCX output (python-docx template §30.2)",
        "PDF output (weasyprint §30.2)",
        "JSON structured output (§30.2)",
        "Hallucination Rate Tracker per model (§18.5; alert >5% on 10+ runs)",
        "PII detection: regex + spaCy NER (§22.3)",
        "Privacy Mode: standard / enhanced / strict / self_hosted (§22.5)",
        "Post-Flight QA: Contradiction Detector + Format Validator (§15.2, §15.3)",
        "Smoke suite Phase 3",
    ],
    excluded=[
        "Web UI Next.js (§32)", "Celery queue (§33.4)",
        "OpenTelemetry full stack (§23)", "Run Companion (§6)",
        "DRS Chain / Pipeline Orchestrator (§31)",
        "Security audit (GDPR, penetration test)",
        "Load testing", "Plugin system (§37)",
        "Multi-Document Mode (§37.4)", "KEDA autoscaling",
    ],
    completion_criteria=[
        "smoke_suite phase_3 exits 0",
        "Style Exemplar saved to DocumentState.style_exemplar after Gate approval",
        "Context Compressor reduces token count by >=60% on section 6+ (measured by MockLLMClient)",
        "Coherence Guard detects synthetic hard contradiction between sections 1 and 4",
        "MoW: 3 parallel Writer calls complete; Fusor output contains elements from >=2 proposers (§36.5 KPI: fusor_integration_rate >0.60)",
        "DeBERTa NLI entailment returns CONTRADICTION label on mocked mismatched claim/source pair",
        "Style Fixer corrects L1 violation without altering numeric facts (unit test §5.10)",
        "Hallucination rate alert fires when mock model exceeds 5% on 10 runs",
        "DOCX and PDF generated for 5 golden set documents; Format Validator passes",
        "PII placeholder substitution verified: email pattern replaced before LLM call",
    ],
    dependencies=["phase_2"],
    smoke_suite_cmd="make test-phase3",
)
```

---

## 35.4 Phase 4 — Production (8 weeks)

```python
PHASE_4 = Phase(
    id="phase_4",
    name="Production",
    duration_weeks=8,
    objective="System ready for real users at 1000 jobs/day",
    included=[
        "Web UI Next.js: wizard, outline editor, progress dashboard, escalation UI (§32)",
        "Celery + Redis job queue (§33.4; KEDA autoscaling min=1 max=20 workers)",
        "OpenTelemetry distributed tracing (§23.1; span per agent call)",
        "Prometheus metrics (§23.2; all counters/gauges/histograms defined)",
        "Grafana dashboards: Operations, Quality, Cost, Infrastructure (§23.3)",
        "AlertManager rules: all 8 alert conditions (§23.7)",
        "Loki structured log aggregation (§23.6)",
        "Run Companion (gemini-2.5-pro, <3s response, §6)",
        "Pipeline Orchestrator DRS Chain: functional→technical→software_spec (§31)",
        "Decision Log accumulation between DRS steps (§31.3)",
        "Traceability Matrix enforcement in DRS#2 Coherence Guard (§31.5)",
        "Security audit: GDPR compliance, OWASP top-10, penetration test",
        "GDPR Right to Deletion endpoint + Deletion Certificate (§22.6)",
        "Audit log append-only table (§22.6)",
        "Encryption at rest AES-256 + TLS 1.3 in transit (§22.2)",
        "OAuth2 + JWT authentication (§22.1)",
        "Rate limiting per API key (60 req/min) + per IP (10 req/min unauth) (§22.4)",
        "Plugin system: SourceConnector + Judge + OutputFormatter interfaces (§37)",
        "Multi-Document Mode (§37.4)",
        "Chaos testing suite (§25.6; 7 scenarios)",
        "Load testing: 1000 jobs/day sustained; P95 API latency <200ms",
        "Kubernetes manifests + Docker Compose prod (§34)",
        "Feedback Collector (§5.20; rating, highlight, blacklist, training loop)",
        "LaTeX + HTML output formats (§30.2)",
        "Smoke suite Phase 4",
    ],
    excluded=[
        "Fine-tuning of judge models",
        "Self-hosted model training",
        "Billing / payment integration (out of scope)",
    ],
    completion_criteria=[
        "smoke_suite phase_4 exits 0",
        "Run Companion responds in <3s on 10 consecutive queries (measured, not estimated)",
        "DRS chain completes functional→technical pipeline on 1 test topic with human approval checkpoint",
        "Grafana alert fires within 60s of simulated oscillation injection",
        "Load test: 50 concurrent runs sustained for 30 min; zero data loss; P95 API <200ms",
        "Deletion Certificate generated for test user; all data removed from PostgreSQL + S3 (verified)",
        "Security audit: zero critical/high CVEs in dependency scan; zero OWASP critical findings",
        "KEDA scales workers from 1→5 when queue length >8 (integration test)",
        "DQS >= 0.75 on all 10 golden set documents (§25.4)",
        "SLO: run completion rate >= 99.0% over 72h chaos test window (§23.6)",
    ],
    dependencies=["phase_3"],
    smoke_suite_cmd="make test-phase4",
)
```

---

## 35.5 Dependency Diagram

```
Phase 1 ──────────────────────────────────────────────────────────┐
│ Writer·JudgeF·JudgeS·Aggregator(binary)·Publisher(MD)           │
│ Budget cap fixed · PostgreSQL checkpoint · Retry · DI arch      │
└──────────────────────────────────────────────────────────────────┘
        │ completes
        ▼
Phase 2 ──────────────────────────────────────────────────────────┐
│ Jury 3×3 · CSS formula · Minority Veto · Reflector              │
│ Panel Discussion · Oscillation CSS+Semantic · Budget regimes    │
│ Style Linter · Content Gate / Style Pass separation             │
└──────────────────────────────────────────────────────────────────┘
        │ completes
        ▼
Phase 3 ──────────────────────────────────────────────────────────┐
│ Planner auto · Academic connectors · NLI entailment             │
│ Context Compressor · Coherence Guard · Style Gate + Fixer       │
│ MoW + Fusor · Post-Draft Analyzer · Span Editor                 │
│ DOCX/PDF/JSON · PII detection · Privacy Mode                    │
└──────────────────────────────────────────────────────────────────┘
        │ completes
        ▼
Phase 4 ──────────────────────────────────────────────────────────┐
│ Web UI Next.js · Celery queue · OTel + Prometheus + Grafana     │
│ Run Companion · DRS Chain orchestrator · Security audit         │
│ Load test 1000 jobs/day · GDPR · Plugin system · KEDA           │
└──────────────────────────────────────────────────────────────────┘
```

**Sequential constraint:** Phase N+1 MUST NOT begin until `smoke_suite phase_N` exits 0 on CI main branch.

---

## 35.6 Time Estimate Summary

| Phase | Duration | Cumulative | Gate |
|-------|----------|------------|------|
| 1 — MVP Core | 4 weeks | 4 weeks | `make test-phase1` passes |
| 2 — Multi-Judge | 4 weeks | 8 weeks | `make test-phase2` passes |
| 3 — Advanced | 6 weeks | 14 weeks | `make test-phase3` passes |
| 4 — Production | 8 weeks | 22 weeks | `make test-phase4` passes + security audit |

**Total:** 22 weeks (~5.5 months) from zero to production-ready.

---

## 35.7 Cross-Phase Component Index

Components not introduced in Phase 1 but referenced by Phase 1 code (DI stubs required):

```python
STUB_REQUIRED_IN_PHASE_1: dict[str, str] = {
    "Reflector": "raises NotImplementedError; §12",
    "ContextCompressor": "returns input unchanged; §14",
    "StyleFixer": "raises NotImplementedError; §5.10",
    "Fusor": "raises NotImplementedError; §5.13",
    "OscillationDetector": "always returns False; §13",
    "CoherenceGuard": "always returns no_conflict; §15",
    "RunCompanion": "raises NotImplementedError; §6",
}
```

Stubs ensure DI wiring compiles from Phase 1; real implementations injected in later phases.

<!-- SPEC_COMPLETE -->