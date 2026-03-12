# Deep Research System — Development Plan v1.0

> **Repository:** [lucadidomenicodopehubs/deep-research-spec](https://github.com/lucadidomenicodopehubs/deep-research-spec)  
> **Branch:** `struct`  
> **Target:** Production-ready DRS v1.0 con ottimizzazioni §29  
> **Timeline:** 8 sprints × 2 settimane = ~4 mesi  
> **Team size:** 2-3 dev + 1 QA

---

## Executive Summary

Questo piano implementa il Deep Research System seguendo l'architettura definita nelle specs `docs/*.md`. Le ottimizzazioni §29 sono integrate nei primi 3 sprint per ottenere **-60% costi + -40% latency** prima di proseguire con feature avanzate.

**Priorità implementazione:**

1. **Sprint 0-1:** Infra base + §29 ottimizzazioni immediate (prompt caching, state optimization, parallel execution)
2. **Sprint 2-3:** Core agents (Writer, Jury, Reflector) + LangGraph orchestration
3. **Sprint 4-5:** MoW, Panel, Budget Controller, Shine Integration
4. **Sprint 6-7:** QA, monitoring, production hardening

**Deliverable finale:** Sistema DRS deployment-ready con:
- Pipeline completa Phase A-D
- Ottimizzazioni §29.1-29.6 attive
- Monitoring Prometheus + Grafana
- CI/CD con regression tests
- Documentazione operativa

---

## Sprint 0: Infrastructure Foundation (Settimana 1-2)

### Obiettivo
Setup ambiente locale + CI/CD + database + monitoring stack.

### Task List

#### S0.1 — Environment Setup
- [ ] **S0.1.1** Clone repo `deep-research-spec` branch `struct`
- [ ] **S0.1.2** Setup Python 3.11+ venv con `requirements-shine.txt`
- [ ] **S0.1.3** Install PostgreSQL 15+ locale (Docker Compose)
- [ ] **S0.1.4** Install Redis 7+ per job queue + cache (Docker Compose)
- [ ] **S0.1.5** Setup MinIO per S3-compatible storage (Docker Compose)
- [ ] **S0.1.6** Crea `.env` da template con API keys (Anthropic, OpenAI, Google, Perplexity, OpenRouter)

#### S0.2 — Database Schema
- [ ] **S0.2.1** Implementa migrations PostgreSQL per tabelle:
  - `documents` (docid, userid, status, config JSONB, created_at, updated_at)
  - `sections` (id, documentid, sectionindex, title, content, cssfinal, cssbreakdown JSONB, iterationsused, verdictshistory JSONB, approvedat, version)
  - `costs` (id, docid, sectionidx, iteration, agent, model, tokensin, tokensout, costusd, latencyms, timestamp)
  - `feedback` (id, runid, userid, sectionratings JSONB, errorhighlights JSONB, styledfeedback, timestamp)
  - `checkpoints` (id, docid, threadid, state BYTEA, created_at) — LangGraph checkpoint store
- [ ] **S0.2.2** Setup Alembic per migrations versionate
- [ ] **S0.2.3** Seed database con test fixtures (3 sample documents)

#### S0.3 — CI/CD Pipeline
- [ ] **S0.3.1** GitHub Actions workflow `.github/workflows/ci.yml`:
  - Pytest con coverage ≥80%
  - Black formatter check
  - Mypy type checking
  - Budget regression test (blocca PR se costo stimato > baseline + 10%)
- [ ] **S0.3.2** Pre-commit hooks: black, isort, flake8
- [ ] **S0.3.3** Branch protection rules: require 1 approval + CI pass

#### S0.4 — Monitoring Stack
- [ ] **S0.4.1** Setup Prometheus + Grafana (Docker Compose)
- [ ] **S0.4.2** Install `prometheus-client` in Python app
- [ ] **S0.4.3** Crea metriche base:
  - `drs_agent_calls_total{agent, model}` — Counter
  - `drs_agent_latency_seconds{agent}` — Histogram
  - `drs_llm_tokens_total{model, type}` — Counter (in/out)
  - `drs_llm_cost_usd_total{model}` — Counter
  - `drs_section_css{section}` — Gauge
  - `drs_budget_spent_usd` — Gauge
- [ ] **S0.4.4** Grafana dashboard template `monitoring/dashboards/drs_overview.json`

#### S0.5 — Project Structure
- [ ] **S0.5.1** Refactor `src/` seguendo architettura:
  ```
  src/
  ├── agents/           # §5 agents
  │   ├── planner.py
  │   ├── researcher.py
  │   ├── writer.py
  │   ├── jury.py
  │   ├── reflector.py
  │   └── ...
  ├── graph/            # §4 LangGraph orchestration
  │   ├── state.py      # DocumentState TypedDict
  │   ├── nodes.py      # Node functions
  │   ├── edges.py      # Conditional routing
  │   └── builder.py    # build_graph()
  ├── llm/              # §28 model routing
  │   ├── client.py     # Unified LLM client
  │   ├── routing.py    # Model tiering logic
  │   └── pricing.py    # MODEL_PRICING table
  ├── budget/           # §19 Budget Controller
  │   ├── estimator.py
  │   ├── tracker.py
  │   └── savings.py
  ├── storage/          # §21 PostgreSQL + MinIO
  │   ├── db.py
  │   └── s3.py
  ├── connectors/       # §17 Shine connectors
  │   └── shine.py
  ├── security/         # §5.5 SourceSanitizer
  │   └── sanitizer.py
  ├── config/           # §1-3 config schemas
  │   └── schemas.py
  └── main.py           # CLI entrypoint
  ```
- [ ] **S0.5.2** Setup `pytest` structure mirror: `tests/unit/`, `tests/integration/`
- [ ] **S0.5.3** Crea `Makefile` con target: `make test`, `make lint`, `make docker-up`

**Deliverable Sprint 0:**
- ✅ Infra locale runnable via `make docker-up`
- ✅ CI/CD green su GitHub Actions
- ✅ Grafana dashboard accessibile su `localhost:3000`
- ✅ Test fixtures caricati in PostgreSQL

**Effort:** 2 settimane × 1 dev

---

## Sprint 1: §29 Ottimizzazioni Immediate (Settimana 3-4)

### Obiettivo
Implementare §29.1 (Prompt Caching), §29.5 (State Optimization), §29.6 (Parallel Execution).

**Target:** -60% costi operativi + -40% latency Phase B.

### Task List

#### S1.1 — §29.1 Prompt Caching
- [ ] **S1.1.1** Modifica `src/llm/client.py`:
  - Aggiungi parametro `cache_blocks: list[dict]` a `call_llm()`
  - Wrapper per Anthropic: system prompt come array con `cache_control: {"type": "ephemeral"}`
  - Wrapper per OpenAI: usa header `X-OpenAI-Cache-Prompt` (se supportato)
- [ ] **S1.1.2** Aggiorna `src/agents/writer.py` (`§5.7`):
  - Inject `style_profile_rules` con `cache_control`
  - Inject `style_exemplar` con `cache_control`
  - System prompt totale: `[rules_block, exemplar_block, memory_block]`
- [ ] **S1.1.3** Aggiorna `src/agents/jury.py` (Judge R/F/S):
  - Cache verdict schema + evaluation rubric
  - Cache per-judge instructions (R: reasoning, F: factual, S: style)
- [ ] **S1.1.4** Aggiorna `src/agents/reflector.py` (`§5.14`):
  - Cache feedback synthesis instructions
- [ ] **S1.1.5** Aggiorna `src/agents/fusor.py` (`§5.13`):
  - Cache fusion strategy instructions
- [ ] **S1.1.6** Test: crea unit test `tests/unit/test_prompt_caching.py`:
  - Mock Anthropic API, verifica `cache_control` presente in request body
  - Verifica token counts: `cache_creation_input_tokens`, `cache_read_input_tokens`
- [ ] **S1.1.7** Integration test: run 5 sezioni consecutive, misura cache hit rate ≥70%

#### S1.2 — §29.5 State Optimization
- [ ] **S1.2.1** Aggiorna `src/graph/state.py` (`DocumentState`):
  - `draft_embeddings: Annotated[list[list[float]], MaxLen(window=4)]`
  - `css_history: Annotated[list[float], MaxLen(window=8)]`
  - Aggiungi `embeddings_db_ref: str` per lazy loading
- [ ] **S1.2.2** Implementa `MaxLen` reducer in `src/graph/state.py`:
  ```python
  from typing import Annotated
  from langgraph.graph.message import add_messages
  
  def max_len_reducer(window: int):
      def reducer(existing: list, new: list) -> list:
          return (existing + new)[-window:]
      return reducer
  
  MaxLen = lambda window: max_len_reducer(window)
  ```
- [ ] **S1.2.3** Aggiorna `src/storage/db.py`:
  - Aggiungi metodi `store_embeddings(docid, embeddings)` → PostgreSQL JSONB
  - Aggiungi `fetch_embeddings(docid)` → lazy load on-demand
- [ ] **S1.2.4** Modifica `all_verdicts_history` persistence:
  - Serialize to JSONB dopo ogni sezione in `sections.verdictshistory`
  - Non portare full history in `DocumentState` oltre sezione corrente
- [ ] **S1.2.5** Test: `tests/unit/test_state_optimization.py`:
  - Verifica `draft_embeddings` non supera mai 4 elementi
  - Misura `sys.getsizeof(state)` pre/post optimization → target -90%
- [ ] **S1.2.6** Integration test: run 10 sezioni, verifica state size < 200KB

#### S1.3 — §29.6 Parallel Execution
- [ ] **S1.3.1** Refactora `src/agents/citation_verifier.py` (`§5.4`):
  - Estrai 3 funzioni async:
    - `async def http_check(source) -> bool`
    - `async def doi_resolve(source) -> str | None`
    - `async def deberta_nli(claim, source) -> float`
  - Modifica `run()` per usare `asyncio.gather(*tasks)` in parallelo
- [ ] **S1.3.2** Test: `tests/integration/test_citation_verifier_parallel.py`:
  - Mock 12 sources
  - Misura latency sequenziale vs parallelo → target 18× speedup
- [ ] **S1.3.3** Aggiorna `src/agents/panel_discussion.py` (`§5.11`):
  - Parallelizza chiamate ai 3 judges con `asyncio.gather`
  - Da 90s sequenziale a ~32s parallelo
- [ ] **S1.3.4** Integration test: end-to-end Phase B su 3 sezioni, misura latency -40%

#### S1.4 — Monitoring §29 Metrics
- [ ] **S1.4.1** Aggiungi metriche Prometheus:
  - `drs_cache_hit_rate{agent}` — Gauge (0.0-1.0)
  - `drs_state_size_bytes` — Gauge
  - `drs_parallel_speedup_ratio{node}` — Gauge
- [ ] **S1.4.2** Grafana dashboard panel:
  - "§29 Optimizations" row con 3 graph:
    - Cache hit rate per agent (line)
    - State size evolution (area)
    - Parallel speedup by node (bar)

**Deliverable Sprint 1:**
- ✅ Prompt caching attivo su Writer + Jury + Reflector + Fusor
- ✅ DocumentState bounded, state size < 200KB dopo 10 sezioni
- ✅ CitationVerifier + Panel parallelizzati, latency -40%
- ✅ Regression test: costo medio/run ridotto 50-60% vs baseline senza caching

**Effort:** 2 settimane × 2 dev

---

## Sprint 2: Core Agents (Planner, Researcher, Writer) (Settimana 5-6)

### Obiettivo
Implementare agents fondamentali per Phase A e Phase B (prima iterazione senza jury).

### Task List

#### S2.1 — Planner Agent (`§5.1`)
- [ ] **S2.1.1** Implementa `src/agents/planner.py`:
  - Input: `topic`, `target_words`, `style_profile`, `quality_preset`
  - Output: `outline: list[OutlineSection]`, `document_type`
  - Prompt template in `prompts/planner.txt`
  - Model: `google/gemini-2.5-pro` (§28)
- [ ] **S2.1.2** Constraint checks:
  - Distribuzione word count ±5% bilanciata
  - Nessuna sezione < 200 parole
  - Max 20 sezioni totali
- [ ] **S2.1.3** Error handling: retry con prompt semplificato, fallback a `gemini-2.5-flash`
- [ ] **S2.1.4** Unit test: `tests/unit/test_planner.py` con 5 topic diversi
- [ ] **S2.1.5** Integration test: verifica outline JSON parseable da Pydantic

#### S2.2 — Researcher Agent (`§5.2`)
- [ ] **S2.2.1** Implementa `src/agents/researcher.py`:
  - Model: `perplexity/sonar-pro` (§28)
  - Connectors: Perplexity Sonar + Tavily + Brave + BeautifulSoup fallback (§17)
  - Output: `sources: list[Source]` ranked + deduplicated
- [ ] **S2.2.2** Integra `src/connectors/shine.py` per Tavily/Brave APIs
- [ ] **S2.2.3** Source ranking:
  - `reliability_score` basato su domain authority + publish date
  - Diversification score ≥0.6 (§17.8)
- [ ] **S2.2.4** Deduplication: by URL + DOI
- [ ] **S2.2.5** Error handling: cascade Sonar → Tavily → Brave → Scraper
- [ ] **S2.2.6** Unit test: mock connectors, verifica ranking + dedup
- [ ] **S2.2.7** Integration test: query reale, verifica max 12 sources returned

#### S2.3 — CitationManager + CitationVerifier (`§5.3`, `§5.4`)
- [ ] **S2.3.1** Implementa `src/agents/citation_manager.py`:
  - Deterministic (no LLM)
  - Genera `citation_map: dict[source_id, citation_string]`
  - Supporta APA, Harvard, Chicago, Vancouver
- [ ] **S2.3.2** Unit test: 10 sources con diversi formati (DOI, ISBN, URL only)
- [ ] **S2.3.3** Implementa `src/agents/citation_verifier.py` (già parallelizzato in S1.3.1)
- [ ] **S2.3.4** DeBERTa NLI integration:
  - Load model `microsoft/deberta-v3-large-mnli` local
  - Entailment threshold: score ≥0.80
- [ ] **S2.3.5** Integration test: verifica HTTP check + DOI resolution + NLI

#### S2.4 — SourceSanitizer (`§5.5`)
- [ ] **S2.4.1** Implementa `src/security/sanitizer.py`:
  - Stage 1: regex injection patterns (§5.5 spec)
  - Stage 2: XML wrapping `<external_source id="{source_id}">...</external_source>`
  - Stage 3: jailbreak detection post-output
- [ ] **S2.4.2** Unit test: 5 injection payloads, verifica truncation + log
- [ ] **S2.4.3** Security audit: test con OWASP LLM Top 10 payloads

#### S2.5 — SourceSynthesizer (`§5.6`)
- [ ] **S2.5.1** Implementa `src/agents/source_synthesizer.py`:
  - Model: `anthropic/claude-sonnet-4` (§28)
  - Compression ratio target: 40% (retain 40% tokens)
  - Deduplica claims semanticamente equivalenti
- [ ] **S2.5.2** Constraint: preserve all `source_id` references
- [ ] **S2.5.3** Unit test: verifica compression ratio ±10%
- [ ] **S2.5.4** Integration test: 15 sources → compressed corpus < 4000 tokens

#### S2.6 — Writer Agent (`§5.7`)
- [ ] **S2.6.1** Implementa `src/agents/writer.py`:
  - Model: `anthropic/claude-opus-4-5` (§28)
  - Input: `section_scope`, `compressed_corpus`, `citation_map`, `style_exemplar`, `writer_memory`
  - Output: `draft`, `word_count`, `citations_used`
  - **Prompt caching già attivo** (da S1.1.2)
- [ ] **S2.6.2** Constraint checks:
  - Word count: `target_words ± 15%`
  - Citations only from `citation_map`
  - No claims absent from corpus
- [ ] **S2.6.3** Prompt template:
  - System: style rules + exemplar + writer memory (cached blocks)
  - User: section scope + compressed corpus
- [ ] **S2.6.4** Unit test: mock LLM, verifica prompt structure
- [ ] **S2.6.5** Integration test: generate 3 drafts, verifica word count ±15%

#### S2.7 — MetricsCollector (`§5.8`)
- [ ] **S2.7.1** Implementa `src/agents/metrics_collector.py`:
  - Flesch-Kincaid grade via `textstat`
  - Citation coverage ratio
  - Plagiarism similarity (cosine sim vs sources)
  - Draft embedding via `sentence-transformers/all-MiniLM-L6-v2`
- [ ] **S2.7.2** Unit test: 5 drafts, verifica tutte metriche popolate
- [ ] **S2.7.3** Integration test: append embedding a `DocumentState.draft_embeddings`

**Deliverable Sprint 2:**
- ✅ Pipeline Researcher → Citation* → Sanitizer → Synthesizer → Writer funzionante
- ✅ Writer genera draft 1000 parole ±15% da query "machine learning applications"
- ✅ MetricsCollector computa embedding + plagiarism score
- ✅ Test suite green: 50+ unit tests + 10 integration tests

**Effort:** 2 settimane × 2 dev

---

## Sprint 3: Jury System + Aggregator (Settimana 7-8)

### Obiettivo
Implementare §8 Jury (3 mini-juries R/F/S) + §9 Aggregator + §10 Minority Veto.

### Task List

#### S3.1 — Judge Base Class
- [ ] **S3.1.1** Implementa `src/agents/jury_base.py`:
  - Abstract class `Judge` con metodo `evaluate(draft, sources) -> JudgeVerdict`
  - Verdict schema: `pass_fail`, `veto_category`, `confidence`, `motivation`, `failed_claims`, `css_contribution`
- [ ] **S3.1.2** Cascading model fallback chain (§28):
  - Tier 1: `qwen/qwq-32b-preview`, `meta/llama-3.3-70b`
  - Tier 2: `openai/o3-mini`, `google/gemini-2.5-flash`
  - Tier 3: `openai/o3`, `google/gemini-2.5-pro`

#### S3.2 — Judge R (Reasoning)
- [ ] **S3.2.1** Implementa `src/agents/judge_r.py`:
  - 3 instances: R1, R2, R3
  - Model: `openai/o3` (Premium), `openai/o3-mini` (Balanced), `qwen/qwq-32b` (Economy)
  - Evaluation: logical consistency, argument structure
- [ ] **S3.2.2** Prompt template `prompts/judge_r.txt`:
  - System: reasoning rubric (cached)
  - User: draft + section scope
- [ ] **S3.2.3** Unit test: 5 drafts con errori logici noti, verifica detection

#### S3.3 — Judge F (Factual)
- [ ] **S3.3.1** Implementa `src/agents/judge_f.py`:
  - 3 instances: F1, F2, F3
  - Model: `openai/o3` (Premium), `google/gemini-2.5-pro` (Balanced/Economy)
  - Micro-search via Perplexity Sonar per falsification (§8.3)
- [ ] **S3.3.2** Falsification loop:
  - Extract factual claims da draft
  - Query Sonar con claim + "is this true?"
  - Compare con sources → flag contradiction
- [ ] **S3.3.3** Unit test: draft con claim fabricato, verifica `veto_category: "fabricated_source"`
- [ ] **S3.3.4** Integration test: micro-search API real call

#### S3.4 — Judge S (Style)
- [ ] **S3.4.1** Implementa `src/agents/judge_s.py`:
  - 3 instances: S1, S2, S3
  - Model: `google/gemini-2.5-pro` (Premium/Balanced), `meta/llama-3.3-70b` (Economy)
  - Evaluation: adherence to style profile (§26)
- [ ] **S3.4.2** Inject style rules + exemplar (cached)
- [ ] **S3.4.3** Unit test: draft con L1 violation, verifica detection

#### S3.5 — Jury Orchestrator
- [ ] **S3.5.1** Implementa `src/agents/jury.py`:
  - Parallel execution: `asyncio.gather(judge_r.evaluate(), judge_f.evaluate(), judge_s.evaluate())`
  - Per mini-jury: 1-3 judges based on `budget.jury_size` (§19.2)
- [ ] **S3.5.2** Cascading logic:
  - Tier 1 always runs (9 calls: 3 judges × 3 mini-juries)
  - Tier 2 only if disagreement within mini-jury (40% of cases)
  - Tier 3 only if Tier 2 disagrees (raro)
- [ ] **S3.5.3** Integration test: 10 drafts, misura jury latency < 12s (parallelo)

#### S3.6 — Aggregator (`§9`)
- [ ] **S3.6.1** Implementa `src/agents/aggregator.py`:
  - CSS formula:
    ```python
    css_content = (sum(R_scores) * 0.35 + sum(F_scores) * 0.50 + sum(S_scores) * 0.15) / jury_size
    css_style = sum(S_scores) / jury_size
    css_final = css_content * 0.70 + css_style * 0.30
    ```
  - Two-gate approval:
    - `css_content ≥ budget.css_threshold` (0.65/0.70/0.78)
    - `css_style ≥ 0.80` (always)
- [ ] **S3.6.2** Routing logic (`route_after_aggregator` §9.4):
  - `APPROVED` → context_compressor
  - `FAIL_REFLECTOR` → reflector
  - `FAIL_STYLE` → style_fixer
  - `PANEL` → panel_discussion
  - `VETO` → reflector
  - `FAIL_MISSING_EV` → researcher_targeted
  - `BUDGET_HARDSTOP` → publisher (partial doc)
  - **`FORCE_APPROVE`** → checked FIRST, routes to context_compressor with WARNING
- [ ] **S3.6.3** Unit test: 20 verdicts combinations, verifica routing corretto

#### S3.7 — Minority Veto (`§10`)
- [ ] **S3.7.1** Implementa veto L1 (individual judge):
  - Se qualunque judge ha `veto_category != None` → `VETO` route
  - Blocca approval anche con CSS alto
- [ ] **S3.7.2** Implementa veto L2 (unanimous mini-jury):
  - Se tutti 3 judges di una mini-jury votano `pass_fail: False` → `VETO`
- [ ] **S3.7.3** Rogue judge detection (§10.3):
  - Track judge disagreements per sezione
  - Se giudice vota contrario 3+ volte consecutive → flag + temporary replacement
- [ ] **S3.7.4** Unit test: 5 scenari veto, verifica override CSS

**Deliverable Sprint 3:**
- ✅ Jury system completo: 9 judges (R1-R3, F1-F3, S1-S3) paralleli
- ✅ Aggregator route correttamente basato su CSS + veto
- ✅ Minority veto L1/L2 funzionanti
- ✅ Integration test: draft → jury → aggregator → route in <15s

**Effort:** 2 settimane × 2 dev

---

## Sprint 4: Reflector + MoW + StyleLinter (Settimana 9-10)

### Obiettivo
Implementare §12 Reflector + §7 MoW + §5.9-5.10 Style pipeline.

### Task List

#### S4.1 — StyleLinter (`§5.9`)
- [ ] **S4.1.1** Implementa `src/agents/style_linter.py`:
  - Deterministic regex scan
  - L1 FORBIDDEN patterns (case-insensitive)
  - L2 REQUIRED elements (absence = violation)
  - Universal forbidden list (§26.9)
- [ ] **S4.1.2** Output: `violations: list[StyleViolation]`, `linter_pass: bool`
- [ ] **S4.1.3** Unit test: 10 drafts con known violations, verifica detection 100%

#### S4.2 — StyleFixer (`§5.10`)
- [ ] **S4.2.1** Implementa `src/agents/style_fixer.py`:
  - Model: `anthropic/claude-sonnet-4`
  - Input: draft + violations
  - Output: fixed_draft + unfixable_violations
  - Max 2 iterations: fix → re-lint → fix (se necessario)
- [ ] **S4.2.2** Constraint: preserve facts, numbers, citations
- [ ] **S4.2.3** Unit test: draft con 5 fixable violations, verifica fix + re-lint pass
- [ ] **S4.2.4** Integration test: violation → fixer → linter → aggregator

#### S4.3 — Reflector (`§5.14`)
- [ ] **S4.3.1** Implementa `src/agents/reflector.py`:
  - Model: `openai/o3`
  - Input: `all_verdicts_history`, `current_draft`, `css_history`, `iteration`
  - Output: `feedback: list[ReflectorFeedback]`, `scope: Scope`
- [ ] **S4.3.2** Scope logic:
  - `SURGICAL`: ≤4 isolated spans AND iteration ≤2
  - `FULL`: argument structure broken → human escalation
  - `PARTIAL`: default
- [ ] **S4.3.3** Conflict resolution: higher severity wins, tie → Judge F wins
- [ ] **S4.3.4** Unit test: 5 verdict histories, verifica scope assignment
- [ ] **S4.3.5** Integration test: reflector → route_after_reflector → span_editor / writer / await_human

#### S4.4 — SpanEditor (`§5.12`)
- [ ] **S4.4.1** Implementa `src/agents/span_editor.py`:
  - Model: `anthropic/claude-sonnet-4`
  - Input: draft + spans (max 4, SURGICAL only)
  - Output: replacements + unfixable_span_ids
- [ ] **S4.4.2** Respect `replacement_length_hint`: SHORTER/SAME/LONGER
- [ ] **S4.4.3** DiffMerger node (deterministic):
  ```python
  def apply_edits(draft: str, edits: list[dict]) -> str:
      sorted_edits = sorted(edits, key=lambda e: draft.rfind(e['original']), reverse=True)
      for edit in sorted_edits:
          if draft.count(edit['original']) != 1:
              raise ValueError(f"Ambiguous span: {edit['original'][:40]}")
          draft = draft.replace(edit['original'], edit['replacement'], 1)
      return draft
  ```
- [ ] **S4.4.4** Unit test: 4 spans, verifica replace + re-lint
- [ ] **S4.4.5** Integration test: SURGICAL scope → span_editor → diff_merger → style_linter

#### S4.5 — Mixture-of-Writers (`§7`)
- [ ] **S4.5.1** Implementa `src/agents/mow_writers.py`:
  - 3 Writer instances paralleli: W-A, W-B, W-C
  - Angles:
    - **W-A (Coverage):** temp=0.3, focus breadth
    - **W-B (Argumentation):** temp=0.6, focus logic
    - **W-C (Readability):** temp=0.8, focus clarity
  - Model: tutti `anthropic/claude-opus-4-5` (§28)
- [ ] **S4.5.2** Activation condition (§7.1):
  - Preset ≠ Economy
  - Section ≥400 words
  - Iteration = 1
  - No human intervention pending
- [ ] **S4.5.3** Unit test: verifica 3 drafts diversi generati in parallelo

#### S4.6 — JuryMultiDraft (`§7.5`)
- [ ] **S4.6.1** Implementa `src/agents/jury_multidraft.py`:
  - Evaluate W-A, W-B, W-C in parallelo
  - Output: `css_individual: list[float]`, `best_elements: list[dict]`
  - Non registra CSS in `css_history` (solo Fusor post-fusion)
- [ ] **S4.6.2** Veto handling: se draft ha `veto_category: "fabricated_source"` → exclude da Fusor
- [ ] **S4.6.3** Integration test: MoW → jury_multidraft → fusor

#### S4.7 — Fusor (`§5.13`)
- [ ] **S4.7.1** Implementa `src/agents/fusor.py`:
  - Model: `openai/o3`
  - Input: 3 drafts + css_individual + best_elements
  - Output: fused_draft
  - Base: draft con CSS più alto (tie-break: Judge F CSS)
- [ ] **S4.7.2** Integrate `best_elements` genuinamente (non append)
- [ ] **S4.7.3** Unit test: 3 drafts mock, verifica fusion usa base corretto
- [ ] **S4.7.4** Integration test: MoW → jury_multidraft → fusor → post_draft_analyzer

**Deliverable Sprint 4:**
- ✅ Reflector genera feedback SURGICAL/PARTIAL/FULL
- ✅ SpanEditor + DiffMerger applicano edit isolati
- ✅ MoW genera 3 drafts paralleli, Fusor li sintetizza
- ✅ StyleLinter + StyleFixer pipeline completa
- ✅ Integration test: iter 2 con FAIL_REFLECTOR → reflector → span_editor → jury → APPROVED

**Effort:** 2 settimane × 2 dev

---

## Sprint 5: Budget Controller + Panel + LangGraph (Settimana 11-12)

### Obiettivo
Completare §19 Budget Controller + §11 Panel Discussion + §4 LangGraph orchestration.

### Task List

#### S5.1 — BudgetEstimator (`§19.1`)
- [ ] **S5.1.1** Implementa `src/budget/estimator.py`:
  - Formula `estimate_run_cost()` (§19.0)
  - Deriva regime: Economy/Balanced/Premium da `budget_per_word`
  - Blocca run se `estimated_total > max_budget * 0.80`
- [ ] **S5.1.2** Unit test: 5 outline diversi, verifica stima ±20%
- [ ] **S5.1.3** Integration test: outline 10 sezioni → budget estimator → blocked se > cap

#### S5.2 — RealTimeCostTracker (`§19.3`)
- [ ] **S5.2.1** Implementa `src/budget/tracker.py`:
  - Update `BudgetState` dopo ogni LLM call
  - Write `CostEntry` a PostgreSQL `costs` table
  - Redis `INCRBYFLOAT run:{docid}:spent_usd`
- [ ] **S5.2.2** Alarm thresholds:
  - 70% → `BUDGET_WARN70` → downgrade Writer fallback, jury_size -1
  - 90% → `BUDGET_ALERT90` → force Economy params
  - 100% → `BUDGET_HARDSTOP` → save checkpoint, return partial doc
- [ ] **S5.2.3** Unit test: mock LLM calls, verifica alarms fired at thresholds

#### S5.3 — BudgetController Node (`§19.5`)
- [ ] **S5.3.1** Implementa `src/budget/controller.py`:
  - Pass-through node prima di ogni Writer/Jury call
  - Legge `budget.spent` vs `budget.max`
  - Applica `apply_dynamic_savings()` (§19.4)
- [ ] **S5.3.2** Integration test: run con budget basso → verifica downgrade automatico

#### S5.4 — Panel Discussion (`§11`)
- [ ] **S5.4.1** Implementa `src/agents/panel_discussion.py`:
  - 3 judges paralleli: `google/gemini-2.5-pro`, `meta/llama-3.3-70b`, `anthropic/claude-sonnet-4`
  - Max 2 rounds
  - Anonymized log di discussione
- [ ] **S5.4.2** Activation: `css_content < 0.50` (§9.5)
- [ ] **S5.4.3** Routing:
  - After round 1: se consensus → aggregator, else → round 2
  - After round 2: aggregator (forced)
- [ ] **S5.4.4** Unit test: draft con CSS=0.45 → panel → 2 rounds → aggregator
- [ ] **S5.4.5** Integration test: panel parallelizzato (da S1.3.3) < 35s

#### S5.5 — LangGraph Builder (`§4.5`)
- [ ] **S5.5.1** Implementa `src/graph/builder.py`:
  - `build_graph(checkpointer) -> CompiledGraph`
  - Registra tutti nodi da `NODES` list
  - Aggiungi edge conditions da `src/graph/edges.py`
- [ ] **S5.5.2** Conditional edges:
  - `route_after_aggregator()` (§9.4) — 8 outcomes
  - `route_after_reflector()` (§12.5) — 3 scopes
  - `route_mow()` — MoW vs single
  - `route_budget()` — continue vs hardstop
  - `route_after_coherence()` — noconflict/soft/hard
  - `route_next_section()` — next vs alldone
- [ ] **S5.5.3** Phase A edges: `preflight → budget_estimator → planner → await_outline`
- [ ] **S5.5.4** Phase B edges:
  - Research pipeline: `researcher → citation_manager → citation_verifier → source_sanitizer → source_synthesizer`
  - MoW branch: `source_synthesizer →[mow]→ writer_a/b/c → jury_multidraft → fusor → post_draft_analyzer`
  - Single branch: `source_synthesizer →[single]→ writer_single → post_draft_analyzer`
  - Jury path: `metrics_collector → style_linter → budget_controller → jury → aggregator`
  - Reflector path: `aggregator →[fail_reflector]→ reflector → oscillation_check → writer_single`
  - Surgical path: `reflector →[surgical]→ span_editor → diff_merger → style_linter`
  - Section approval: `context_compressor → coherence_guard → section_checkpoint`
- [ ] **S5.5.5** Phase C edges: `post_qa → publisher`
- [ ] **S5.5.6** Phase D edges: `publisher → END`
- [ ] **S5.5.7** Unit test: verifica tutti 50+ nodi presenti nel graph
- [ ] **S5.5.8** Integration test: graph serialization → JSON → deserialize

#### S5.6 — DocumentState Schema (`§4.6`)
- [ ] **S5.6.1** Implementa `src/graph/state.py`:
  - Full `DocumentState` TypedDict da spec §4.6
  - Include bounded fields da §29.5
- [ ] **S5.6.2** Unit test: verifica Pydantic validation su tutti campi

#### S5.7 — OscillationDetector (`§5.15`)
- [ ] **S5.7.1** Implementa `src/agents/oscillation_detector.py`:
  - CSS oscillation: `variance(css_history[-4:]) < 0.05`
  - Semantic oscillation: `cosine_sim(draft_N, draft_N-2) > 0.85`
  - Whack-a-mole: error categories rotate 3+ iterations
- [ ] **S5.7.2** Early warning: window-1 observations
- [ ] **S5.7.3** Unit test: 4 CSS sequences, verifica detection
- [ ] **S5.7.4** Integration test: oscillation → escalate_human

#### S5.8 — ContextCompressor (`§5.16`)
- [ ] **S5.8.1** Implementa `src/agents/context_compressor.py`:
  - Model: `qwen/qwen3-7b`
  - Position-based strategy:
    - `idx in [current-1, current-2]` → verbatim
    - `idx in [current-3, current-5]` → structured summary 80-120 words
    - `idx < current-5` → thematic extract
  - Preserve `load_bearing_claims` (referenced in future scopes)
- [ ] **S5.8.2** Budget: fit within `context_budget_tokens` (§14 MECW formula)
- [ ] **S5.8.3** Unit test: 10 approved sections → compressed context < 4000 tokens

#### S5.9 — CoherenceGuard (`§5.17`)
- [ ] **S5.9.1** Implementa `src/agents/coherence_guard.py`:
  - Model: `google/gemini-2.5-flash`
  - Detect SOFT vs HARD conflicts
  - Compare new section vs all approved sections
- [ ] **S5.9.2** Unit test: 2 sections con hard conflict, verifica detection
- [ ] **S5.9.3** Integration test: coherence_guard → hard conflict → await_human

**Deliverable Sprint 5:**
- ✅ Budget Controller attivo: alarm 70%/90%/100% funzionanti
- ✅ Panel Discussion completato con 2 rounds max
- ✅ LangGraph completo: 50+ nodi, 80+ edges
- ✅ Integration test end-to-end: topic → outline → 3 sezioni → approved → output DOCX

**Effort:** 2 settimane × 2 dev

---

## Sprint 6: Phase C/D + Shine Integration (Settimana 13-14)

### Obiettivo
Completare Phase C (Post-QA) + Phase D (Publisher) + §17/§30 Shine Integration.

### Task List

#### S6.1 — PostQA Agent (`§4.3`)
- [ ] **S6.1.1** Implementa `src/agents/post_qa.py`:
  - ContradictionDetector: cross-section conflicts
  - FormatValidator: word count vs target ±10%
  - CompletenessCheck: all outline sections present
- [ ] **S6.1.2** Routing:
  - `length_out_of_range` → length_adjuster
  - `conflicts` → await_human
  - `ok` → publisher
- [ ] **S6.1.3** Unit test: 10 assembled docs, verifica detection conflicts

#### S6.2 — LengthAdjuster (`§5.22`)
- [ ] **S6.2.1** Implementa `src/agents/length_adjuster.py`:
  - Direct Writer call con explicit word count instruction
  - Bypass jury/reflector loop (Phase C, no verdicts_history available)
- [ ] **S6.2.2** Unit test: doc 20% over target → adjuster → within ±10%

#### S6.3 — Publisher (`§5.19`)
- [ ] **S6.3.1** Implementa `src/agents/publisher.py`:
  - Assemble approved sections from PostgreSQL `sections` table
  - Generate TOC (python-docx Heading styles)
  - Append bibliography
  - Output formats: DOCX (primary), PDF, Markdown, JSON, LaTeX, HTML
- [ ] **S6.3.2** DOCX template: `templates/default.docx` con headers/footers
- [ ] **S6.3.3** S3/MinIO upload: `output/{docid}/document.{format}`
- [ ] **S6.3.4** Metadata: embed `run_metrics` in JSON format in all outputs
- [ ] **S6.3.5** Unit test: 5 approved sections → DOCX file valid
- [ ] **S6.3.6** Integration test: full pipeline → DOCX uploaded to MinIO

#### S6.4 — FeedbackCollector (`§5.20`)
- [ ] **S6.4.1** Implementa `src/agents/feedback_collector.py`:
  - REST endpoint `/api/feedback` (POST)
  - Input: `run_id`, `section_ratings`, `error_highlights`, `style_feedback`
  - Persist to PostgreSQL `feedback` table
- [ ] **S6.4.2** Source blacklist update: immediate effect on subsequent runs
- [ ] **S6.4.3** Prompt improvement signal: avg rating <3.0 → flag agent for tuning
- [ ] **S6.4.4** Unit test: POST feedback → verify DB row

#### S6.5 — Shine Integration (`§17`, `§30`)
- [ ] **S6.5.1** Review specs:
  - `docs/17_shine_infrastructure.md` (connectors)
  - `docs/30_shine_integration.md` (orchestration)
- [ ] **S6.5.2** Implementa connectors:
  - `src/connectors/shine.py`:
    - Tavily API wrapper
    - Brave Search API wrapper
    - BeautifulSoup scraper fallback
  - Diversity scoring (§17.8)
- [ ] **S6.5.3** Integration test: Researcher usa Shine connectors in cascade

#### S6.6 — SectionCheckpoint (`§5.21`)
- [ ] **S6.6.1** Implementa `src/agents/section_checkpoint.py`:
  - INSERT into PostgreSQL `sections` table
  - Atomically: content + verdicts_history + css_breakdown
  - Update `writer_memory` via `update_writer_memory()`
  - Increment `current_section_idx`
  - Emit SSE event `SECTION_APPROVED`
- [ ] **S6.6.2** Idempotency: unique constraint `(document_id, section_index, version)`
- [ ] **S6.6.3** Error handling: retry 3× with backoff, escalate on failure
- [ ] **S6.6.4** Unit test: mock DB, verify INSERT + state update
- [ ] **S6.6.5** Integration test: approved section → checkpoint → next section starts

#### S6.7 — WriterMemory (`§5.18`)
- [ ] **S6.7.1** Implementa `src/agents/writer_memory.py`:
  - Accumulator (no LLM)
  - Track:
    - `recurring_errors`: forbidden patterns count ≥2
    - `technical_glossary`: term → canonical form
    - `style_drift_index`: cosine distance between section embeddings
    - `citation_tendency`: under/normal/over
  - Output: `proactive_warnings` injected into Writer prompt
- [ ] **S6.7.2** Unit test: 5 sections con recurring errors, verifica accumulation
- [ ] **S6.7.3** Integration test: writer_memory → Writer prompt → draft avoids errors

**Deliverable Sprint 6:**
- ✅ Phase C completa: PostQA + LengthAdjuster
- ✅ Phase D completa: Publisher genera DOCX + PDF + Markdown
- ✅ Shine connectors integrati: Tavily + Brave + Scraper
- ✅ SectionCheckpoint + WriterMemory funzionanti
- ✅ Integration test: full pipeline A-D su topic reale → DOCX uploaded to MinIO

**Effort:** 2 settimane × 2 dev

---

## Sprint 7: Testing + QA + Monitoring (Settimana 15-16)

### Obiettivo
Test suite completa + regression tests + monitoring production-grade.

### Task List

#### S7.1 — Unit Test Coverage
- [ ] **S7.1.1** Target: ≥80% coverage su tutti i moduli
- [ ] **S7.1.2** Coverage report: `pytest --cov=src --cov-report=html`
- [ ] **S7.1.3** CI enforcement: blocca PR se coverage < 80%

#### S7.2 — Integration Tests
- [ ] **S7.2.1** Test suite `tests/integration/`:
  - `test_phase_a.py`: Planner → outline approval
  - `test_phase_b_single.py`: Research → Writer → Jury → APPROVED (no MoW)
  - `test_phase_b_mow.py`: MoW → Fusor → Jury → APPROVED
  - `test_phase_b_reflector.py`: FAIL_REFLECTOR → Reflector → Writer → APPROVED
  - `test_phase_b_panel.py`: CSS<0.50 → Panel → 2 rounds → aggregator
  - `test_phase_c.py`: PostQA → conflicts → await_human
  - `test_phase_d.py`: Publisher → DOCX/PDF output
  - `test_budget_hardstop.py`: budget exhausted → partial doc
  - `test_oscillation.py`: CSS oscillation → escalate_human
  - `test_veto.py`: Minority veto L1/L2 → reflector
- [ ] **S7.2.2** Parametrized tests: 3 preset (Economy/Balanced/Premium) × 5 topics = 15 full runs
- [ ] **S7.2.3** Timeout: max 10min per test (abort se supera)

#### S7.3 — Regression Tests
- [ ] **S7.3.1** Budget regression:
  - Golden dataset: 10 run con costo noto
  - Test: estimate vs actual ±20%
  - Blocca PR se degrado >10%
- [ ] **S7.3.2** Quality regression:
  - Golden dataset: 10 run con CSS noto
  - Test: CSS attuale vs baseline ±5%
  - Blocca PR se CSS scende >5%
- [ ] **S7.3.3** Latency regression:
  - Golden dataset: 10 run con latency noto
  - Test: latency attuale vs baseline ±15%
  - Alert se supera (non blocca)

#### S7.4 — Stress Tests
- [ ] **S7.4.1** Long document: 50 sezioni, 50k parole → verify no memory leak
- [ ] **S7.4.2** Concurrent runs: 10 run paralleli → verify no race conditions
- [ ] **S7.4.3** Budget exhaustion: cap $10 → verify graceful partial doc
- [ ] **S7.4.4** Network failures: mock connector down → verify cascade fallback

#### S7.5 — Monitoring Production
- [ ] **S7.5.1** Prometheus metrics (già definite in S0.4.3):
  - Aggiungi:
    - `drs_section_iterations{section}` — Histogram
    - `drs_jury_rejection_rate` — Gauge (0.0-1.0)
    - `drs_panel_trigger_rate` — Gauge (0.0-1.0)
    - `drs_oscillation_detected_total` — Counter
    - `drs_veto_fired_total{level}` — Counter (L1/L2)
- [ ] **S7.5.2** Grafana dashboard update:
  - Row "Quality Metrics":
    - CSS mean/P50/P95 by section (line)
    - Jury rejection rate trend (area)
    - Panel trigger frequency (bar)
  - Row "Budget Tracking":
    - Budget spent vs cap (gauge)
    - Cost per section (bar)
    - Alarm history (events)
  - Row "Performance":
    - Latency by phase (stacked area)
    - Agent call distribution (pie)
    - Cache hit rate (line)

#### S7.6 — Alerting
- [ ] **S7.6.1** Prometheus Alertmanager rules:
  - `BudgetExhausted`: `drs_budget_spent_usd ≥ max_budget` → Slack/email
  - `HighRejectionRate`: `drs_jury_rejection_rate > 0.50` for 1h → Slack
  - `CacheHitRateLow`: `drs_cache_hit_rate{agent="writer"} < 0.60` for 30min → Slack
  - `LatencyP95High`: `drs_agent_latency_seconds{quantile="0.95"} > 60` for 15min → Slack
- [ ] **S7.6.2** Slack webhook integration
- [ ] **S7.6.3** Email alerting per critical alerts

#### S7.7 — Logging
- [ ] **S7.7.1** Structured logging: JSON format
- [ ] **S7.7.2** Log levels:
  - `INFO`: section approved, phase transition
  - `WARNING`: budget alarm, early oscillation warning
  - `ERROR`: LLM API error, DB error
  - `CRITICAL`: budget hardstop, security event
- [ ] **S7.7.3** Log aggregation: Loki + Grafana (opzionale, se deployment Kubernetes)

#### S7.8 — Documentation
- [ ] **S7.8.1** `docs/DEPLOYMENT.md`:
  - Requisiti infra
  - Docker Compose setup
  - Environment variables
  - Database migrations
- [ ] **S7.8.2** `docs/API.md`:
  - REST endpoints
  - Request/response schemas
  - Authentication
- [ ] **S7.8.3** `docs/MONITORING.md`:
  - Metriche Prometheus
  - Dashboard Grafana
  - Alert rules
- [ ] **S7.8.4** `docs/TROUBLESHOOTING.md`:
  - Common errors + solutions
  - Debug checklist

**Deliverable Sprint 7:**
- ✅ Test coverage ≥80%
- ✅ 15 integration tests green (3 preset × 5 topics)
- ✅ Regression tests in CI
- ✅ Monitoring dashboard completo
- ✅ Alerting attivo su Slack
- ✅ Documentation completa

**Effort:** 2 settimane × 2 dev + 1 QA

---

## Sprint 8: Production Hardening + §29 Advanced (Settimana 17-18)

### Obiettivo
Security audit + §29.3 Model Tiering + §29.7 Distilled Judges (opzionale).

### Task List

#### S8.1 — Security Audit
- [ ] **S8.1.1** OWASP LLM Top 10 testing:
  - Prompt injection (§5.5 SourceSanitizer)
  - Insecure output handling
  - Training data poisoning (N/A, no fine-tuning)
  - Model DoS (rate limiting)
  - Supply chain vulnerabilities
  - Sensitive information disclosure
- [ ] **S8.1.2** Dependency audit: `pip-audit` + `safety check`
- [ ] **S8.1.3** Secrets scan: `gitleaks` + `trufflehog`
- [ ] **S8.1.4** Fix: tutte le vulnerabilità CRITICAL/HIGH

#### S8.2 — §29.3 Model Tiering
- [ ] **S8.2.1** Implementa `src/llm/routing.py`:
  - `MODEL_ROUTING_TABLE` da YAML config
  - Per ogni agent: `economy_model`, `balanced_model`, `premium_model`
  - Routing logic: `route_model(agent, preset) -> model_name`
- [ ] **S8.2.2** Config `config/model_routing.yaml`:
  ```yaml
  writer:
    economy: anthropic/claude-sonnet-4
    balanced: anthropic/claude-opus-4-5
    premium: anthropic/claude-opus-4-5
  jury_r:
    economy: qwen/qwq-32b-preview
    balanced: openai/o3-mini
    premium: openai/o3
  jury_f:
    economy: google/gemini-2.5-pro
    balanced: google/gemini-2.5-pro
    premium: openai/o3
  panel:
    economy: meta/llama-3.3-70b  # self-hosted
    balanced: google/gemini-2.5-pro
    premium: google/gemini-2.5-pro
  ```
- [ ] **S8.2.3** Fallback chain: Economy → Balanced → Premium on error
- [ ] **S8.2.4** Test A/B: 100 run Economy vs Premium:
  - Compare CSS delta (target: <3% degrado)
  - Compare cost (target: -55%)
- [ ] **S8.2.5** Blocca deploy se CSS degrado >3%

#### S8.3 — §29.2 Speculative Decoding (opzionale)
- [ ] **S8.3.1** Setup infra: SGLang o vLLM server
- [ ] **S8.3.2** Deploy draft model: `google/gemini-2.5-flash` (Writer), `meta/llama-3.3-70b` (Jury)
- [ ] **S8.3.3** Implementa speculative client wrapper:
  ```python
  def speculative_generate(draft_model, target_model, prompt, n_speculative=5):
      draft_tokens = draft_model.generate(prompt, max_tokens=n_speculative)
      verified = target_model.verify_batch(draft_tokens)
      return verified
  ```
- [ ] **S8.3.4** Integration test: Writer con speculative decoding → 2.3× speedup
- [ ] **S8.3.5** Deployment complexity: ~1 settimana, solo se latency è bottleneck critico

#### S8.4 — §29.7 Distilled Judges (opzionale)
- [ ] **S8.4.1** Colleziona dataset teacher:
  - 500 run Premium
  - Extract verdicts: `(draft, sources) → (pass_fail, css_contribution, motivation)`
- [ ] **S8.4.2** Fine-tune student models:
  - Base: `meta/llama-3.2-3b`
  - 3 modelli: `DistilJudge-R-3B`, `DistilJudge-F-3B`, `DistilJudge-S-3B`
  - Target: 95% accuracy retention
- [ ] **S8.4.3** Deploy su modal.com o Runpod (self-hosted)
- [ ] **S8.4.4** Test accuracy: held-out set 100 drafts → verify ≥95% agreement con o3
- [ ] **S8.4.5** Routing: Economy preset → DistilJudge-*, Balanced/Premium → original models
- [ ] **S8.4.6** Cost analysis: Economy $4.50/run → $0.80/run (-70%)
- [ ] **S8.4.7** Effort: ~2 settimane, solo se segmento Economy è significativo (>30% users)

#### S8.5 — Performance Baseline
- [ ] **S8.5.1** Benchmark suite: 20 topic diversi × 3 preset = 60 run
- [ ] **S8.5.2** Metriche target (vs baseline senza ottimizzazioni §29):
  - **Costi:** -60% (da $150 a $60 per run 10k parole Premium)
  - **Latency Phase B:** -40% (da 45min a 27min)
  - **Cache hit rate:** ≥70% su Writer/Jury
  - **State size:** <200KB dopo 10 sezioni
- [ ] **S8.5.3** Golden dataset: commit metriche in `tests/golden/metrics.json`
- [ ] **S8.5.4** CI: regression test vs golden ±10%

#### S8.6 — Production Readiness Checklist
- [ ] **S8.6.1** ✅ All integration tests green
- [ ] **S8.6.2** ✅ Coverage ≥80%
- [ ] **S8.6.3** ✅ Security audit: zero CRITICAL/HIGH vulns
- [ ] **S8.6.4** ✅ Monitoring dashboard + alerting attivi
- [ ] **S8.6.5** ✅ Documentation completa (deployment, API, troubleshooting)
- [ ] **S8.6.6** ✅ Performance baseline: costi -60%, latency -40%
- [ ] **S8.6.7** ✅ Rollback plan: LangGraph checkpoint restore
- [ ] **S8.6.8** ✅ Incident response plan documentato

**Deliverable Sprint 8:**
- ✅ Model Tiering attivo: Economy -55% costi vs Premium
- ✅ Security audit completo: zero vulns CRITICAL/HIGH
- ✅ Production-ready: tutti i checklist items ✅
- ✅ (Opzionale) Speculative Decoding: Writer 2.3× faster
- ✅ (Opzionale) Distilled Judges: Economy $0.80/run

**Effort:** 2 settimane × 2 dev + 1 QA

---

## Post-Sprint: Deployment & Maintenance

### Deployment Kubernetes (opzionale)

#### K8s Resources
- [ ] **Namespace:** `drs-prod`
- [ ] **Deployments:**
  - `drs-api` (FastAPI app, 3 replicas)
  - `drs-workers` (Celery workers, 5 replicas)
  - `postgres` (StatefulSet, 1 replica + backup)
  - `redis` (StatefulSet, 1 replica)
  - `minio` (StatefulSet, 1 replica)
  - `prometheus` (Deployment, 1 replica)
  - `grafana` (Deployment, 1 replica)
- [ ] **Services:**
  - `drs-api-svc` (LoadBalancer, port 8000)
  - `postgres-svc` (ClusterIP, port 5432)
  - `redis-svc` (ClusterIP, port 6379)
  - `minio-svc` (ClusterIP, port 9000)
  - `prometheus-svc` (ClusterIP, port 9090)
  - `grafana-svc` (LoadBalancer, port 3000)
- [ ] **ConfigMaps:**
  - `drs-config` (model routing, style profiles)
  - `prometheus-config` (scrape configs, alert rules)
  - `grafana-dashboards` (JSON dashboards)
- [ ] **Secrets:**
  - `drs-api-keys` (Anthropic, OpenAI, Google, Perplexity, OpenRouter)
  - `postgres-credentials`
  - `minio-credentials`
- [ ] **PersistentVolumeClaims:**
  - `postgres-data` (100GB)
  - `minio-data` (500GB)
  - `prometheus-data` (50GB)

#### Helm Chart
- [ ] `helm/drs/Chart.yaml`
- [ ] `helm/drs/values.yaml` (configurazione ambiente-specific)
- [ ] `helm/drs/templates/*.yaml` (K8s resources)
- [ ] CI/CD: GitHub Actions deploy on tag push (`v*.*.*`)

### Maintenance Plan

#### Weekly
- [ ] Review Grafana dashboards: anomalie costi/latency
- [ ] Check alert history: pattern ricorrenti
- [ ] Backup PostgreSQL: dump to S3

#### Monthly
- [ ] Update dependencies: `pip list --outdated`
- [ ] Security scan: `pip-audit` + `safety check`
- [ ] Performance review: compare vs golden metrics
- [ ] Cost analysis: trend costi/run per preset

#### Quarterly
- [ ] Model evaluation: test nuovi modelli (es. Claude Opus 5, GPT-5)
- [ ] Feedback analysis: aggregate user ratings → prompt tuning
- [ ] Capacity planning: scale workers based on load

---

## Summary: ROI × Timeline

| Sprint | Settimane | Deliverable | ROI Business |
| :-- | :-- | :-- | :-- |
| **0** | 1-2 | Infra base + CI/CD | Foundation |
| **1** | 3-4 | §29 Opt immediate: -60% costi, -40% latency | ★★★★★ CRITICAL |
| **2** | 5-6 | Core agents: Planner, Researcher, Writer | ★★★★☆ |
| **3** | 7-8 | Jury system + Aggregator + Veto | ★★★★☆ |
| **4** | 9-10 | Reflector + MoW + StyleLinter | ★★★☆☆ |
| **5** | 11-12 | Budget Controller + Panel + LangGraph | ★★★★☆ |
| **6** | 13-14 | Phase C/D + Shine + Checkpoint | ★★★☆☆ |
| **7** | 15-16 | Testing + QA + Monitoring | ★★★★★ CRITICAL |
| **8** | 17-18 | Security + Model Tiering + Distilled Judges | ★★★☆☆ |

**Timeline totale:** 16-18 settimane (4-4.5 mesi)  
**Team:** 2-3 dev + 1 QA  
**Budget stimato:** €80k-120k (salari + infra)  

**Target finale:**
- ✅ Sistema DRS production-ready
- ✅ Costi operativi: $60/run (10k parole Premium) vs $150 baseline → **-60%**
- ✅ Latency Phase B: 27min vs 45min baseline → **-40%**
- ✅ Cache hit rate: ≥70%
- ✅ Test coverage: ≥80%
- ✅ Monitoring: Prometheus + Grafana + Alerting
- ✅ Security: zero CRITICAL/HIGH vulnerabilities
- ✅ Documentation: deployment, API, troubleshooting completi

---

## Next Steps

1. **Review plan** con stakeholders
2. **Approvazione budget** + hiring team
3. **Kickoff Sprint 0:** setup repo + infra (settimana prossima)
4. **Daily standup:** 15min sync, blockers resolution
5. **Sprint review:** ogni 2 settimane, demo + retrospective

**Contatti:**
- **Project Manager:** [email]
- **Tech Lead:** [email]
- **Repository:** https://github.com/lucadidomenicodopehubs/deep-research-spec/tree/struct
- **Specs docs:** `docs/*.md` in branch `struct`

---

*Piano generato: 2026-02-23*  
*Versione: 1.0*  
*Riferimenti: §1-§30 spec files + §29 Performance Optimizations*
