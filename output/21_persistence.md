# §21 Persistence and Checkpointing

## §21.1 PostgreSQL Schema

```sql
-- Core tables with typed columns, PKs, FKs, indexes

CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    config_yaml TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('draft','partial','complete','failed')),
    word_count  INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id       TEXT NOT NULL UNIQUE,   -- LangGraph checkpoint key
    document_id     UUID NOT NULL REFERENCES documents(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    status          TEXT NOT NULL CHECK (status IN
                    ('initializing','running','paused','awaiting_approval',
                     'completed','failed','cancelled','orphaned')),
    profile         TEXT NOT NULL,
    config          JSONB NOT NULL,
    cost_usd        NUMERIC(10,4) NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    last_heartbeat  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_runs_thread   ON runs(thread_id);
CREATE INDEX idx_runs_status   ON runs(status);
CREATE INDEX idx_runs_document ON runs(document_id);

CREATE TABLE outlines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL REFERENCES runs(id),
    section_index   INTEGER NOT NULL,
    title           TEXT NOT NULL,
    scope           TEXT NOT NULL,
    estimated_words INTEGER NOT NULL,
    dependencies    JSONB NOT NULL DEFAULT '[]',
    approved_at     TIMESTAMPTZ,
    UNIQUE (document_id, section_index)
);

-- Permanent approved-section store; survives run crashes
CREATE TABLE sections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL REFERENCES runs(id),
    section_index   INTEGER NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('approved','regenerating','superseded')),
    css_content     NUMERIC(4,3),
    css_style       NUMERIC(4,3),
    iterations_used INTEGER NOT NULL,
    cost_usd        NUMERIC(8,4) NOT NULL,
    checkpoint_hash TEXT NOT NULL,   -- SHA-256 of content
    approved_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    warnings        JSONB NOT NULL DEFAULT '[]',
    UNIQUE (document_id, section_index, version)
);
CREATE INDEX idx_sections_document ON sections(document_id, section_index);

CREATE TABLE jury_rounds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id      UUID NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL REFERENCES runs(id),
    iteration       INTEGER NOT NULL,
    judge_slot      TEXT NOT NULL,   -- 'R1'|'R2'|'R3'|'F1'|'F2'|'F3'|'S1'|'S2'|'S3'
    model           TEXT NOT NULL,
    verdict         BOOLEAN NOT NULL,
    confidence      TEXT NOT NULL CHECK (confidence IN ('low','medium','high')),
    veto_category   TEXT,            -- NULL if no veto
    css_contribution NUMERIC(4,3),
    motivation      TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jury_section ON jury_rounds(section_id, iteration);

CREATE TABLE costs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    run_id        UUID NOT NULL REFERENCES runs(id),
    section_index INTEGER,
    iteration     INTEGER,
    agent         TEXT NOT NULL,
    model         TEXT NOT NULL,
    tokens_in     INTEGER NOT NULL,
    tokens_out    INTEGER NOT NULL,
    cost_usd      NUMERIC(8,6) NOT NULL,
    latency_ms    INTEGER NOT NULL,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_costs_run ON costs(run_id);

CREATE TABLE sources (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id      UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_index    INTEGER NOT NULL,
    source_type      TEXT NOT NULL CHECK (source_type IN
                     ('academic','institutional','web','social','uploaded')),
    title            TEXT NOT NULL,
    authors          JSONB NOT NULL DEFAULT '[]',
    year             INTEGER,
    doi              TEXT,
    url              TEXT,
    reliability_score NUMERIC(3,2) NOT NULL,
    nli_entailment   NUMERIC(4,3),
    http_verified    BOOLEAN NOT NULL DEFAULT false,
    ghost_flag       BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX idx_sources_document ON sources(document_id, section_index);

-- LangGraph checkpoint tables (managed by langgraph-checkpoint-postgres)
-- Thread state is persisted automatically; DRS does NOT write these directly.
-- Table: checkpoints (thread_id, checkpoint_id, parent_id, type, checkpoint, metadata)
-- Table: checkpoint_blobs  (thread_id, versions, type, blob)
-- Table: checkpoint_writes (thread_id, checkpoint_id, task_id, idx, channel, type, blob)

CREATE TABLE writer_memory (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    forbidden_hits  JSONB NOT NULL DEFAULT '{}',  -- {pattern: count}
    glossary        JSONB NOT NULL DEFAULT '{}',  -- {term: definition}
    citation_ratio  NUMERIC(4,3),
    style_drift_idx NUMERIC(4,3),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id)
);

CREATE TABLE run_companion_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id        UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    role          TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content       TEXT NOT NULL,
    section_index INTEGER,
    iteration     INTEGER,
    modification  JSONB,   -- NULL if informational; else {field, before, after}
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_companion_run ON run_companion_log(run_id, timestamp);
```

