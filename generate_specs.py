#!/usr/bin/env python3
"""
generate_specs.py v3.0 — AI-optimized spec generation
Format: machine-readable English, typed contracts, no prose
"""
import os, time, datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL        = "anthropic/claude-sonnet-4-6"
REVIEW_MODEL = "google/gemini-2.0-flash-001"  # cheap reviewer
MAX_TOKENS   = 32000
RETRY_ATTEMPTS = 3
RETRY_DELAY    = 15
SOURCE_DIR  = Path("source")
OUTPUT_DIR  = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """You are a senior software architect writing AI-READABLE technical specifications
for the Deep Research System (DRS). These files will be read by AI coding agents, not humans.

=== OUTPUT FORMAT (mandatory, zero exceptions) ===

1. LANGUAGE: English only.
2. TYPED CONTRACTS: Python type hints everywhere. No prose descriptions of data.
3. AGENT TEMPLATE - every agent must use this exact structure:
   AGENT: Name [section]
   RESPONSIBILITY: single verb phrase
   MODEL: model-id / TEMP: 0.x / MAX_TOKENS: N
   INPUT: field: Type
   OUTPUT: TypeName
   CONSTRAINTS: MUST/NEVER/ALWAYS rule
   ERROR_HANDLING: condition -> action -> fallback
   CONSUMES: [StateField] from DocumentState
   PRODUCES: [StateField] -> DocumentState
4. LITERALS: always Literal["a","b"], never "one of: a or b".
5. CODE BLOCKS: all schemas, YAML, SQL, Python types, JSON examples.
6. THRESHOLDS: always explicit numbers. CSS >= 0.85, never "sufficiently high".
7. CROSS-REFS: section N.M notation. If defined elsewhere, write "see N.M" - NEVER copy.

=== COMPRESSION RULES (mandatory) ===

- If a field name is self-explanatory, NO comment needed
- If info is defined in section X, write "see X" - never copy it here
- No example if the type already implies it (str, int, bool)
- One example max per concept, never two
- No "Note:", "Important:", "Remember:" prefixes
- Omit obvious defaults (None for Optional, [] for list)
- No inline explanation of Python syntax (assume senior dev)
- Prefer tables over repeated bullet structures
- If two agents share a pattern, define it once and reference it
- No restating the section title as first sentence

=== TOKEN ECONOMY (mandatory - design constraint, not style preference) ===

Token budget per file: 1500-3500 tokens.
Exceeding the budget means you are repeating or over-explaining. Cut ruthlessly.
Every token costs money at inference time - both during spec generation
and every time an AI agent reads them during system operation.
Violating token economy is a bug, not a style choice.

=== QUALITY BAR ===

An AI coding agent reading this file must be able to:
  (a) implement the component without asking any clarifying questions
  (b) write a unit test for every constraint listed
  (c) determine exactly which other components produce each INPUT field
If any of (a)(b)(c) is impossible from this file alone -> the file is incomplete.
End every complete file with exactly: <!-- SPEC_COMPLETE -->"""

