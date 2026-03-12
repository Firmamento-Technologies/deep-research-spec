# Knowledge Spaces Task 1.1-1.3 — Test Guide

**Status:** ✅ COMPLETED (2026-03-04)  
**Branch:** `fix/ui-issues-and-docker-config`  
**Tasks:** 1.1 (SQL schema), 1.3 (ORM models)

---

## 🎯 What Was Implemented

### Task 1.1: SQL Schema Base
**File:** [`002_add_chunks_table.py`](versions/002_add_chunks_table.py)

✅ **3 new tables:**
- `spaces` — knowledge containers
- `sources` — uploaded files/URLs per space
- `chunks` — RAG text chunks (512 token target)

✅ **Foreign keys:** `chunks.space_id → spaces.id`, `chunks.source_id → sources.id`  
✅ **Indexes:** `space_id`, `source_id` for fast filtering  
⏳ **Embedding column:** Coming in Task 1.2 (pgvector)

---

### Task 1.3: SQLAlchemy ORM Models
**File:** [`backend/database/models.py`](../models.py)

✅ **3 new models:**
```python
class Space(Base):   # Knowledge container
class Source(Base):  # Uploaded file metadata
class Chunk(Base):   # Text chunk for RAG
```

✅ **Relationships:**
```
Space (1) ──< Sources (*) ──< Chunks (*)
```

---

## 🧪 Step 1: Apply Migration

### Prerequisites

1. **PostgreSQL running**
```bash
# If using Docker Compose
docker-compose up -d postgres

# Or local PostgreSQL
psql -U postgres -c "CREATE DATABASE drs;"
```

2. **Python dependencies installed**
```bash
pip install alembic sqlalchemy psycopg2-binary
```

---

### Apply Migration 002

```bash
cd backend

# Check current migration status
alembic current
# Should show: 001 (initial_runs_table)

# Apply migration 002
alembic upgrade head

# Expected output:
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Add chunks table for Knowledge Spaces
```

**If you see errors:**

❌ **Error: `spaces already exists`**
```bash
# Migration 002 creates spaces table
# If it already exists from another migration, edit 002_add_chunks_table.py
# and comment out the "Create spaces table" block (lines 32-42)
```

❌ **Error: `ModuleNotFoundError: No module named 'database'`**
```bash
# Add backend to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
alembic upgrade head
```

---

## 🔍 Step 2: Validate Schema

### Check Tables Exist

```bash
psql -U postgres -d drs -c "\dt"
```

**Expected output:**
```
           List of relations
 Schema |   Name   | Type  |  Owner
--------+----------+-------+----------
 public | chunks   | table | postgres
 public | runs     | table | postgres
 public | settings | table | postgres
 public | sources  | table | postgres
 public | spaces   | table | postgres
(5 rows)
```

---

### Inspect chunks Table

```bash
psql -U postgres -d drs -c "\d chunks"
```

**Expected output:**
```
                          Table "public.chunks"
   Column   |            Type             | Nullable | Default
------------+-----------------------------+----------+---------
 id         | character varying(36)       | not null |
 space_id   | character varying(36)       | not null |
 source_id  | character varying(36)       | not null |
 content    | text                        | not null |
 created_at | timestamp without time zone |          | now()
 metadata   | jsonb                       |          |
Indexes:
    "chunks_pkey" PRIMARY KEY, btree (id)
    "ix_chunks_space_id" btree (space_id)
    "ix_chunks_source_id" btree (source_id)
Foreign-key constraints:
    "chunks_space_id_fkey" FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE CASCADE
    "chunks_source_id_fkey" FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
```

✅ **If you see this, Task 1.1 is SUCCESSFUL.**

---

## 🐍 Step 3: Test ORM Models

### Instantiate Models

