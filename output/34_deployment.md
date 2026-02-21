# §34 — Deployment & Infrastructure

## §34.1 Environments

### §34.1.1 Dev — Docker Compose

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      ENVIRONMENT: local
      MOCK_LLM: "true"
      DATABASE_URL: postgresql+asyncpg://drs:drs@postgres:5432/drs
      REDIS_URL: redis://redis:6379/0
      MINIO_URL: http://minio:9000
      MAX_CONCURRENT_RUNS: "3"
    depends_on: [postgres, redis, minio]

  langgraph-server:
    image: langchain/langgraph-api:latest
    ports: ["8123:8123"]
    environment:
      DATABASE_URL: postgresql+asyncpg://drs:drs@postgres:5432/drs
    depends_on: [postgres]

  worker:
    build: .
    command: celery -A src.workers.app worker --concurrency=4
    environment:
      ENVIRONMENT: local
      MOCK_LLM: "true"
      DATABASE_URL: postgresql+asyncpg://drs:drs@postgres:5432/drs
      REDIS_URL: redis://redis:6379/0
    depends_on: [postgres, redis]

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: drs
      POSTGRES_PASSWORD: drs
      POSTGRES_DB: drs
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: drs
      MINIO_ROOT_PASSWORD: drs_secret
    volumes:
      - minio_data:/data

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    depends_on: [prometheus]

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

**MockLLM** (`src/llm/mock_client.py`):
```python
class MockLLMClient:
    """Injected in place of real LLM client when MOCK_LLM=true. See §25.3."""
    fixtures: dict[str, str]  # agent_name -> fixed_response_json

    async def complete(self, model: str, system: str, user: str,
                       **kwargs) -> dict[str, Any]:
        agent = kwargs.get("agent", "default")
        return {
            "content": self.fixtures.get(agent, '{"verdict": "PASS"}'),
            "model_used": f"mock/{model}",
            "tokens_in": 100, "tokens_out": 50,
            "cost_usd": 0.0, "latency_ms": 10
        }
```

**Required env vars (dev)**:
```bash
ENVIRONMENT=local
MOCK_LLM=true
DATABASE_URL=postgresql+asyncpg://drs:drs@postgres:5432/drs
REDIS_URL=redis://redis:6379/0
MINIO_URL=http://minio:9000
MINIO_ACCESS_KEY=drs
MINIO_SECRET_KEY=drs_secret
SECRET_KEY=dev_secret_64chars_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LOG_LEVEL=DEBUG
```

---

### §34.1.2 Staging — Kubernetes

Real models, `max_budget_dollars` capped at `5.0` per run, anonymized data via PII pipeline (see §22.3).

```yaml
# k8s/staging/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: drs-config
  namespace: drs-staging
data:
  ENVIRONMENT: staging
  MOCK_LLM: "false"
  MAX_CONCURRENT_RUNS: "5"
  DEFAULT_MAX_BUDGET_USD: "5.0"
  LOG_LEVEL: INFO
  PRIVACY_MODE: enhanced        # forces PII detection before any LLM call
  CROSSREF_MAILTO: staging@drs.internal
---
# k8s/staging/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: drs-secrets
  namespace: drs-staging
type: Opaque
stringData:
  OPENROUTER_API_KEY: "sk-or-staging-..."
  TAVILY_API_KEY: "tvly-staging-..."
  SECRET_KEY: "staging_64char_hex..."
  DATABASE_URL: "postgresql+asyncpg://..."
  REDIS_URL: "redis://..."
```

---

### §34.1.3 Prod — Kubernetes

```yaml
# k8s/prod/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: drs-config
  namespace: drs-prod
data:
  ENVIRONMENT: production
  MOCK_LLM: "false"
  LOG_LEVEL: INFO
  PRIVACY_MODE: standard
  CROSSREF_MAILTO: ops@drs.io
---
# k8s/prod/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drs-api
  namespace: drs-prod
spec:
  replicas: 3
  selector:
    matchLabels: {app: drs-api}
  template:
    spec:
      containers:
        - name: api
          image: drs/api:latest
          resources:
            requests: {cpu: "500m", memory: "512Mi"}
            limits: {cpu: "2", memory: "2Gi"}
          envFrom:
            - configMapRef: {name: drs-config}
            - secretRef: {name: drs-secrets}
---
# k8s/prod/hpa.yaml  — HPA for worker agents
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: drs-worker-hpa
  namespace: drs-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: drs-worker
  minReplicas: 1
  maxReplicas: 20
  metrics:
    - type: External
      external:
        metric:
          name: redis_queue_length
          selector:
            matchLabels: {queue: drs-runs}
        target:
          type: AverageValue
          averageValue: "2"   # scale up: 1 worker per 2 queued jobs
---
# k8s/prod/pdb.yaml  — PodDisruptionBudget
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: drs-api-pdb
  namespace: drs-prod
spec:
  minAvailable: 2
  selector:
    matchLabels: {app: drs-api}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: drs-worker-pdb
  namespace: drs-prod
spec:
  minAvailable: 1
  selector:
    matchLabels: {app: drs-worker}
---
# k8s/prod/postgres-backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: drs-prod
spec:
  schedule: "0 * * * *"   # hourly
  successfulJobsHistoryLimit: 720   # 30d × 24h
  failedJobsHistoryLimit: 10
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:16-alpine
              command:
                - sh
                - -c
                - |
                  BACKUP_FILE="drs-$(date +%Y%m%d-%H%M%S).dump"
                  pg_dump $DATABASE_URL -Fc -f /tmp/$BACKUP_FILE
                  aws s3 cp /tmp/$BACKUP_FILE s3://$S3_BUCKET/backups/$BACKUP_FILE
                  # Prune backups older than 30d
                  aws s3 ls s3://$S3_BUCKET/backups/ | \
                    awk '{print $4}' | \
                    while read f; do
                      age=$(( ($(date +%s) - $(date -d "${f:4:8}" +%s)) / 86400 ))
                      [ $age -gt 30 ] && aws s3 rm s3://$S3_BUCKET/backups/$f
                    done
              envFrom:
                - secretRef: {name: drs-secrets}
          restartPolicy: OnFailure
```

