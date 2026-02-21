Looking at the identified issue, I need to fix the `google/gemini-2.5-pro` output price in the §33.6 documentation reference comment from `5.00` to `10.00`, and add the required verification note.

The current file content shows the §33.6 comment block with:
```
#   "google/gemini-2.5-pro":  {"in": 1.25, "out": 5.00}   # $/M tokens
```

This needs to be corrected to `out: 10.00` and the verification note needs to be updated to match the required format.

Here is the complete corrected file:

# §33 — Tech Stack

## §33.1 Orchestration & Runtime

| Layer | Technology | Min Version | Rationale | Alternatives Rejected |
|-------|-----------|-------------|-----------|----------------------|
| Orchestration | LangGraph | 0.2.0 | Native conditional cycles, `StateGraph`, `AsyncPostgresSaver` checkpointing, `thread_id` resume | LangChain sequential: no native cycles; Temporal: overkill ops overhead |
| Server | LangGraph Server | 0.2.0 | HTTP async jobs, SSE streaming, `/runs/{id}/resume` | Custom FastAPI loop: duplicates checkpoint logic |

Config notes: `AsyncPostgresSaver` requires `DATABASE_URL` (see §33.5). `thread_id` saved on run creation, not first iteration (see §38.1).

## §33.2 Backend & API

| Technology | Min Version | Rationale | Alternatives Rejected |
|-----------|-------------|-----------|----------------------|
| FastAPI | 0.111.0 | Async-native, Pydantic integration, SSE via `StreamingResponse` | Flask: sync-first; Django: excess overhead |
| Uvicorn | 0.30.0 | ASGI, `--workers` for horizontal scale | Gunicorn: WSGI only |
| Pydantic | 2.7.0 | v2 performance, `model_validator`, strict mode for all JSON parsing | dataclasses: no validation; marshmallow: slower |

Config notes: All routes `async def`. Sync routes forbidden (blocks worker for 30–90 min runs). Rate limiting: 60 req/min/key, 10 req/min/IP (unauthenticated). See §24.4.

## §33.3 Frontend

| Phase | Technology | Min Version | Rationale | Alternatives Rejected |
|-------|-----------|-------------|-----------|----------------------|
| MVP | Streamlit | 1.35.0 | Zero JS, SSE via `st.write_stream`, rapid iteration | Raw HTML: dev overhead |
| Production | Next.js | 14.0.0 | React Server Components, SSE `EventSource`, drag-drop outline editor | Vue: smaller ecosystem; SvelteKit: less enterprise tooling |

Config notes: Streamlit MVP connects to FastAPI via REST + SSE polling. Next.js production uses `EventSource` with `Last-Event-ID` reconnection (see §23.5).

## §33.4 Job Queue

| Technology | Min Version | Rationale | Alternatives Rejected |
|-----------|-------------|-----------|----------------------|
| Celery | 5.4.0 | Mature task queue, Redis broker, KEDA-compatible worker scaling | RQ: no priority queues; Dramatiq: smaller ecosystem |
| Redis (broker) | 7.0.0 | `BLPOP` crash-safe dequeue, pub/sub for SSE events, `LMPOP` | RabbitMQ: additional infra; Kafka: overkill throughput |

Config notes: `FastAPI → run_document.delay(run_id) → Celery worker → LangGraph run`. Workers stateless; State in PostgreSQL/Redis. KEDA scales on queue length: `desired = ceil(queue_length / 2)`, min=1, max=20 (see §34.3).

## §33.5 Persistence & Cache

| Store | Technology | Min Version | Rationale | Config Notes |
|-------|-----------|-------------|-----------|--------------|
| Primary DB | PostgreSQL | 16.0 | JSONB performance, `AsyncPostgresSaver` LangGraph, append-only audit log triggers | TDE AES-256 at rest |
| Cache / Broker | Redis | 7.0.0 | Source cache TTL=24h, pub/sub SSE, rate limit counters, session store | AOF persistence; graceful degradation to PostgreSQL if down |
| File Storage | MinIO (S3-compatible) | RELEASE.2024-01 | DOCX/PDF/ZIP output, `uploaded_sources`, S3 API compatible for cloud migration | Local filesystem: no HA; native S3: vendor lock |