```python
# backend/test_models.py
from database.models import Space, Source, Chunk
import uuid

# Create Space
space = Space(
    id=str(uuid.uuid4()),
    name="Test Space",
    description="Space for testing",
)

# Create Source
source = Source(
    id=str(uuid.uuid4()),
    space_id=space.id,
    filename="test.pdf",
    mime_type="application/pdf",
    status="pending",
)

# Create Chunk
chunk = Chunk(
    id=str(uuid.uuid4()),
    space_id=space.id,
    source_id=source.id,
    content="This is a test chunk for RAG retrieval.",
    metadata={"chunk_idx": 0, "token_count": 12},
)

print(f"✅ Space:  {space.name} ({space.id})")
print(f"✅ Source: {source.filename} ({source.id})")
print(f"✅ Chunk:  {len(chunk.content)} chars ({chunk.id})")
```

**Run test:**
```bash
cd backend
python test_models.py

# Expected output:
✅ Space:  Test Space (a1b2c3...)
✅ Source: test.pdf (d4e5f6...)
✅ Chunk:  42 chars (g7h8i9...)
```

---

### Insert into Database

```python
# backend/test_insert.py
from database.models import Space, Source, Chunk, Base
from database.connection import engine, get_db_session
import uuid

async def test_insert():
    async with get_db_session() as session:
        # Create space
        space = Space(
            id=str(uuid.uuid4()),
            name="Test Space",
            description="For RAG testing",
        )
        session.add(space)
        await session.flush()  # Get space.id
        
        # Create source
        source = Source(
            id=str(uuid.uuid4()),
            space_id=space.id,
            filename="test.pdf",
            mime_type="application/pdf",
        )
        session.add(source)
        await session.flush()
        
        # Create chunk
        chunk = Chunk(
            id=str(uuid.uuid4()),
            space_id=space.id,
            source_id=source.id,
            content="Test RAG chunk content.",
            metadata={"chunk_idx": 0},
        )
        session.add(chunk)
        await session.commit()
        
        print(f"✅ Inserted: Space {space.id}, Source {source.id}, Chunk {chunk.id}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_insert())
```

**Run test:**
```bash
cd backend
python test_insert.py

# Expected output:
✅ Inserted: Space abc123..., Source def456..., Chunk ghi789...
```

**Verify in DB:**
```bash
psql -U postgres -d drs -c "SELECT id, name FROM spaces;"
psql -U postgres -d drs -c "SELECT id, filename FROM sources;"
psql -U postgres -d drs -c "SELECT id, LEFT(content, 50) FROM chunks;"
```

✅ **If you see rows, Task 1.3 is SUCCESSFUL.**

---

## ✅ Success Criteria

- [x] Migration 002 applied without errors
- [x] Tables `spaces`, `sources`, `chunks` exist in PostgreSQL
- [x] Indexes `ix_chunks_space_id`, `ix_chunks_source_id` exist
- [x] Foreign keys validate correctly
- [x] ORM models instantiate without errors
- [x] INSERT into DB succeeds
- [ ] **Next:** Task 2.1 (text extraction utility)

---

## 🚀 Next Steps

### Ready for Task 2.1: Text Extraction

Once Task 1.1-1.3 validated:

```bash
# Ask for next task
"Ok Task 1 completato, procedi con Task 2.1 (text extraction)"
```

**Task 2.1 will create:**
- `backend/services/text_extractor.py`
- Support for PDF/DOCX/TXT extraction
- Test with real files

---

## 🐛 Troubleshooting

### Migration Fails: "relation already exists"

**Cause:** `spaces` table already created in another migration.  
**Fix:** Edit `002_add_chunks_table.py` line 32-42, comment out space creation.

### Import Error: `cannot import name 'Space'`

**Cause:** Models not in Python path.  
**Fix:**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
```

### Foreign Key Error: "violates foreign key constraint"

**Cause:** Trying to insert `Chunk` before `Space`/`Source` exist.  
**Fix:** Insert in order: `Space` → `Source` → `Chunk`

---

**Questions?** Check commit history:
- [Migration 002](https://github.com/lucadidomenicodopehubs/deep-research-spec/commit/9f5d09788c46d5d67d9b459213ab950bf45ee69a)
- [Models update](https://github.com/lucadidomenicodopehubs/deep-research-spec/commit/7ac51557bd905b029ce2b35a9a6a206ee99339de)