## §21.2 LangGraph AsyncPostgresSaver Configuration

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

# src/storage/checkpointer.py
async def build_checkpointer(dsn: str) -> AsyncPostgresSaver:
    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=2,
        max_size=10,
        kwargs={"autocommit": True},
    )
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()   # creates checkpoint tables if not present
    return checkpointer

# src/graph/graph.py
async def build_graph(dsn: str):
    checkpointer = await build_checkpointer(dsn)
    graph = _define_graph()                         # see §4.5
    return graph.compile(checkpointer=checkpointer)
```

```python
# Thread config passed to every graph invocation
from typing import TypedDict

class RunnableConfig(TypedDict):
    configurable: dict  # must contain {"thread_id": str}

# Example invocation
config: RunnableConfig = {"configurable": {"thread_id": run.thread_id}}
result = await graph.ainvoke(initial_state, config=config)
```

**Checkpoint frequency:** LangGraph saves state after every super-step (node completion).
Every node in the graph is one checkpoint boundary. No additional checkpoint logic needed.

**thread_id lifecycle:**

| Event | Action |
|---|---|
| `POST /v1/runs` received | `thread_id = str(uuid4())` saved to `runs.thread_id` **before** first LLM call |
| Node completes | LangGraph auto-saves checkpoint keyed by `thread_id` |
| Process crash | State preserved in `checkpoints` table |
| `POST /v1/runs/{id}/resume` | `graph.ainvoke({}, config={"configurable": {"thread_id": existing_thread_id}})` |

## §21.3 Resume Mechanism — Crash + Recovery Timeline

### Concrete Crash Scenario

```
T+00:00  POST /v1/runs → run_id=abc, thread_id=thr-xyz saved to DB
T+00:05  Planner completes → checkpoint saved: {outline approved, section_idx=0}
T+02:30  Section 1 approved → checkpoint: {approved_sections=[0], section_idx=1}
T+05:10  Section 2, iteration 2 — Writer node starts
T+05:14  CRASH: Celery worker OOM-killed mid Writer node
         → no checkpoint written for partial Writer output
         → last valid checkpoint: {section_idx=1, iteration=1 of section 2}
T+05:15  Celery worker restarts; job re-queued (Redis LMPOP crash-safe)
T+05:16  Worker picks job; calls graph.ainvoke({}, config=thread_id=thr-xyz)
T+05:17  LangGraph loads checkpoint → resumes at start of Writer node for section 2 iter 2
         → approved_sections=[0,1] intact in Store (sections table)
         → no re-computation of section 1
T+07:40  Section 2 approved → run continues normally
```

### Recovery Rules

```python
# src/workers/tasks.py
@celery.task(bind=True, max_retries=5, default_retry_delay=10)
def execute_run(self, run_id: str) -> None:
    run = db.get_run(run_id)

    # Idempotent: if run already completed, skip
    if run.status in ("completed", "cancelled"):
        return

    # Mark heartbeat; orphan detector uses this
    db.update_heartbeat(run_id)

    config = {"configurable": {"thread_id": run.thread_id}}

    try:
        # Empty input: LangGraph merges with checkpointed state
        asyncio.run(graph.ainvoke({}, config=config))
    except Exception as exc:
        db.set_run_status(run_id, "failed", error=str(exc))
        raise self.retry(exc=exc)
