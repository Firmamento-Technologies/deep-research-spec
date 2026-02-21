# Direttiva 09 — API & Integration

## Obiettivo

Implementare la FastAPI application: routes REST, SSE streaming, HITL endpoints, Run Companion chat, autenticazione (JWT + API key), Celery task dispatcher, e observability layer (OpenTelemetry + Prometheus + structlog).

## Pre-requisiti

- Fase 8 completata (tutti i nodi graph funzionanti, publisher genera output)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/24_api.md` | §24.0 | Transport conventions: BASE_URL, API_VERSION, ContentType, AuthScheme |
| `output/24_api.md` | §24.1 | Auth headers (X-DRS-Key, Bearer JWT), rate limits table |
| `output/24_api.md` | §24.2 | `POST /v1/runs` — RunCreateRequest/Response, HTTP codes |
| `output/24_api.md` | §24.2 | `GET /v1/runs/{id}` — RunStatusResponse, RunProgress |
| `output/24_api.md` | §24.2 | `DELETE /v1/runs/{id}` — RunCancelResponse |
| `output/24_api.md` | §24.3 | SSE stream: 8 event types, typed payloads, reconnection via Last-Event-ID |
| `output/24_api.md` | §24.4 | HITL endpoints: POST /approve, /pause, /resume |
| `output/24_api.md` | §24.5 | GET /documents/{id}/export — 303 redirect to pre-signed URL |
| `output/24_api.md` | §24.6 | Webhook delivery: HMAC-SHA256 signature, retry policy |
| `output/06_run_companion.md` | §6.1–§6.5 | Run Companion: conversational interface during run, proactive notifications, POST /v1/runs/{id}/companion |
| `output/06_run_companion.md` | §6.2 | Allowed actions: adjust_style, add_instruction, view_progress, explain_verdict |
| `output/06_run_companion.md` | §6.4 | Run Companion prompt template |
| `output/22_security.md` | §22.1–§22.2 | JWT validation, API key format, CORS policy |
| `output/22_security.md` | §22.5 | Rate limiting implementation (Redis counters) |
| `output/23_observability.md` | §23.1–§23.3 | OpenTelemetry spans, Prometheus metrics, structlog config |
| `output/23_observability.md` | §23.4 | Grafana dashboard definitions |
| `output/23_observability.md` | §23.5 | SSE event catalog for observability |
| `output/32_ui.md` | §32.1–§32.3 | Frontend API contract (non implementare UI, solo API contract) |
| `output/34_deployment.md` | §34.1.1 | Docker Compose for dev environment |
| `output/20_error_handling.md` | §20.1–§20.5 | Error taxonomy, circuit breaker config, graceful degradation |

## Conflitti da Applicare

- **C02**: `style_profile` nel RunCreateRequest usa `StyleProfile` (nomi corti: `"academic"`, etc.)
- **C09**: `privacy_mode` nella API usa `"standard"/"enhanced"/"strict"/"self_hosted"`
- **C17**: Rimuovere `"functional_spec"` e `"technical_spec"` dal Literal della API
- **C18**: `target_words` minimo = 500 (non 1000)

## Output Atteso

### File da creare

```
src/api/main.py                  # FastAPI app factory, lifespan, middleware
src/api/auth.py                  # JWT decode + API key validation
src/api/routes/runs.py           # POST/GET/DELETE /v1/runs, GET /v1/runs/{id}/stream
src/api/routes/documents.py      # GET /v1/documents/{id}/export
src/api/routes/sources.py        # POST /v1/sources (file upload)
src/api/routes/presets.py        # Style preset CRUD
src/workers/app.py               # Celery app definition
src/workers/tasks.py             # execute_run(run_id) task
src/observability/tracing.py     # OpenTelemetry setup
src/observability/metrics.py     # Prometheus counters/histograms
src/observability/logging.py     # structlog JSON config
src/llm/client.py                # call_llm() wrapper with tenacity + OTel spans
src/llm/circuit_breaker.py       # CLOSED/OPEN/HALF-OPEN per (slot, model)
src/llm/rate_limiter.py          # ProviderSemaphore (§34.2)
src/llm/mock_client.py           # MockLLMClient for tests
src/graph/nodes/run_companion.py # Run Companion node
src/config/settings.py           # Pydantic Settings from env vars
config/prometheus.yml            # Prometheus scrape config
docker-compose.yml               # Dev environment
Makefile                         # make test-phase1 ... make deploy-staging
```

### `src/api/main.py` — Struttura richiesta

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup: DB pool, Redis client, graph compilation, OTel provider
    yield
    # Teardown: close pools

def create_app() -> FastAPI:
    app = FastAPI(title="DRS API", version="1.0.0", lifespan=lifespan)
    app.include_router(runs_router, prefix="/v1")
    app.include_router(documents_router, prefix="/v1")
    app.include_router(sources_router, prefix="/v1")
    app.include_router(presets_router, prefix="/v1")
    return app
```

### `src/api/routes/runs.py` — Endpoints

```python
@router.post("/runs", status_code=202)
async def create_run(request: RunCreateRequest, ...) -> RunCreateResponse: ...

@router.get("/runs/{run_id}")
async def get_run_status(run_id: str, ...) -> RunStatusResponse: ...

@router.delete("/runs/{run_id}")
async def cancel_run(run_id: str, purge: bool = False, ...) -> RunCancelResponse: ...

@router.get("/runs/{run_id}/stream")
async def stream_events(run_id: str, ...) -> StreamingResponse: ...

@router.post("/runs/{run_id}/approve")
async def approve_escalation(run_id: str, body: ApproveRequest, ...) -> ApproveResponse: ...

@router.post("/runs/{run_id}/pause")
async def pause_run(run_id: str, ...) -> PauseResponse: ...

@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, ...) -> ResumeResponse: ...

@router.post("/runs/{run_id}/companion")
async def companion_chat(run_id: str, ...) -> CompanionResponse: ...
```

## Script di Validazione

```bash
# Verifica che FastAPI app si importi e monti tutte le route
python -c "
from src.api.main import create_app
app = create_app()
routes = [r.path for r in app.routes]
assert '/v1/runs' in routes or any('/runs' in r for r in routes)
print(f'OK: {len(routes)} routes mounted')
"

# Verifica docker-compose
docker compose config --quiet && echo "OK: docker-compose valid"
```