---

## §34.2 Rate Limiting — Provider Semaphores

```python
# src/llm/rate_limiter.py
import asyncio
from dataclasses import dataclass, field
from typing import Literal

ProviderID = Literal["openrouter", "crossref", "tavily", "brave", "semantic_scholar"]

PROVIDER_LIMITS: dict[ProviderID, dict] = {
    "openrouter":       {"req_per_min": 60,  "window_s": 60},
    "crossref":         {"req_per_s": 50,    "window_s": 1},
    "tavily":           {"req_per_min": 60,  "window_s": 60},   # Retry-After honoured
    "brave":            {"req_per_s": 1,     "window_s": 1},
    "semantic_scholar": {"req_per_s": 10,    "window_s": 1},
}

@dataclass
class ProviderSemaphore:
    provider: ProviderID
    _sem: asyncio.Semaphore = field(init=False)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)
    _tokens: int = field(init=False)

    def __post_init__(self) -> None:
        cfg = PROVIDER_LIMITS[self.provider]
        capacity = cfg.get("req_per_min", cfg.get("req_per_s", 10))
        self._tokens = capacity
        self._sem = asyncio.Semaphore(capacity)

    async def acquire(self) -> None:
        await self._sem.acquire()

    def release(self) -> None:
        self._sem.release()

    async def handle_retry_after(self, retry_after_s: float) -> None:
        """Called on HTTP 429. Drains semaphore, waits, refills."""
        async with self._lock:
            await asyncio.sleep(retry_after_s)

_semaphores: dict[ProviderID, ProviderSemaphore] = {
    p: ProviderSemaphore(provider=p) for p in PROVIDER_LIMITS
}

def get_semaphore(provider: ProviderID) -> ProviderSemaphore:
    return _semaphores[provider]
```

**Usage pattern** (every external call):
```python
async def call_crossref(doi: str) -> dict:
    sem = get_semaphore("crossref")
    await sem.acquire()
    try:
        resp = await httpx_client.get(f"https://api.crossref.org/works/{doi}")
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "60"))
            await sem.handle_retry_after(retry_after)
            return await call_crossref(doi)  # single retry
        return resp.json()
    finally:
        sem.release()
```

---

## §34.3 Horizontal Scaling Strategy

Agents are **stateless Celery tasks** reading/writing exclusively via `DocumentState` in PostgreSQL (see §21). Each agent module exposes a single async function; the LangGraph node wraps it.

```
Scaling unit → Celery worker pod
Scale trigger → redis_queue_length / 2 (KEDA, see §34.1.3 HPA)
Min replicas → 1
Max replicas → 20
Scale-down delay → 300s (avoid thrashing)
State location → PostgreSQL (immutable), Redis (ephemeral cache)
Worker crash → job re-queued from last checkpoint (thread_id resume)
```

**No agent holds in-memory state between invocations.** `WriterMemory`, `css_history`, `circuit_breaker_states` live in `DocumentState` (see §4.6).

---

## §34.4 Project Directory Tree