```

```python
# Orphan detector: runs as cron every 5 minutes
# A run is orphaned if last_heartbeat > 3 minutes ago and status == 'running'
async def detect_orphaned_runs(db) -> None:
    threshold = datetime.utcnow() - timedelta(minutes=3)
    orphans = await db.fetch(
        "SELECT id FROM runs WHERE status='running' AND last_heartbeat < $1",
        threshold
    )
    for run in orphans:
        await celery.send_task("execute_run", args=[str(run.id)])
```

### Permanent vs Ephemeral State

| Layer | Storage | Survives crash? | Contents |
|---|---|---|---|
| **Store (permanent)** | PostgreSQL `sections` table | YES | Approved section content, CSS scores, sources, jury verdicts |
| **LangGraph State (ephemeral)** | PostgreSQL `checkpoints` table | YES (last super-step) | Full `DRSState` TypedDict — current draft, embeddings, budget counters |
| **In-process memory** | Python heap | NO | LLM response objects, temp buffers |
| **Redis pub/sub** | Redis (AOF enabled) | Partial (AOF) | SSE events, task queue entries |

**Architectural invariant:** `sections` table is the source of truth for approved content.
`DRSState.approved_sections` is a derived cache rebuilt from `sections` table on resume.
If State and Store diverge, Store wins.

```python
# Resume reconciliation (first node after crash recovery)
async def preflight_node(state: DRSState, db) -> dict:
    # Re-sync approved_sections from permanent store
    db_sections = await db.fetch_approved_sections(state["document_id"])
    return {
        "approved_sections": [s.to_dict() for s in db_sections],
        "current_section_idx": len(db_sections),  # resume from next section
    }
```

## §21.4 Redis Key Schema

```python
from typing import Literal

RedisKeySpace = Literal[
    "src:{query_hash}",           # Researcher cache: list[Source] JSON
    "cite:{doi_or_url_hash}",     # Citation metadata cache
    "verdict:{draft_hash}:{judge_id}",  # Judge verdict cache (session-scoped)
    "compress:{section_hash}",    # Context Compressor output cache
    "run:{run_id}:cost",          # Atomic cost accumulator (INCRBYFLOAT)
    "run:{run_id}:events",        # SSE event stream (Redis List, RPUSH/BLPOP)
    "rate:{provider}:{window_ts}",# Rate limit counter (INCR + EXPIRE)
    "session:{user_id}",          # Run Companion conversation (JSON)
    "lock:{run_id}",              # Distributed lock (SET NX EX)
]

TTL_SECONDS: dict[str, int] = {
    "src:*":       86_400,   # 24h
    "cite:*":      2_592_000, # 30d
    "verdict:*":   3_600,    # 1h (session-scoped)
    "compress:*":  86_400,   # 24h
    "run:*:cost":  604_800,  # 7d
    "run:*:events": 3_600,   # 1h
    "rate:*":      60,       # 1 min window
    "session:*":   86_400,   # 24h
    "lock:*":      300,      # 5 min max lock hold
}
```

**Hash function:** `SHA-256(canonical_json(input))[:16]` for all `*_hash` keys.

**Cache lookup pattern (Researcher):**

```python
async def cached_search(query: str, provider: str, redis) -> list[dict] | None:
    key = f"src:{sha256_hex(query + provider)}"
    hit = await redis.get(key)
    if hit:
        return json.loads(hit)
    results = await provider.search(query)
    await redis.setex(key, TTL_SECONDS["src:*"], json.dumps(results))
    return results
```

**Cost accumulator (atomic):**

```python
async def record_cost(run_id: str, delta_usd: float, redis) -> float:
    key = f"run:{run_id}:cost"
    total = await redis.incrbyfloat(key, delta_usd)
    await redis.expire(key, TTL_SECONDS["run:*:cost"])
    return total
```

**Graceful degradation:** If Redis is unreachable, all cache lookups return `None` (cache miss); cost accumulation falls back to `costs` PostgreSQL table aggregation. Run continues without interruption. Circuit breaker (see §20.3) tracks Redis failures independently.

<!-- SPEC_COMPLETE -->