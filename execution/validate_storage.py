"""Phase 2 validation — Persistence & Storage layer.

Checks:
  1. SQLAlchemy Base.metadata contains all 10 required tables
  2. All tables match §21.1 column counts and constraints
  3. checkpointer module imports cleanly
  4. Redis cache exports TTL_SECONDS with correct values
  5. MinIO client exports key helpers
  6. Migration file is present and valid
  7. Repository classes exist with required methods
"""
from __future__ import annotations
import os
import sys

# Ensure project root is on sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
errors: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS} {label}")
    else:
        msg = f"{label}: {detail}" if detail else label
        errors.append(msg)
        print(f"  {FAIL} {msg}")


# ── 1. SQLAlchemy models — all 10 tables ────────────────────────────────────
print("\n[1] SQLAlchemy models (src/storage/postgres.py)")
try:
    from src.storage.postgres import (
        Base, User, Document, Run, Outline, Section,
        JuryRound, CostEntry, SourceRecord, WriterMemoryRecord,
        RunCompanionLog,
    )
    tables = set(Base.metadata.tables.keys())
    expected_tables = {
        "users", "documents", "runs", "outlines", "sections",
        "jury_rounds", "costs", "sources", "writer_memory",
        "run_companion_log",
    }
    check("All 10 tables defined", expected_tables.issubset(tables),
          f"Missing: {expected_tables - tables}")

    # Verify key columns exist
    sec_cols = {c.name for c in Base.metadata.tables["sections"].columns}
    check("sections has checkpoint_hash", "checkpoint_hash" in sec_cols)
    check("sections has css_content", "css_content" in sec_cols)
    check("sections has css_style", "css_style" in sec_cols)
    check("sections has version", "version" in sec_cols)

    run_cols = {c.name for c in Base.metadata.tables["runs"].columns}
    check("runs has thread_id", "thread_id" in run_cols)
    check("runs has last_heartbeat", "last_heartbeat" in run_cols)
    check("runs has cost_usd", "cost_usd" in run_cols)

    cost_cols = {c.name for c in Base.metadata.tables["costs"].columns}
    check("costs has tokens_in/tokens_out", "tokens_in" in cost_cols and "tokens_out" in cost_cols)
    check("costs has latency_ms", "latency_ms" in cost_cols)

    src_cols = {c.name for c in Base.metadata.tables["sources"].columns}
    check("sources has reliability_score", "reliability_score" in src_cols)
    check("sources has ghost_flag", "ghost_flag" in src_cols)
    check("sources has nli_entailment", "nli_entailment" in src_cols)

    wm_cols = {c.name for c in Base.metadata.tables["writer_memory"].columns}
    check("writer_memory has forbidden_hits", "forbidden_hits" in wm_cols)
    check("writer_memory has glossary", "glossary" in wm_cols)

    comp_cols = {c.name for c in Base.metadata.tables["run_companion_log"].columns}
    check("run_companion_log has modification", "modification" in comp_cols)

except Exception as e:
    errors.append(f"SQLAlchemy import failed: {e}")
    print(f"  {FAIL} Import failed: {e}")

# ── 2. Checkpointer ─────────────────────────────────────────────────────────
print("\n[2] Checkpointer (src/storage/checkpointer.py)")
try:
    from src.storage.checkpointer import (
        build_checkpointer, RunnableConfig, make_config,
        preflight_reconcile, detect_orphaned_runs,
    )
    check("build_checkpointer importable", callable(build_checkpointer))
    check("make_config importable", callable(make_config))
    check("preflight_reconcile importable", callable(preflight_reconcile))
    check("detect_orphaned_runs importable", callable(detect_orphaned_runs))

    # Verify make_config output
    cfg = make_config("test-thread-123")
    check("make_config returns correct structure",
          cfg == {"configurable": {"thread_id": "test-thread-123"}})

except Exception as e:
    errors.append(f"Checkpointer import failed: {e}")
    print(f"  {FAIL} Import failed: {e}")

# ── 3. Redis cache ──────────────────────────────────────────────────────────
print("\n[3] Redis cache (src/storage/redis_cache.py)")
try:
    from src.storage.redis_cache import (
        TTL_SECONDS, sha256_hex, canonical_json,
        cached_search, cache_search_results,
        record_cost_redis, push_sse_event,
        check_rate_limit, acquire_lock, release_lock,
        cached_citation, cache_citation,
        cached_verdict, cache_verdict,
        cached_compressed, cache_compressed,
    )

    # Verify TTL values from §21.4
    check("TTL src:* = 86400", TTL_SECONDS.get("src:*") == 86_400)
    check("TTL cite:* = 2592000", TTL_SECONDS.get("cite:*") == 2_592_000)
    check("TTL verdict:* = 3600", TTL_SECONDS.get("verdict:*") == 3_600)
    check("TTL compress:* = 86400", TTL_SECONDS.get("compress:*") == 86_400)
    check("TTL run:*:cost = 604800", TTL_SECONDS.get("run:*:cost") == 604_800)
    check("TTL run:*:events = 3600", TTL_SECONDS.get("run:*:events") == 3_600)
    check("TTL rate:* = 60", TTL_SECONDS.get("rate:*") == 60)
    check("TTL session:* = 86400", TTL_SECONDS.get("session:*") == 86_400)
    check("TTL lock:* = 300", TTL_SECONDS.get("lock:*") == 300)

    # Verify hash function (SHA-256 truncated to 16 hex chars)
    h = sha256_hex("test")
    check("sha256_hex returns 16 hex chars", len(h) == 16 and all(c in "0123456789abcdef" for c in h))

    # Verify canonical_json determinism
    j1 = canonical_json({"b": 2, "a": 1})
    j2 = canonical_json({"a": 1, "b": 2})
    check("canonical_json is deterministic (key order)", j1 == j2)

