# Direttiva 02 — Persistence & Storage

## Obiettivo

Implementare lo schema PostgreSQL, il checkpointer LangGraph (`AsyncPostgresSaver`), il layer Redis cache, e il client MinIO/S3. Dopo questa fase, il sistema può persistere stato e recuperare da crash.

## Pre-requisiti

- Fase 1 completata (`src/graph/state.py` esiste)
- Leggi `output/00_conflict_resolutions.md` §C11 (status enum)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/21_persistence.md` | §21.1 completo | Schema SQL: `users`, `documents`, `runs`, `outlines`, `sections`, `jury_rounds`, `costs`, `sources`, `writer_memory`, `run_companion_log` |
| `output/21_persistence.md` | §21.2 | `AsyncPostgresSaver` config, `build_checkpointer()`, `RunnableConfig` |
| `output/21_persistence.md` | §21.3 | Resume mechanism, crash recovery, orphan detector, permanent vs ephemeral state |
| `output/21_persistence.md` | §21.4 | Redis key schema, TTL table, cache lookup pattern, cost accumulator |
| `output/33_tech_stack.md` | §33.5 | SQLAlchemy models (core tables), schema note, MinIO config |
| `output/34_deployment.md` | §34.1.1 | Docker Compose service definitions per postgres, redis, minio |

## Output Atteso

### File da creare

```
src/storage/postgres.py         # SQLAlchemy async models + repository pattern
src/storage/checkpointer.py     # build_checkpointer(dsn) → AsyncPostgresSaver
src/storage/redis_cache.py      # TTL cache helpers, cost accumulator, key schema
src/storage/minio.py            # S3-compatible upload/download/presigned URLs
migrations/env.py               # Alembic config (async)
migrations/versions/001_initial.py  # Initial schema migration
```

### `src/storage/postgres.py` — Struttura richiesta

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import JSONB, ForeignKey, NUMERIC, TEXT
import uuid, datetime

class Base(DeclarativeBase): pass

class User(Base):              # da §21.1
class Document(Base):          # da §21.1 — status CHECK: draft/partial/complete/failed
class Run(Base):               # da §21.1 — status CHECK include "orphaned"
class Outline(Base):           # da §21.1
class Section(Base):           # da §21.1 — UNIQUE(document_id, section_index, version)
class JuryRound(Base):         # da §21.1
class CostEntry(Base):         # da §21.1
class SourceRecord(Base):      # da §21.1
class WriterMemoryRecord(Base):# da §21.1
class RunCompanionLog(Base):   # da §21.1

# Repository classes
class DocumentRepository:
    async def create(self, ...) -> Document: ...
    async def get_by_id(self, doc_id: uuid.UUID) -> Document | None: ...

class SectionRepository:
    async def insert_approved(self, ...) -> Section: ...
    async def fetch_approved_sections(self, doc_id: uuid.UUID) -> list[Section]: ...
    
class CostRepository:
    async def record_cost(self, entry: dict) -> None: ...
    async def get_total_cost(self, run_id: uuid.UUID) -> float: ...
```

### `src/storage/checkpointer.py` — Struttura richiesta

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
async def build_checkpointer(dsn: str) -> AsyncPostgresSaver: ...
```

### `src/storage/redis_cache.py` — Struttura richiesta

```python
# Key schema da §21.4
TTL_SECONDS: dict[str, int]  # src:*=86400, cite:*=2592000, etc.
async def cached_search(query: str, provider: str, redis) -> list[dict] | None: ...
async def record_cost_redis(run_id: str, delta_usd: float, redis) -> float: ...
# Graceful degradation: if Redis unreachable → return None / fallback PostgreSQL
```

## Script di Validazione

```bash
# Verifica che il modello SQLAlchemy definisca tutte le tabelle
python -c "from src.storage.postgres import Base; tables = Base.metadata.tables; assert 'sections' in tables and 'jury_rounds' in tables and 'costs' in tables, f'Missing tables: {tables.keys()}'; print('OK: all tables defined')"

# Verifica che checkpointer si importi correttamente
python -c "from src.storage.checkpointer import build_checkpointer; print('OK: checkpointer importable')"
```