FILES = [
    ("01_vision.md", "§1.1-1.4",
     "Define: system description (1 paragraph max), use_case table (doc_type/word_range/complexity), user_type table (persona/user_story), mandatory params (max_budget_dollars, target_words) with types and valid ranges, derived params list."),
    ("02_design_principles.md", "§2.1-2.11",
     "For each of the 11 principles: NAME, ONE_LINE_DEFINITION, IMPLEMENTATION_CONSTRAINT (what the code must/must-not do), VIOLATED_BY (antipattern example). Principles: Budget-First, Section-Granularity, Epistemic-Diversity, Minority-Veto, Economic-Cascading, Accumulated-Context, Human-in-the-Loop, Observability, Zero-Downtime, GDPR-Privacy, Testability-First."),
    ("03_input_config.md", "§3.1-3.3",
     "Full Pydantic model for DRSConfig with all fields typed, validators, error messages. YAML examples for: minimal academic, full business, software-spec pipeline. Required vs optional with defaults."),
    ("03b_style_calibration.md", "§3B.1-3B.4",
     "StyleCalibrationGate: flow diagram as ASCII, StyleExemplar schema, frozen ruleset mechanism (what freezes, when, only-exception), UI text exact strings for approve/feedback/regenerate, max attempts + fallback to preset-change, injection mechanism into Writer context."),
    ("04_architecture.md", "§4.1-4.6",
     "ASCII flow diagram for phases A-D with all conditional branches. DocumentState TypedDict with ALL fields typed. LangGraph node list with edge conditions as Python conditionals. Narrative for each phase in bullet points only. route_after_aggregator() full logic."),
    ("05_agents.md", "§5.1-5.20",
     "Full spec for all 20 agents using the AGENT template. Agents: Planner, Researcher, CitationManager, CitationVerifier (DeBERTa NLI), SourceSanitizer (3-stage injection guard), SourceSynthesizer (NEW §5.6), Writer (StyleExemplar injected), MetricsCollector, StyleLinter (deterministic non-LLM), StyleFixer, PostDraftAnalyzer, SpanEditor, Fusor, Reflector, OscillationDetector, ContextCompressor, CoherenceGuard, WriterMemory, Publisher, FeedbackCollector."),
    ("06_run_companion.md", "§6.1-6.6",
     "RunCompanion: NOT orchestrator definition, readable State fields table with field/type/accessible_since, 4 response types with exact dialogue examples, direct_modifications list vs confirm_required list, proactive_triggers table with trigger/message/condition, conversation persistence schema."),
    ("07_mixture_of_writers.md", "§7.1-7.6",
     "MoW: activation conditions as boolean expression, Writer proposer table (W-A/B/C with temp/angle/profile), Fusor spec (model/constraints/single-run), jury multi-draft evaluation sequence, cost model with break-even formula, ASCII flow MoW vs single-writer."),
    ("08_jury_system.md", "§8.1-8.6",
     "Three mini-juries (R/F/S): judge models, evaluation rubric as scoring dimensions with weights, Agent-as-Judge for F (falsification logic, max 3 claims, 2 queries/claim, external_sources_consulted field), cascading tiers with conditions and expected savings, full VerdictJSON schema typed."),
    ("09_css_aggregator.md", "§9.1-9.4",
     "CSS formula with derivation: CSS_content = 0.44*pass_R/n_R + 0.56*pass_F/n_F, CSS_style = pass_S/n_S, threshold table by quality_preset. Content Gate vs Style Pass as sequential phases. Full route_after_aggregator() decision tree as Python pseudo-code with all branches."),
    ("10_minority_veto.md", "§10.1-10.3",
     "MinorityVeto: L1 individual veto with veto_category enum (fabricated_source/factual_error/logical_contradiction/plagiarism) + definition + system behavior per category. L2 unanimous jury veto condition. RogueJudgeDetector: threshold (>70% disagreement over 3+ sections), notification flow, temporary fallback + log schema."),
    ("11_panel_discussion.md", "§11.1-11.3",
     "PanelDiscussion: activation condition (CSS < panel_threshold, default 0.50), step-by-step mechanism (anonymization, comment exchange format, revote), max 2 rounds, PostgreSQL log schema, all possible exits with routing."),
    ("12_reflector.md", "§12.1-12.3",
     "Reflector: FeedbackItem schema with all fields typed (severity enum, category, affected_text as exact quote, action, scope, priority). Scope determination rules: SURGICAL/PARTIAL/FULL with conditions. Conflict resolution rule. SURGICAL vs PARTIAL vs FULL examples as JSON."),
    ("13_oscillation_detector.md", "§13.1-13.4",
     "Three oscillation types with exact formulas: CSS oscillation (variance < threshold for N≥4 iter), Semantic oscillation (cosine_sim ≥ 0.85 between draft_N and draft_N-2 with divergence on N-1), Whack-a-Mole (error categories change completely each iter). Early warning condition. Escalation UI data (CSS history, draft log, oscillation type) + available actions."),
    ("14_context_compressor.md", "§14.1-14.3",
     "ContextCompressor: compression strategy by position (verbatim last 2, structured summary 3-5, thematic extract ≥6), load-bearing claim identification algorithm, model qwen3-7b rationale, invocation timing (after approval, not before next section), output schema and injection point."),
    ("15_coherence_guard.md", "§15.1-15.3",
     "CoherenceGuard: SOFT vs HARD levels with conditions, contradiction report format. ContradictionDetector: post-assembly cross-section scan. FormatValidator: checks (referenced sections exist, length ±10%, zero L1 violations, all citations have entry) with routing per failed check."),
    ("16_writer_memory.md", "§16.1-16.3",
     "WriterMemory schema (all fields typed). Forbidden pattern tracker: threshold, exact reminder text injected into Writer prompt. Technical glossary: inconsistency detection + alert. Citation tendency tracker: under/over-citation average with proactive reminder. Injection mechanism: when and where in Writer prompt."),
    ("17_research_layer.md", "§17.1-17.9",
     "SourceConnector interface: async def search(query, max_results) -> list[Source]. Source schema typed. Each connector: reliability_score, API params, fallback. SourceRanker scoring algorithm. SourceDiversityAnalyzer: thresholds (max 40% same publisher, 30% same author, 50% same year) + action on concentration. Scraper fallback. User-upload local processing."),
    ("18_citations.md", "§18.1-18.5",
     "CitationManager: formatting for Harvard/APA/Chicago/Vancouver with typed output examples. CitationVerifier pipeline: HTTP 200 check → DOI resolver → NLI DeBERTa entailment → temporal consistency → quantitative consistency. Classification enum: valid/mismatch/ghost with behavior per class. missing_evidence path → targeted Researcher. HallucinationRateTracker PostgreSQL schema + alert threshold per model."),
    ("19_budget_controller.md", "§19.1-19.5",
     "Pre-run formula with all factors typed. Three regime table (Economy/Standard/Premium): CSS thresholds, max_iter, jury_size, MoW flag, models per slot. Real-time tracker: per-agent/section/iteration counter, exact alarm texts at 70%/90%/100%. Dynamic savings strategies: trigger → action for each. Adaptive parameter table as levers per regime."),
    ("20_error_handling.md", "§20.1-20.5",
     "ErrorHandlingMatrix as Python TypedDict: trigger, first_response, second_response, fallback, escalation. Scenarios: API 429/500/timeout, LLM malformed output, ghost citation, context overflow, mid-section crash, mid-jury crash. Retry policy: exponential backoff (2s/4s/8s + jitter, max 3). Circuit breaker states CLOSED/OPEN/HALF-OPEN. Fallback chain YAML with independent circuit breaker per agent slot."),
    ("21_persistence.md", "§21.1-21.3",
     "Full PostgreSQL schema: tables (documents/outlines/sections/jury_rounds/costs/sources/runs/writer_memory/run_companion_log) with typed columns and keys. LangGraph AsyncPostgresSaver config. Resume mechanism step-by-step with concrete crash+recovery timeline. Redis key schema with TTL. Store permanent vs State ephemeral architectural difference."),
    ("22_security.md", "§22.1-22.7",
     "SourceSanitizer 3-stage injection guard (regex/XML isolation/output monitoring). PII detection: presidio-analyzer + regex + local NER, before every external LLM call. PrivacyMode enum (cloud/self_hosted/hybrid) with Ollama/VLLM substitution table. OAuth2+JWT + audit log. AES-256 at rest + TLS 1.3. GDPR: right-to-deletion flow, data export, retention policy. Data→provider explicit mapping."),
    ("23_observability.md", "§23.1-23.7",
     "OpenTelemetry mandatory span attributes (run_id/section_idx/iteration/agent/model/tokens_in/tokens_out/cost_usd/latency_ms/outcome). Prometheus metrics table: name/type/labels/description. Grafana panels list with PromQL queries. Sentry error schema. Structured log JSON fields (free text forbidden in prod). Alerting trigger table: condition/severity/recipient."),
    ("24_api.md", "§24.1-24.4",
     "REST API: for each endpoint (POST/GET/DELETE /v1/runs, GET /v1/runs/{id}/stream SSE, POST approve/pause/resume, GET /v1/documents/{id}/export): URL, HTTP method, request body JSON schema, response schema, HTTP codes + meaning, curl example. All SSE event types with typed payload. Auth: X-DRS-Key + JWT + rate limiting."),
    ("25_testing.md", "§25.1-25.11",
     "GoldenDataset criteria + ground_truth structure. Unit tests: deterministic modules list + coverage target. Integration tests: MockLLMClient interface + predefined outputs + agent interception. PromptUnitTest: input/expected_output_structure/forbidden_in_output. Regression threshold + rollback. CostTest. OscillationSimulation synthetic inputs. ChaosTest API-down scenarios. BERTScore + citation_validity + Cohen's kappa. DI pattern: constructor injection, no direct imports, MockLLMClient/MockSearchClient/MockDBClient. Smoke suite: make test-phaseN + checklist per phase."),
    ("26_style_profiles.md", "§26.1-26.11",
     "L1/L2/L3 rule schema: {id, level, category, enforcement, message, fix_hint, regex_pattern?}. Per profile (scientific/business/technical/journalistic/narrative/ai-instructions/blog): tone, register, L1/L2/L3 rules with regex where applicable, W-A/B/C angles. Universal forbidden patterns with good/bad examples. Customization modes (natural language/YAML/form). i18n support."),
    ("27_prompt_layer.md", "§27.1-27.4",
     "3-level structure (System/Context/Task) with annotated placeholder template for each agent (Writer/Reflector/JudgeF). Exact anti-sycophancy formulation in English for judge system prompts. Prompt versioning: file naming convention + failure log + review schedule. PromptRegistry schema with per-version metrics. A/B testing framework with auto-rollback condition."),
    ("28_llm_assignments.md", "§28.1-28.4",
     "Full table: agent / primary_model / fallback_1 / fallback_2 / task_fit_justification for all 20 agents. Task-fit principle vs benchmark ranking with decisive capability examples per role. Model verification pre-run procedure. MODEL_PRICING dict with input/output cost per M tokens. Update procedure + Budget Estimator impact."),
    ("29_yaml_config.md", "§29.1-29.6",
     "Complete annotated YAML config file with every parameter commented. Pydantic schema with validators + explicit error messages for every out-of-range field. Sections: user (budget/words/language/style/preset), models (per-agent slot with fallback chain), convergence (all CSS thresholds/oscillation/panel), sources (connectors/max per section/reliability/diversity), style (profile ref/extra forbidden in 3 formats/calibration gate toggle)."),
    ("30_output.md", "§30.1-30.6",
     "Guaranteed output properties (length ±10%, zero L1 violations, verified citations). Publisher spec (Store assembly, DOCX template styles, auto-summary, bibliography, section cache). Per output format (DOCX/PDF/Markdown/LaTeX+BibTeX/HTML/JSON): technology, file structure, use case. RunReport JSON schema (all fields: cost per agent, CSS history, verdicts, RunCompanion conversation, hallucination rate). Multi-file output for software_spec (AGENTS.md/architecture.md/api_spec.yaml/features/). FeedbackCollector rating schema + training loop."),
    ("31_pipeline_orchestrator.md", "§31.1-31.6",
     "3-step sequential pipeline rationale (why not single step). DRS#1 functional_spec: input/output/jury adaptation (JudgeF checks AC testability). DRS#2 technical_spec: input (functional_spec+DecisionLog)/output/CoherenceGuard traceability. DRS#3 software_spec: multi-file output, JudgeS→AI-Readability. PipelineOrchestrator as zero-LLM pure logic. DecisionLog JSON schema. inter-step Summary structure. Traceability matrix format AC-007→satisfies→mechanism."),
    ("32_ui.md", "§32.1-32.7",
     "Config wizard: steps/fields/inline validations/live style preview. Outline editor: drag-and-drop behaviors, inline editing, insufficient-sources revision request. Progress dashboard components: section status, CSS trend chart, cost gauge with alarms, iteration count, ETA, recent event log. Escalation UI: visual diff + actions per escalation type. Section regeneration flow + cost estimate. Style override without interrupting production. RunCompanion: chat sidebar, proactive badge, conversation log."),
    ("33_tech_stack.md", "§33.1-33.10",
     "Stack table: layer/technology/min_version/rationale/alternatives_rejected/config_notes. Layers: Orchestration LangGraph, Backend FastAPI+Uvicorn+Pydantic, Frontend Streamlit(MVP)/Next.js(prod), Queue Celery+Redis, Persistence PostgreSQL+Redis+S3/MinIO, LLM Routing OpenRouter, NLP sentence-transformers+DeBERTa+textstat+presidio+tenacity, Output python-docx+weasyprint+pandoc+BibTeX, Container Docker Compose/K8s. Full pyproject.toml with all Python deps + versions + rationale."),
    ("34_deployment.md", "§34.1-34.4",
     "Docker Compose dev: services/volumes/MockLLM/PostgreSQL/env vars. K8s staging: real models, reduced budget, anonymized data. K8s prod: HPA autoscaling for agents, PodDisruptionBudget, ConfigMap/Secret, hourly PostgreSQL backup, 30d retention. Rate limiting: asyncio semaphores (OpenRouter 60 req/min, CrossRef 50 req/s, Tavily Retry-After). Horizontal scaling strategy for agents as microservices. Full project directory tree."),
    ("35_roadmap.md", "§35.1-35.4",
     "4 phases: objective/included/excluded/completion_criteria/dependencies/time_estimate. Phase 1 MVP Core (4w): single Writer, Judge F+S, Tavily, Markdown, max 1 iter, fixed budget cap. Phase 2 Multi-Judge (4w): 3×3 juries, CSS, MinorityVeto, Reflector, Panel, OscillationDetector, PostgreSQL checkpointing. Phase 3 Advanced (6w): Planner, academic sources, NLI, Compressor, CoherenceGuard, StyleCalibrationGate, StyleFixer, MoW+Fusor, DOCX/PDF. Phase 4 Production (8w): Next.js, Celery, OTel, RunCompanion, DRS chain, security audit, load test. Dependency diagram."),
    ("36_kpis.md", "§36.1-36.7",
     "KPI table: metric/definition/target_value/measurement_method/frequency/grafana_panel. Categories: quality (human_acceptance ≥90%, citation_accuracy ≥98%, L1_violation_rate ≤1%, error_density ≤1/1000w), economy (cost/doc $20-50, cost/word ≤$0.004, first_approval ≥60%, avg_iter ≤2.5), reliability (uptime ≥99.5%, recovery_rate 100%, MTTR ≤5min), convergence (oscillation_rate ≤5%, panel_rate ≤15%, budget_overrun 0%), MoW (first_approval ≥55%, delta_vs_single ≥15pp), RunCompanion (response ≤3s, alert_relevance ≥70%), StyleGate (pass_rate ≥70%, fixer_convergence ≥90%)."),
    ("37_extensibility.md", "§37.1-37.4",
     "SourceConnector interface with full signature + Source typed schema + custom connector example (corporate DB). Judge interface with mandatory methods + VerdictSchema + domain-specific Judge example (Legal/Medical with custom rubric + Aggregator integration without changes). OutputFormatter interface + custom format example. Multi-Document Mode: shared glossary schema, citation reuse (verified sources not re-processed), cross-referencing system, style consistency cross-document. Python docstrings for all interfaces."),
    ("38_dev_rules.md", "§38.1-38.5",
     "Operational rules for AI builder. Each rule: NAME, DESCRIPTION, RATIONALE, CORRECT_EXAMPLE (Python code), WRONG_EXAMPLE (Python code), CONSEQUENCE_IF_VIOLATED. Rules: 38.1 Preflight-mandatory (thread_id saved immediately), 38.2 Pydantic-mandatory (never json.loads direct, FAIL on parse_error), 38.3 Async-parallelism (3 mini-juries in asyncio.gather, MoW Writers parallel, Reflector always sequential), 38.4 WebSocket-via-Redis-pubsub (Celery publishes, WS endpoint forwards, never polling), 38.5 DI-mandatory (no direct imports in src/agents/, MockLLMClient injectable, clients injected at constructor)."),
    ("00_index.md", "§index",
     "Project title + version + date. Executive summary 200 words max (what it does, key architecture, outputs). Table of all 38 files: number/title/one-line-description/relative link. Reading paths for 3 profiles: (1) implement-from-scratch: 33→04→05→rest, (2) integrate-component: navigate by section, (3) evaluate-design: 02→08→09→19→31. Inter-section dependencies note (read §26 before §27)."),
]

