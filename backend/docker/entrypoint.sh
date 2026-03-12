#!/bin/bash
# =============================================================================
# DRS Backend Entrypoint
#
# 1. Wait for PostgreSQL to be ready
# 2. Wait for Redis to be ready
# 3. Run Alembic migrations
# 4. Start uvicorn
# =============================================================================

set -euo pipefail

WAIT_RETRIES=${WAIT_RETRIES:-30}
WAIT_DELAY=${WAIT_DELAY:-2}

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

log() {
    echo "[entrypoint] $(date '+%Y-%m-%d %H:%M:%S') $*"
}

wait_for_postgres() {
    local host
    local port
    # Extract host and port from DATABASE_URL
    # postgresql+asyncpg://user:pass@host:port/db
    host=$(echo "${DATABASE_URL}" | sed -E 's|.*@([^:/]+).*|\1|')
    port=$(echo "${DATABASE_URL}" | sed -E 's|.*:([0-9]+)/.*|\1|')
    port=${port:-5432}

    log "Waiting for PostgreSQL at ${host}:${port}..."
    for i in $(seq 1 "${WAIT_RETRIES}"); do
        if pg_isready -h "${host}" -p "${port}" -q 2>/dev/null; then
            log "✅ PostgreSQL ready"
            return 0
        fi
        log "  attempt ${i}/${WAIT_RETRIES} — not ready, retrying in ${WAIT_DELAY}s..."
        sleep "${WAIT_DELAY}"
    done

    log "❌ PostgreSQL did not become ready after ${WAIT_RETRIES} attempts"
    exit 1
}

wait_for_redis() {
    local host
    local port
    # Extract host and port from REDIS_URL (redis://host:port)
    host=$(echo "${REDIS_URL:-redis://redis:6379}" | sed -E 's|redis://([^:/]+).*|\1|')
    port=$(echo "${REDIS_URL:-redis://redis:6379}" | sed -E 's|.*:([0-9]+).*|\1|')
    port=${port:-6379}

    log "Waiting for Redis at ${host}:${port}..."
    for i in $(seq 1 "${WAIT_RETRIES}"); do
        if redis-cli -h "${host}" -p "${port}" ping 2>/dev/null | grep -q PONG; then
            log "✅ Redis ready"
            return 0
        fi
        log "  attempt ${i}/${WAIT_RETRIES} — not ready, retrying in ${WAIT_DELAY}s..."
        sleep "${WAIT_DELAY}"
    done

    log "❌ Redis did not become ready after ${WAIT_RETRIES} attempts"
    exit 1
}

run_migrations() {
    log "Running Alembic migrations..."
    alembic upgrade head
    log "✅ Migrations complete"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

log "=================================================="
log "Starting DRS Backend"
log "=================================================="

wait_for_postgres
wait_for_redis
run_migrations

log "=================================================="
log "Starting application server"
log "CMD: $*"
log "=================================================="

# exec replaces the shell process (proper signal forwarding)
exec "$@"