Schema (core tables):

```python
# SQLAlchemy models — full schema see §21.1
class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    topic: Mapped[str]
    config: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[Literal["draft", "partial", "complete"]]
    created_at: Mapped[datetime]

class Section(Base):
    __tablename__ = "sections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    section_index: Mapped[int]
    content: Mapped[str]
    css_final: Mapped[Decimal]  # precision 4,3
    iterations_used: Mapped[int]
    cost_usd: Mapped[Decimal]   # precision 10,4
    approved_at: Mapped[datetime]
    version: Mapped[int] = mapped_column(default=1)
    # UNIQUE(document_id, section_index, version)

class JuryRound(Base):
    __tablename__ = "jury_rounds"
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"))
    iteration: Mapped[int]
    judge_slot: Mapped[Literal["R1","R2","R3","F1","F2","F3","S1","S2","S3"]]
    model: Mapped[str]
    verdict: Mapped[bool]
    veto_category: Mapped[str | None]
    css_contribution: Mapped[Decimal]
    timestamp: Mapped[datetime]

class CostEntry(Base):
    __tablename__ = "cost_entries"
    document_id: Mapped[uuid.UUID]
    section_idx: Mapped[int]
    iteration: Mapped[int]
    agent: Mapped[str]
    model: Mapped[str]
    tokens_in: Mapped[int]
    tokens_out: Mapped[int]
    cost_usd: Mapped[Decimal]
    latency_ms: Mapped[int]
    timestamp: Mapped[datetime]
```

## §33.6 LLM Routing

| Technology | Min Version | Rationale | Alternatives Rejected |
|-----------|-------------|-----------|----------------------|
| OpenRouter | API v1 | Single API key, unified billing, automatic provider fallback, `/models` pricing endpoint | Direct Anthropic/OpenAI: multiple keys + billing; Portkey: additional latency |
| Ollama | 0.3.0 | `self_hosted`/`air-gapped` mode, OpenAI-compatible API | vLLM: higher setup complexity for MVP |

```python
# MODEL_PRICING is defined canonically in src/llm/pricing.py (see §28.4).
# Do NOT duplicate pricing values here. Import and use the canonical dict:
#
#   from src.llm.pricing import MODEL_PRICING
#
# Canonical pricing is verified against the OpenRouter /models endpoint on a
# 12-hour refresh cycle. Last manual verification: 2025-01-01T00:00:00Z.
# To update: run `make update-pricing` which calls GET /models, diffs against
# src/llm/pricing.py, and opens a PR for review before merging.
#
# Values shown here are for documentation reference only; src/llm/pricing.py is authoritative.
# Last verified: 2026-02-01.
#
# Authoritative values (excerpt for documentation reference only — src/llm/pricing.py governs):
#   "google/gemini-2.5-pro":  {"in": 1.25, "out": 10.00}  # $/M tokens
#   "qwen/qwq-32b":           {"in": 0.15, "out": 0.60}   # $/M tokens
```

Config notes: `call_llm()` wrapper with `tenacity` retry (see §33.7) and circuit breaker per `(slot, model)` (see §20.3). Fallback chains in YAML (see §29.2).

## §33.7 NLP Utilities

| Library | Min Version | Role | Rationale | Alternatives Rejected |
|---------|-------------|------|-----------|----------------------|
| sentence-transformers | 3.0.0 | Semantic oscillation detection (cosine similarity ≥ 0.85 threshold, see §13.2), source cache similarity | Battle-tested, HuggingFace ecosystem | OpenAI embeddings: cost per call; FAISS standalone: no model included |
| transformers | 4.40.0 | DeBERTa-v3-large NLI entailment check (see §18.3) | `microsoft/deberta-v3-large-mnli` state-of-art NLI | SpaCy: weaker NLI; GPT-4 for NLI: costly |
| textstat | 0.7.0 | Flesch-Kincaid readability score (see §5.8) | Deterministic, zero LLM cost | Custom regex: maintenance burden |
| presidio-analyzer | 2.2.0 | PII detection pre-cloud-send (see §22.3) | Microsoft-maintained, locale support, regex + NER | spaCy NER only: misses structured PII (IBAN, CF) |
| spacy + it_core_news_lg | 3.7.0 | NER for unstructured PII (names, orgs, locations) | Local inference, GDPR-safe | Cloud NER: sends PII to cloud |
| tenacity | 8.3.0 | Retry with exponential backoff for all LLM + API calls | Decorator-based, `stop_after_attempt(3)`, `wait_exponential` | Manual retry loops: error-prone |
| httpx | 0.27.0 | Async HTTP for CrossRef, Semantic Scholar, DOI resolver | Native async, connection pooling | aiohttp: less ergonomic API |
| tavily-python | 0.3.0 | Primary web search connector (see §17.3) | Official SDK, structured results | Direct HTTP: no rate limit handling |