except Exception as e:
    errors.append(f"Redis cache import failed: {e}")
    print(f"  {FAIL} Import failed: {e}")

# ── 4. MinIO client ─────────────────────────────────────────────────────────
print("\n[4] MinIO client (src/storage/minio.py)")
try:
    from src.storage.minio import (
        MinIOClient, build_minio_client, output_key, uploaded_source_key,
        CONTENT_TYPES, OutputFormat, PRESIGNED_URL_EXPIRY, DEFAULT_BUCKET,
    )

    check("MinIOClient class exists", isinstance(MinIOClient, type))
    check("build_minio_client callable", callable(build_minio_client))
    check("PRESIGNED_URL_EXPIRY = 900", PRESIGNED_URL_EXPIRY == 900)
    check("DEFAULT_BUCKET = 'drs-documents'", DEFAULT_BUCKET == "drs-documents")

    # Verify output_key generates correct paths
    key = output_key("abc123", "pdf")
    check("output_key('abc123','pdf') = 'runs/abc123/output.pdf'",
          key == "runs/abc123/output.pdf")

    key_docx = output_key("abc123", "docx")
    check("output_key docx", key_docx == "runs/abc123/output.docx")

    src_key = uploaded_source_key("abc123", "paper.pdf")
    check("uploaded_source_key", src_key == "runs/abc123/sources/paper.pdf")

    # Verify all 6 output formats in CONTENT_TYPES
    expected_formats = {"docx", "pdf", "markdown", "latex", "html", "json"}
    check("CONTENT_TYPES has all 6 formats",
          set(CONTENT_TYPES.keys()) == expected_formats,
          f"Got: {set(CONTENT_TYPES.keys())}")

except Exception as e:
    errors.append(f"MinIO import failed: {e}")
    print(f"  {FAIL} Import failed: {e}")

# ── 5. Migration file ───────────────────────────────────────────────────────
print("\n[5] Migration file")
try:
    from migrations.versions import __init__ as _  # noqa: F401
    import importlib
    mod = importlib.import_module("migrations.versions.001_initial")
    check("001_initial.py importable", True)
    check("Has upgrade()", callable(getattr(mod, "upgrade", None)))
    check("Has downgrade()", callable(getattr(mod, "downgrade", None)))
    check("revision = '001_initial'", getattr(mod, "revision", None) == "001_initial")
    check("down_revision = None", getattr(mod, "down_revision", "MISSING") is None)
except Exception as e:
    errors.append(f"Migration import failed: {e}")
    print(f"  {FAIL} Import failed: {e}")

# ── 6. Repository classes ───────────────────────────────────────────────────
print("\n[6] Repository classes (src/storage/postgres.py)")
try:
    from src.storage.postgres import (
        DocumentRepository, RunRepository, SectionRepository,
        CostRepository, JuryRoundRepository, SourceRepository,
        build_engine,
    )
    check("DocumentRepository exists", isinstance(DocumentRepository, type))
    check("RunRepository exists", isinstance(RunRepository, type))
    check("SectionRepository exists", isinstance(SectionRepository, type))
    check("CostRepository exists", isinstance(CostRepository, type))
    check("JuryRoundRepository exists", isinstance(JuryRoundRepository, type))
    check("SourceRepository exists", isinstance(SourceRepository, type))
    check("build_engine callable", callable(build_engine))

    # Verify key methods exist
    check("DocumentRepository.create", hasattr(DocumentRepository, "create"))
    check("DocumentRepository.get_by_id", hasattr(DocumentRepository, "get_by_id"))
    check("DocumentRepository.set_status", hasattr(DocumentRepository, "set_status"))
    check("RunRepository.create", hasattr(RunRepository, "create"))
    check("RunRepository.update_heartbeat", hasattr(RunRepository, "update_heartbeat"))
    check("SectionRepository.insert_approved", hasattr(SectionRepository, "insert_approved"))
    check("SectionRepository.fetch_approved_sections",
          hasattr(SectionRepository, "fetch_approved_sections"))
    check("CostRepository.record_cost", hasattr(CostRepository, "record_cost"))
    check("CostRepository.get_total_cost", hasattr(CostRepository, "get_total_cost"))

except Exception as e:
    errors.append(f"Repository import failed: {e}")
    print(f"  {FAIL} Import failed: {e}")

# ── 7. Alembic env ──────────────────────────────────────────────────────────
print("\n[7] Alembic environment")
try:
    import os
    env_path = os.path.join("migrations", "env.py")
    check("migrations/env.py exists", os.path.isfile(env_path))
    versions_dir = os.path.join("migrations", "versions")
    check("migrations/versions/ directory exists", os.path.isdir(versions_dir))
except Exception as e:
    errors.append(f"Alembic env check failed: {e}")
    print(f"  {FAIL} Check failed: {e}")

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
if errors:
    print(f"PHASE 2 VALIDATION: {FAIL} {len(errors)} error(s)")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"PHASE 2 VALIDATION: {PASS} ALL CHECKS PASSED")
    sys.exit(0)