```
deep-research-system/
├── docker-compose.yml
├── docker-compose.prod.yml
├── pyproject.toml
├── Makefile                         # make test-phase1 / make deploy-staging
│
├── k8s/
│   ├── staging/
│   │   ├── configmap.yaml
│   │   └── secret.yaml
│   └── prod/
│       ├── configmap.yaml
│       ├── api-deployment.yaml
│       ├── worker-deployment.yaml
│       ├── hpa.yaml
│       ├── pdb.yaml
│       └── postgres-backup-cronjob.yaml
│
├── config/
│   ├── settings.py                  # Pydantic Settings, loads env vars
│   ├── models_config.yaml           # MODEL_PRICING, fallback chains
│   └── prometheus.yml
│
├── prompts/
│   ├── v1/
│   │   ├── planner.md
│   │   ├── writer.md
│   │   ├── fusor.md
│   │   ├── judge_reasoning.md
│   │   ├── judge_factual.md
│   │   ├── judge_style.md
│   │   ├── reflector.md
│   │   ├── span_editor.md
│   │   ├── context_compressor.md
│   │   ├── coherence_guard.md
│   │   ├── post_draft_analyzer.md
│   │   ├── source_synthesizer.md
│   │   └── run_companion.md
│   └── v2/                          # next version under A/B test
│
├── style_presets/
│   ├── academic.yaml
│   ├── business.yaml
│   ├── technical.yaml
│   ├── blog.yaml
│   ├── software_spec.yaml
│   └── journalistic.yaml
│
├── src/
│   ├── api/
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── routes/
│   │   │   ├── runs.py
│   │   │   ├── documents.py
│   │   │   ├── sources.py
│   │   │   └── presets.py
│   │   └── auth.py                  # JWT + API key validation
│   │
│   ├── graph/
│   │   ├── state.py                 # DRSState TypedDict (see §4.6)
│   │   ├── graph.py                 # build_graph(), compile with checkpointer
│   │   ├── nodes/
│   │   │   ├── planner.py
│   │   │   ├── researcher.py
│   │   │   ├── citation_manager.py
│   │   │   ├── citation_verifier.py
│   │   │   ├── source_sanitizer.py
│   │   │   ├── source_synthesizer.py
│   │   │   ├── writer.py
│   │   │   ├── fusor.py
│   │   │   ├── jury.py
│   │   │   ├── aggregator.py
│   │   │   ├── reflector.py
│   │   │   ├── span_editor.py
│   │   │   ├── diff_merger.py
│   │   │   ├── style_linter.py
│   │   │   ├── style_fixer.py
│   │   │   ├── metrics_collector.py
│   │   │   ├── post_draft_analyzer.py
│   │   │   ├── context_compressor.py
│   │   │   ├── coherence_guard.py
│   │   │   ├── oscillation_detector.py
│   │   │   ├── writer_memory.py
│   │   │   ├── publisher.py
│   │   │   ├── run_companion.py
│   │   │   └── budget_controller.py
│   │   └── routers/
│   │       ├── outline_approval.py
│   │       ├── post_aggregator.py
│   │       ├── post_coherence.py
│   │       └── next_section.py
│   │
│   ├── llm/
│   │   ├── client.py                # call_llm(), MODEL_PRICING
│   │   ├── mock_client.py           # MockLLMClient for tests
│   │   ├── rate_limiter.py          # ProviderSemaphore (see §34.2)
│   │   └── circuit_breaker.py      # CLOSED/OPEN/HALF-OPEN per (slot,model)
│   │
│   ├── connectors/
│   │   ├── base.py                  # SourceConnector ABC
│   │   ├── tavily.py
│   │   ├── brave.py
│   │   ├── crossref.py
│   │   ├── semantic_scholar.py
│   │   ├── arxiv.py
│   │   └── scraper.py               # BeautifulSoup + Playwright fallback
│   │
│   ├── storage/
│   │   ├── postgres.py              # SQLAlchemy async models + repositories
│   │   ├── redis_cache.py           # TTL cache helpers
│   │   └── minio.py                 # S3-compatible file ops
│   │
│   ├── workers/
│   │   ├── app.py                   # Celery app definition
│   │   └── tasks.py                 # run_document.delay(run_id)
│   │
│   ├── security/
│   │   ├── pii_detector.py          # presidio + spaCy pipeline
│   │   ├── injection_guard.py       # regex + structural isolation
│   │   └── encryption.py            # AES-256 helpers
│   │
│   ├── observability/
│   │   ├── tracing.py               # OpenTelemetry setup
│   │   ├── metrics.py               # Prometheus counters/histograms
│   │   └── logging.py               # structlog JSON config
│   │
│   ├── budget/
│   │   ├── estimator.py             # pre-run cost projection
│   │   ├── tracker.py               # real-time token/cost accumulation
│   │   └── regime.py                # Economy/Balanced/Premium params
│   │
│   └── models/
│       ├── document.py              # Pydantic I/O models for API
│       ├── source.py
│       ├── verdict.py
│       └── config.py                # DocumentConfig Pydantic model
│
├── migrations/
│   ├── env.py                       # Alembic config
│   └── versions/
│
└── tests/
    ├── unit/
    │   ├── test_style_linter.py
    │   ├── test_diff_merger.py
    │   ├── test_css_formula.py
    │   ├── test_circuit_breaker.py
    │   ├── test_pii_detector.py
    │   ├── test_budget_estimator.py
    │   └── test_rate_limiter.py
    ├── integration/
    │   ├── test_section_loop.py      # uses MockLLMClient
    │   ├── test_recovery.py          # kill worker mid-run, verify resume
    │   └── test_budget_enforcement.py
    ├── smoke/
    │   ├── phase1_smoke.py           # make test-phase1
    │   ├── phase2_smoke.py
    │   ├── phase3_smoke.py
    │   └── phase4_smoke.py
    └── benchmark/
        └── golden_set/
            ├── writer/
            ├── reflector/
            └── judges/
```

<!-- SPEC_COMPLETE -->