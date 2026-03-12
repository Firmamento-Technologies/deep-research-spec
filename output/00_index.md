# 00_index.md — Deep Research System v3.0

**Version:** 3.0 | **Date:** 2026-02-15 | **Status:** SPEC_COMPLETE

---

## Executive Summary

The Deep Research System (DRS) is a multi-agent AI pipeline that produces long-form research documents (5k–50k words) with verifiable citations, controlled style, and certified quality. It operates as a LangGraph state machine executing three sequential phases: (A) outline negotiation with human approval, (B) section-by-section production loop, (C) post-flight QA and multi-format export.

Core architecture: a **Mixture-of-Writers** produces parallel drafts per section; a **3×3 heterogeneous jury** (Reasoning/Factual/Style mini-juries, each with 3 decorrelated models) evaluates quality via the **Consensus Strength Score (CSS)**; a **Minority Veto** blocks on critical errors regardless of CSS; a **Reflector** synthesizes structured feedback; a **Budget Controller** enforces hard economic limits. Approved sections are immutable and stored permanently in PostgreSQL. The system self-checkpoints after every section, supports full crash recovery via `thread_id`, and exposes SSE streaming for real-time progress. Output formats: DOCX, PDF, Markdown, LaTeX, HTML, JSON. A **Run Companion** agent provides conversational access to system state throughout execution. A **Pipeline Orchestrator** chains three DRS instances (functional → technical → software spec) for software specification generation.

---

## File Index

| # | File | Description | Link |
|---|------|-------------|------|
| 00 | Index | This file: navigation, reading paths, dependency graph | [00_index.md](./00_index.md) |
| 01 | Vision & Objectives | System purpose, use cases, user types, fundamental constraints | [01_vision.md](./01_vision.md) |
| 02 | Design Principles | 12 architectural principles governing all implementation decisions | [02_design_principles.md](./02_design_principles.md) |
| 03 | System Inputs | Complete input spec: required/optional fields, YAML advanced params | [03_inputs.md](./03_inputs.md) |
| 03B | Style Calibration Gate | Pre-run style exemplar generation and ruleset freezing | [03b_style_calibration.md](./03b_style_calibration.md) |
| 04 | System Architecture | Phase A→D flow, LangGraph graph definition, DocumentState TypedDict | [04_architecture.md](./04_architecture.md) |
| 05 | Production Agents | All 20 agents: AGENT templates with INPUT/OUTPUT/MODEL/CONSTRAINTS | [05_agents.md](./05_agents.md) |
| 06 | Run Companion | Conversational agent with read access to full state and safe mutations | [06_run_companion.md](./06_run_companion.md) |
| 07 | Mixture-of-Writers & Fusor | MoW activation, 3 proposer writers, Fusor synthesis, budget impact | [07_mow_fusor.md](./07_mow_fusor.md) |
| 08 | Jury System | 3 mini-juries, cascading tiers, verdict format, jury calibration | [08_jury.md](./08_jury.md) |
| 09 | Aggregator & CSS Formula | CSS_content/CSS_style formulas, Content Gate, Style Pass, routing table | [09_aggregator_css.md](./09_aggregator_css.md) |
| 10 | Minority Veto | L1 individual veto, L2 unanimous mini-jury veto, Rogue Judge Detector | [10_minority_veto.md](./10_minority_veto.md) |
| 11 | Panel Discussion | Activation condition, anonymized deliberation, max rounds, escalation | [11_panel_discussion.md](./11_panel_discussion.md) |
| 12 | Reflector | Structured feedback format, SURGICAL/PARTIAL/FULL scope, conflict rules | [12_reflector.md](./12_reflector.md) |
| 13 | Oscillation Detector | CSS/semantic/whack-a-mole detection, thresholds, human escalation UI | [13_oscillation_detector.md](./13_oscillation_detector.md) |
| 14 | Context Compressor | Position-based compression rules, load-bearing claims, invocation timing | [14_context_compressor.md](./14_context_compressor.md) |
| 15 | Coherence Guard & Post-QA | Cross-section contradiction detection, SOFT/HARD levels, format validation | [15_coherence_guard.md](./15_coherence_guard.md) |
| 16 | Writer Memory | Recurring error tracking, technical glossary, citation tendency, drift | [16_writer_memory.md](./16_writer_memory.md) |
| 17 | Source Layer | Connectors (academic/institutional/web/social/upload), SourceRanker, diversity | [17_sources.md](./17_sources.md) |
| 18 | Citation Management | Citation map, Harvard/APA/Chicago/Vancouver formatting, NLI entailment, ISBN | [18_citations.md](./18_citations.md) |
| 19 | Budget Controller | Pre-run estimator, adaptive regimes, real-time tracker, cascading strategy | [19_budget.md](./19_budget.md) |
| 20 | Error Handling & Resilience | Full error matrix, retry policy, circuit breaker, fallback chains | [20_error_handling.md](./20_error_handling.md) |
| 21 | Persistence & Checkpointing | PostgreSQL schema, AsyncPostgresSaver, Redis cache, crash recovery | [21_persistence.md](./21_persistence.md) |
| 22 | Security & Privacy | Auth, encryption, PII detection, prompt injection guard, GDPR compliance | [22_security.md](./22_security.md) |
| 23 | Observability Stack | OpenTelemetry tracing, Prometheus metrics, Grafana dashboards, alerting | [23_observability.md](./23_observability.md) |
| 24 | REST API & Integration | Async-first endpoints, SSE streaming, human-in-the-loop endpoints, webhooks | [24_api.md](./24_api.md) |
| 25 | Testing Framework | Golden dataset, unit/integration/e2e layers, chaos testing, DQS formula | [25_testing.md](./25_testing.md) |
| 26 | Style Profiles & L1/L2/L3 | 3-level enforcement, 7 preset profiles, universal forbidden patterns, i18n | [26_style_profiles.md](./26_style_profiles.md) |
| 27 | Prompt Layer | Prompt structure, anti-sycophancy, versioning, A/B testing, CI/CD pipeline | [27_prompts.md](./27_prompts.md) |
| 28 | LLM Model Assignment | Agent→model table with fallback chains, task-fit rationale, pricing dict | [28_models.md](./28_models.md) |
| 29 | YAML Configuration | Complete config schema with Pydantic validation, all parameters | [29_config.md](./29_config.md) |
| 30 | System Output | Document properties, 6 output formats, Publisher, Run Report, Feedback Collector | [30_output.md](./30_output.md) |
| 31 | Pipeline Orchestrator | DRS chain (functional→technical→software), Decision Log, Traceability Matrix | [31_pipeline_orchestrator.md](./31_pipeline_orchestrator.md) |
| 32 | User Interface & HITL | Wizard, outline editor, dashboard, escalation interface, section versioning | [32_ui_hitl.md](./32_ui_hitl.md) |
| 33 | Technology Stack | Full tech table with rationale, pyproject.toml dependencies | [33_tech_stack.md](./33_tech_stack.md) |
| 34 | Deployment & Infrastructure | Environments, rate limiting, scalability, KEDA, directory tree | [34_deployment.md](./34_deployment.md) |
| 35 | MVP Roadmap | 4-phase incremental plan with scope, smoke suites, success criteria | [35_roadmap.md](./35_roadmap.md) |
| 36 | KPIs & Success Metrics | Quantitative targets: quality, efficiency, reliability, convergence, MoW | [36_kpis.md](./36_kpis.md) |
| 37 | Extensibility & Plugins | SourceConnector/Judge/OutputFormatter interfaces, Multi-Document Mode | [37_extensibility.md](./37_extensibility.md) |
| 38 | AI Builder Rules | Imperative non-negotiable implementation rules for the coding agent | [38_ai_builder_rules.md](./38_ai_builder_rules.md) |
| 39 | Spec Review & Self-Validation Loop | Pre-production validation gate: SpecReviewAgent, SpecFixerAgent, Loop Controller (max 3 iter) — blocks code generation until `critical_issues == 0` | [39_spec_review_loop.md](./39_spec_review_loop.md) |

