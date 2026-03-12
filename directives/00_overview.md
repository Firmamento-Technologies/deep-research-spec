# Direttiva 00 — Project Overview

## Pre-requisito

**Leggi SEMPRE `output/00_conflict_resolutions.md` prima di qualsiasi implementazione.**

---

## Stack Tecnologico

| Layer | Tecnologia | Versione min |
|-------|-----------|-------------|
| Orchestrazione | LangGraph | 0.2.0 |
| Backend API | FastAPI + Uvicorn | 0.111.0 / 0.30.0 |
| Validazione | Pydantic v2 | 2.7.0 |
| Database | PostgreSQL | 16.0 |
| Cache / Broker | Redis | 7.0.0 |
| Job Queue | Celery | 5.4.0 |
| File Storage | MinIO (S3-compatible) | 2024-01 |
| LLM Routing | OpenRouter API v1 | - |
| NLP | sentence-transformers, transformers (DeBERTa), textstat | 3.0 / 4.40 / 0.7 |
| Output | python-docx, weasyprint, pandoc | 1.1 / 62 / 3.2 |
| Observability | OpenTelemetry + Prometheus + Grafana + structlog | - |
| Containerizzazione | Docker Compose (dev) / Kubernetes (prod) | - |
| Python | 3.11+ | 3.11 |

Ref: `output/33_tech_stack.md` §33.1–§33.10

---

## Struttura `src/`

```
src/
├── api/
│   ├── main.py                  # FastAPI app factory
│   ├── routes/
│   │   ├── runs.py              # POST/GET/DELETE /v1/runs
│   │   ├── documents.py         # GET /v1/documents/{id}/export
│   │   ├── sources.py           # POST /v1/sources (upload)
│   │   └── presets.py           # Style preset CRUD
│   └── auth.py                  # JWT + API key (§22)
│
├── graph/
│   ├── state.py                 # DocumentState TypedDict (§04.6)
│   ├── graph.py                 # build_graph(), compile
│   ├── nodes/                   # Un file per nodo graph
│   │   ├── planner.py
│   │   ├── researcher.py
│   │   ├── citation_manager.py
│   │   ├── citation_verifier.py
│   │   ├── source_sanitizer.py
│   │   ├── source_synthesizer.py
│   │   ├── writer.py            # Include MoW/Fusor internamente
│   │   ├── post_draft_analyzer.py
│   │   ├── style_linter.py
│   │   ├── style_fixer.py
│   │   ├── metrics_collector.py
│   │   ├── jury.py              # asyncio.gather(R, F, S)
│   │   ├── aggregator.py        # CSS + routing
│   │   ├── reflector.py
│   │   ├── span_editor.py
│   │   ├── diff_merger.py
│   │   ├── oscillation_detector.py
│   │   ├── coherence_guard.py
│   │   ├── context_compressor.py
│   │   ├── writer_memory.py
│   │   ├── section_checkpoint.py
│   │   ├── budget_controller.py
│   │   ├── post_qa.py
│   │   ├── length_adjuster.py
│   │   ├── publisher.py
│   │   ├── run_companion.py
│   │   ├── feedback_collector.py
│   │   └── panel_discussion.py
│   └── routers/
│       ├── outline_approval.py  # route_outline_approval()
│       ├── post_aggregator.py   # route_after_aggregator() §9.4
│       ├── post_reflector.py    # route_after_reflector() §12.5
│       ├── post_oscillation.py  # route_after_oscillation()
│       ├── post_coherence.py    # route_after_coherence()
│       └── next_section.py      # route_next_section()
│
├── llm/
│   ├── client.py                # call_llm() wrapper + tenacity
│   ├── pricing.py               # MODEL_PRICING canonical (§28.4)
│   ├── mock_client.py           # MockLLMClient per test
│   ├── model_verifier.py        # verify_models() preflight (§28.3)
│   ├── rate_limiter.py          # ProviderSemaphore (§34.2)
│   └── circuit_breaker.py       # CLOSED/OPEN/HALF-OPEN
│
├── connectors/
│   ├── base.py                  # SourceConnector ABC
│   ├── tavily.py
│   ├── brave.py
│   ├── crossref.py
│   ├── semantic_scholar.py
│   ├── arxiv.py
│   └── scraper.py               # BS4 + Playwright fallback
│
├── storage/
│   ├── postgres.py              # SQLAlchemy async models + repos
│   ├── redis_cache.py           # TTL cache helpers
│   ├── checkpointer.py          # AsyncPostgresSaver setup
│   └── minio.py                 # S3-compatible ops
│
├── config/
│   ├── schema.py                # DRSConfig Pydantic YAML (§29.6)
│   └── settings.py              # Pydantic Settings env vars
│
├── budget/
│   ├── estimator.py             # Pre-run cost projection (§19.0)
│   ├── tracker.py               # Real-time token/cost (§19.3)
│   ├── regime.py                # REGIME_PARAMS + THRESHOLD_TABLE
│   └── thresholds.py            # populate_budget_thresholds()
│
├── workers/
│   ├── app.py                   # Celery app
│   └── tasks.py                 # execute_run task
│
├── security/
│   ├── pii_detector.py          # Presidio + spaCy
│   ├── injection_guard.py       # 3-stage source sanitization
│   └── encryption.py            # AES-256
│
├── observability/
│   ├── tracing.py               # OpenTelemetry
│   ├── metrics.py               # Prometheus
│   └── logging.py               # structlog JSON
│
└── models/
    ├── config.py                # DRSConfig API input (§03)
    ├── source.py                # Source, CitationEntry
    ├── verdict.py               # VerdictJSON, DimensionScores
    └── document.py              # API response models
```