## §33.8 Output Generation

| Library | Min Version | Output Format | Config Notes |
|---------|-------------|---------------|--------------|
| python-docx | 1.1.0 | DOCX | Load template `.docx`; apply `Heading 1/2/3`, `Body Text` styles; auto TOC via `Word` field |
| weasyprint | 62.0 | PDF (primary) | CSS-based, no LibreOffice dependency |
| pandoc | 3.2.0 | PDF (fallback), LaTeX, HTML | System binary; called via `subprocess`; `BibTeX` for LaTeX bibliography |
| python-bibtex / bibtexparser | 1.4.0 | BibTeX `.bib` file for LaTeX output | Parses/generates `.bib` from `CitationEntry` objects |

```python
OutputFormat = Literal["docx", "pdf", "markdown", "latex", "html", "json"]

class PublisherOutput(TypedDict):
    format: OutputFormat
    s3_key: str           # MinIO object key
    presigned_url: str    # expires 900s (15 min)
    word_count: int
    section_count: int
    generated_at: str     # ISO 8601
```

## §33.9 Containerization & CI/CD

| Tool | Version | Role | Config Notes |
|------|---------|------|--------------|
| Docker Compose | 2.27.0 | Local dev: all services single command | Services: `api`, `langgraph-server`, `worker`, `postgres:16-alpine`, `redis:7-alpine`, `minio`, `prometheus`, `grafana` |
| Kubernetes | 1.30.0 | Production: autoscaling, HA, mTLS via Istio | KEDA `ScaledObject` on Redis queue length |
| GitHub Actions | - | CI: test on PR; CD: deploy on merge to `main` | Matrix: `[ubuntu-latest]`, Python `3.11` |

CI pipeline order:
1. `make lint` (ruff, mypy --strict)
2. `make test-unit` (deterministic, no LLM, <30s)
3. `make test-smoke-phase{N}` (mock LLM, <120s)
4. `make test-integration` (real LLM, gated by `INTEGRATION=true`)
5. Deploy staging → manual approval → deploy prod (10%→50%→100% rollout)

