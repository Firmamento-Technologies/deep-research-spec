"""001 — Initial schema: all DRS tables from §21.1.

Revision ID: 001_initial
Revises: (none)
Create Date: 2026-02-22
"""
from __future__ import annotations

from alembic import op

# Revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all DRS tables per §21.1 PostgreSQL schema."""

    # ── users ────────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE users (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    # ── documents ────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE documents (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        topic        TEXT NOT NULL,
        config_yaml  TEXT NOT NULL,
        status       TEXT NOT NULL CHECK (status IN ('draft','partial','complete','failed')),
        word_count   INTEGER,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        completed_at TIMESTAMPTZ
    );
    """)

    # ── runs ─────────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE runs (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        thread_id       TEXT NOT NULL UNIQUE,
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
    """)

    # ── outlines ─────────────────────────────────────────────────────────
    op.execute("""
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
    """)

    # ── sections ─────────────────────────────────────────────────────────
    op.execute("""
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
        checkpoint_hash TEXT NOT NULL,
        approved_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        warnings        JSONB NOT NULL DEFAULT '[]',
        UNIQUE (document_id, section_index, version)
    );
    CREATE INDEX idx_sections_document ON sections(document_id, section_index);
    """)

    # ── jury_rounds ──────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE jury_rounds (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        section_id       UUID NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
        run_id           UUID NOT NULL REFERENCES runs(id),
        iteration        INTEGER NOT NULL,
        judge_slot       TEXT NOT NULL,
        model            TEXT NOT NULL,
        verdict          BOOLEAN NOT NULL,
        confidence       TEXT NOT NULL CHECK (confidence IN ('low','medium','high')),
        veto_category    TEXT,
        css_contribution NUMERIC(4,3),
        motivation       TEXT NOT NULL,
        timestamp        TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX idx_jury_section ON jury_rounds(section_id, iteration);
    """)

    # ── costs ────────────────────────────────────────────────────────────
    op.execute("""
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
    """)

    # ── sources ──────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE sources (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id       UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        section_index     INTEGER NOT NULL,
        source_type       TEXT NOT NULL CHECK (source_type IN
                          ('academic','institutional','web','social','upload')),
        title             TEXT NOT NULL,
        authors           JSONB NOT NULL DEFAULT '[]',
        year              INTEGER,
        doi               TEXT,
        url               TEXT,
        reliability_score NUMERIC(3,2) NOT NULL,
        nli_entailment    NUMERIC(4,3),
        http_verified     BOOLEAN NOT NULL DEFAULT false,
        ghost_flag        BOOLEAN NOT NULL DEFAULT false
    );
    CREATE INDEX idx_sources_document ON sources(document_id, section_index);
    """)

    # ── writer_memory ────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE writer_memory (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        run_id          UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        forbidden_hits  JSONB NOT NULL DEFAULT '{}',
        glossary        JSONB NOT NULL DEFAULT '{}',
        citation_ratio  NUMERIC(4,3),
        style_drift_idx NUMERIC(4,3),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (run_id)
    );
    """)

    # ── run_companion_log ────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE run_companion_log (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        run_id        UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        role          TEXT NOT NULL CHECK (role IN ('user','assistant')),
        content       TEXT NOT NULL,
        section_index INTEGER,
        iteration     INTEGER,
        modification  JSONB,
        timestamp     TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX idx_companion_run ON run_companion_log(run_id, timestamp);
    """)


def downgrade() -> None:
    """Drop all DRS tables in reverse dependency order."""
    for table in [
        "run_companion_log", "writer_memory", "sources", "costs",
        "jury_rounds", "sections", "outlines", "runs", "documents", "users",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