def load_sources() -> str:
    sources = []
    for path in sorted(SOURCE_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        sources.append(f"{'='*60}\nSOURCE: {path.name}\n{'='*60}\n{content}")
    if not sources:
        raise FileNotFoundError(f"No .md files in {SOURCE_DIR}/")
    return "\n".join(sources)

def is_complete(path: Path) -> bool:
    if not path.exists(): return False
    content = path.read_text(encoding="utf-8")
    return len(content) > 500 and "<!-- SPEC_COMPLETE -->" in content

def generate_file(client, filename, section_ref, instructions, source_content) -> str:
    user_prompt = f"""Generate spec file: {filename}
Reference sections: {section_ref}

GENERATION INSTRUCTIONS:
{instructions}

---
SOURCE MATERIAL:
{source_content}
---

Rules:
- Write in English, machine-readable format
- Use typed contracts (Python types), not prose
- Every agent: INPUT/OUTPUT/MODEL/CONSTRAINTS/ERROR_HANDLING/CONSUMES/PRODUCES
- All thresholds explicit (numbers, not words)
- Code blocks for schemas, configs, type definitions
- Cross-references as §N.M notation
- When complete, end with exactly: <!-- SPEC_COMPLETE -->"""

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"  [{ts}] API call {attempt}/{RETRY_ATTEMPTS}...", flush=True)
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                extra_headers={
                    "HTTP-Referer": "https://github.com/deep-research-spec",
                    "X-Title": "DRS Spec Generator v3.0",
                },
            )
            content = response.choices[0].message.content
            if "<!-- SPEC_COMPLETE -->" not in content:
                raise ValueError(f"Truncated after {len(content)} chars. Increase MAX_TOKENS.")
            return content
        except Exception as e:
            print(f"  ⚠ Error attempt {attempt}: {e}", flush=True)
            if attempt < RETRY_ATTEMPTS:
                wait = RETRY_DELAY * attempt
                print(f"  Waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise

def main():
    print("=" * 60, flush=True)
    print(f"DRS SPEC GENERATOR v3.0", flush=True)
    print(f"Model: {MODEL} | Max tokens: {MAX_TOKENS}", flush=True)
    print("=" * 60, flush=True)

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in .env")

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")

    print("Loading source files...", flush=True)
    source_content = load_sources()
    print(f"Sources loaded: {len(source_content):,} chars", flush=True)

    total    = len(FILES)
    skipped  = 0
    generated = 0
    failed   = []

    for i, (filename, section_ref, instructions) in enumerate(FILES, 1):
        output_path = OUTPUT_DIR / filename
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{ts}] [{i:02d}/{total}] {filename}", flush=True)

        if is_complete(output_path):
            print(f"  ✓ Already complete — skipping", flush=True)
            skipped += 1
            continue

        if output_path.exists():
            print(f"  ⚠ Exists but incomplete — regenerating", flush=True)

        try:
            content = generate_file(client, filename, section_ref, instructions, source_content)
            output_path.write_text(content, encoding="utf-8")
            print(f"  ✓ Saved {len(content):,} chars", flush=True)
            generated += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}", flush=True)
            failed.append(filename)

        if i < total:
            time.sleep(2)

    print("\n" + "=" * 60, flush=True)
    print(f"DONE: {generated} generated, {skipped} skipped, {len(failed)} failed", flush=True)
    if failed:
        print("Failed files:", flush=True)
        for f in failed:
            print(f"  - {f}", flush=True)
    print("=" * 60, flush=True)

if __name__ == "__main__":
    main()