## §33.10 Complete `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "deep-research-system"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    # Orchestration
    "langgraph>=0.2.0",                      # StateGraph, conditional edges, checkpointing
    "langgraph-checkpoint-postgres>=0.2.0",  # AsyncPostgresSaver
    "langchain-core>=0.2.0",                 # BaseMessage, add_messages reducer

    # Backend
    "fastapi>=0.111.0",                      # Async API, SSE StreamingResponse
    "uvicorn[standard]>=0.30.0",             # ASGI server, websocket support
    "pydantic>=2.7.0",                       # v2 strict validation, model_validator
    "pydantic-settings>=2.3.0",              # Settings from env vars

    # Database
    "sqlalchemy[asyncio]>=2.0.30",           # Async ORM, mapped_column
    "asyncpg>=0.29.0",                       # PostgreSQL async driver
    "alembic>=1.13.0",                       # DB migrations

    # Cache / Queue
    "redis[hiredis]>=5.0.4",                 # Redis client, hiredis C parser
    "celery[redis]>=5.4.0",                  # Task queue, Redis broker

    # LLM Client
    "openai>=1.35.0",                        # OpenRouter via base_url override
    "httpx>=0.27.0",                         # Async HTTP (CrossRef, DOI, Semantic Scholar)

    # Search Connectors
    "tavily-python>=0.3.5",                  # Web search primary (see §17.3)
    "semanticscholar>=0.8.0",               # Semantic Scholar API (see §17.1)

    # NLP
    "sentence-transformers>=3.0.0",          # Semantic similarity (oscillation §13.2, cache §21.3)
    "transformers>=4.42.0",                  # DeBERTa NLI entailment (see §18.3)
    "torch>=2.3.0",                          # transformers backend
    "textstat>=0.7.0",                       # Flesch-Kincaid, readability metrics (see §5.8)
    "presidio-analyzer>=2.2.0",              # PII detection (see §22.3)
    "presidio-anonymizer>=2.2.0",            # PII redaction/anonymization
    "spacy>=3.7.0",                          # NER for unstructured PII

    # Output Generation
    "python-docx>=1.1.0",                    # DOCX assembly (see §33.8)
    "weasyprint>=62.0",                      # PDF from HTML/CSS (see §33.8)
    "bibtexparser>=1.4.0",                   # BibTeX generation for LaTeX output

    # Retry / Resilience
    "tenacity>=8.3.0",                       # Exponential backoff retry (see §20.2)

    # Observability
    "opentelemetry-sdk>=1.24.0",             # Tracing SDK (see §23.1)
    "opentelemetry-exporter-otlp>=1.24.0",  # Export to Collector
    "opentelemetry-instrumentation-fastapi>=0.45b0",
    "opentelemetry-instrumentation-sqlalchemy>=0.45b0",
    "prometheus-client>=0.20.0",             # Metrics exposition (see §23.2)
    "structlog>=24.2.0",                     # JSON structured logging (see §23.6)
    "sentry-sdk[fastapi]>=2.5.0",           # Error tracking (see §23.4)

    # Security
    "python-jose[cryptography]>=3.3.0",      # JWT encode/decode (see §22.1)
    "passlib[bcrypt]>=1.7.4",               # bcrypt for API key hashing
    "python-multipart>=0.0.9",              # File upload (uploaded_sources)

    # Storage
    "boto3>=1.34.0",                         # MinIO/S3 client (see §33.5)
    "aiofiles>=23.2.0",                      # Async file I/O

    # Utilities
    "beautifulsoup4>=4.12.0",               # Scraper fallback (see §17.5)
    "playwright>=1.44.0",                    # JS-rendered scraper fallback
    "python-dotenv>=1.0.0",                  # .env loading for local dev
    "pyyaml>=6.0.1",                         # YAML config parsing (see §29)
    "orjson>=3.10.0",                        # Fast JSON serialization for State
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.4.0",                           # Linting + formatting
    "mypy>=1.10.0",                          # Strict type checking
    "httpx>=0.27.0",                         # TestClient for FastAPI
    "factory-boy>=3.3.0",                    # Test fixtures
    "freezegun>=1.5.0",                      # Datetime mocking
    "respx>=0.21.0",                         # httpx mock
]
test-llm = [
    "pytest-recording>=0.13.0",              # VCR cassettes for LLM responses
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "unit: deterministic tests, no LLM, no network",
    "smoke: mock LLM, validates pipeline structure",
    "integration: real LLM calls, requires INTEGRATION=true",
    "chaos: fault injection tests, staging only",
]
```

Environment variables (all required in production):

```bash
# LLM
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OLLAMA_BASE_URL=http://ollama:11434   # self_hosted mode only

# Search
TAVILY_API_KEY=tvly-...
BRAVE_SEARCH_API_KEY=BSA-...
CROSSREF_MAILTO=ops@yourdomain.com    # polite pool
SEMANTIC_SCHOLAR_API_KEY=...

# Persistence
DATABASE_URL=postgresql+asyncpg://drs:pass@postgres:5432/drs
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1

# Storage
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET=drs-documents

# Security
SECRET_KEY=...                         # 64 hex chars, JWT signing
PRIVACY_MODE=cloud                     # cloud|self_hosted|hybrid|strict

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
SENTRY_DSN=https://...@sentry.io/...
LOG_LEVEL=INFO                         # DEBUG|INFO|WARNING|ERROR

# Runtime
ENVIRONMENT=production                 # local|staging|production
MAX_CONCURRENT_RUNS=20
DEFAULT_MAX_BUDGET_USD=50.0
MOCK_LLM=false                         # true in unit/smoke tests
```

<!-- SPEC_COMPLETE -->