Ref: `output/34_deployment.md` §34.4

---

## Vincoli Globali (Non-Negotiable)

Da `output/38_dev_rules.md` e `output/02_design_principles.md`:

1. **Budget-First**: MAI eseguire LLM call senza check budget preventivo
2. **Section-Granularity**: Sezioni approvate sono IMMUTABILI
3. **Dependency Injection**: Ogni agente accetta `LLMClient` come parametro, MAI import diretto
4. **Observability by Design**: Ogni LLM call emette OpenTelemetry span + Prometheus counter
5. **Zero unstructured logging**: Solo structlog JSON in produzione
6. **Async everything**: Tutte le route FastAPI `async def`; mai sync blocking
7. **Type safety**: `mypy --strict` deve passare su tutto `src/`
8. **Test before advance**: `make test-phaseN` deve passare prima di iniziare fase N+1

---

## Ordine di Implementazione (9 Fasi)

```
Fase 1: State & Types          → directives/01_state.md
Fase 2: Persistence & Storage  → directives/02_persistence.md
Fase 3: Budget & Thresholds    → directives/03_budget.md
Fase 4: Graph & Routing        → directives/04_graph.md
Fase 5: Research Pipeline      → directives/05_research.md
Fase 6: Writer & Jury          → directives/06_writer_jury.md
Fase 7: Feedback Loop          → directives/07_feedback.md
Fase 8: Output & QA            → directives/08_output.md
Fase 9: API & Integration      → directives/09_api.md
```

### Dipendenze tra Fasi

```
Fase 1 ──→ Fase 2 ──→ Fase 3 ──→ Fase 4
                                     │
                         ┌───────────┼───────────┐
                         ▼           ▼           ▼
                      Fase 5     Fase 6      Fase 7
                         │           │           │
                         └───────────┼───────────┘
                                     ▼
                                  Fase 8
                                     │
                                     ▼
                                  Fase 9
```

- Fasi 1→4 sono **sequenziali strette** (ogni fase dipende dalla precedente)
- Fasi 5, 6, 7 possono procedere **in parallelo** dopo Fase 4
- Fase 8 richiede Fasi 5+6+7 complete
- Fase 9 richiede Fase 8 completa

---

## Validazione Post-Fase

Dopo ogni fase, eseguire lo script di validazione corrispondente:

| Fase | Script di validazione | Cosa verifica |
|------|----------------------|---------------|
| 1 | `execution/validate_state.py` | Tutti i campi DocumentState presenti e tipizzati |
| 4 | `execution/run_graph_compile.py` | Il grafo LangGraph compila senza errori |
| 4 | `execution/test_routing.py` | Routing functions coprono tutti i casi edge |

---

## File Spec da NON Modificare

Tutti i file in `output/*.md` sono READ-ONLY eccetto `output/00_conflict_resolutions.md`.
Le direttive in `directives/` sono documenti vivi che possono essere aggiornati con nuove informazioni scoperte durante l'implementazione (cfr. GEMINI.md §3).