---

## Reading Paths

### Path 1: Implement from Scratch
```
§39 → §33 → §04 → §05 → §38 → §21 → §19 → §20 → §28 → §29 →
§26 → §27 → §08 → §09 → §10 → §07 → §12 → §13 → §14 →
§15 → §16 → §17 → §18 → §06 → §11 → §03 → §03B → §01 →
§02 → §22 → §23 → §24 → §25 → §30 → §31 → §32 → §34 →
§35 → §36 → §37
```
**Start with §39**: run the Spec Review Loop and resolve all CRITICAL issues before any implementation. Then stack (§33) and architecture (§04). Read §38 before writing any agent module. §26 defines L1/L2/L3 enforcement consumed by §05 Style Linter — read §26 before §27.

### Path 2: Integrate a Single Component
Navigate directly to the section for the target component. Every agent spec in §05 lists `CONSUMES` and `PRODUCES` fields pointing to the exact `DocumentState` fields and their source sections.

```python
# Cross-reference pattern used throughout specs:
# CONSUMES: [current_sources] from §17, [style_exemplar] from §03B
# PRODUCES: [current_draft] -> DocumentState (see §04.6)
```

### Path 3: Evaluate Design
```
§02 → §08 → §09 → §19 → §31 → §36 → §25 → §10 → §13 → §07
```
Covers principles → jury design → economics → chain orchestration → success criteria.

---

## Critical Inter-Section Dependencies

```
§26  MUST be read before §27   (style rules are prompt inputs)
§04  MUST be read before §05   (State schema required for all agents)
§09  MUST be read before §10   (CSS formula required for veto logic)
§19  MUST be read before §29   (budget regimes define YAML valid ranges)
§21  MUST be read before §04   (persistence model constrains graph design)
§17  MUST be read before §18   (Source type determines citation format)
§08  MUST be read before §11   (jury verdict format required for panel)
§12  MUST be read before §05.12 (Reflector scope defines Span Editor activation)
§03B MUST be read before §05.7  (Style Exemplar is Writer input)
§31  REQUIRES §04 complete      (Pipeline Orchestrator wraps the full graph)
```

```
§39  MUST run before Phase A    (blocks code generation until critical_issues == 0)
§04  provides DocumentState fields consumed by §39.6 (SpecValidationState)
```

<!-- SPEC_COMPLETE -->