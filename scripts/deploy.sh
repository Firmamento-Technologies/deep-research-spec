#!/bin/bash
# =============================================================================
# DRS Deployment Script
#
# Usage:
#   ENV=development ./scripts/deploy.sh
#   ENV=staging ./scripts/deploy.sh
#   ENV=production ./scripts/deploy.sh
# =============================================================================

set -euo pipefail

ENV=${ENV:-development}
VERSION=${VERSION:-latest}
BACKUP_RETENTION_DAYS=30

# ── Colors ───────────────────────────────────────────────────────────────────
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

log() {
    echo -e "${CYAN}[deploy]${RESET} $(date '+%Y-%m-%d %H:%M:%S') $*"
}

success() {
    echo -e "${GREEN}[deploy]${RESET} $*"
}

warn() {
    echo -e "${YELLOW}[deploy]${RESET} $*"
}

error() {
    echo -e "${RED}[deploy]${RESET} $*"
    exit 1
}

# ── Pre-flight checks ────────────────────────────────────────────────────────

log "Starting deployment to ${ENV}"

# Check Docker is running
if ! docker info >/dev/null 2>&1; then
    error "Docker is not running"
fi

# Check disk space (require 5GB free)
AVAIL=$(df / | tail -1 | awk '{print $4}')
if [ "$AVAIL" -lt 5242880 ]; then
    warn "Low disk space: $(df -h / | tail -1 | awk '{print $4}') free"
fi

# Check docker-compose version
if ! docker-compose version >/dev/null 2>&1; then
    error "docker-compose not found"
fi

success "Pre-flight checks passed"

# ── Backup database (production only) ───────────────────────────────────────

if [ "$ENV" = "production" ]; then
    log "Creating database backup..."
    bash scripts/backup.sh || warn "Backup failed, continuing..."
fi

# ── Pull latest images ──────────────────────────────────────────────────────

log "Pulling latest Docker images..."
if [ "$ENV" = "production" ]; then
    # Pull from registry
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull
else
    # Build locally
    export DOCKER_BUILDKIT=1
    docker-compose build --parallel
fi

success "Images ready"

# ── Run migrations ──────────────────────────────────────────────────────────

log "Running database migrations..."
docker-compose run --rm backend alembic upgrade head || error "Migrations failed"

success "Migrations complete"

# ── Deploy with zero-downtime ──────────────────────────────────────────────

log "Starting services..."
if [ "$ENV" = "production" ]; then
    # Blue-green deployment
    bash scripts/blue-green-deploy.sh
else
    # Simple restart
    docker-compose up -d
fi

success "Services started"

# ── Health checks ────────────────────────────────────────────────────────────

log "Running health checks..."
sleep 10  # Give services time to start

if bash scripts/health-check.sh; then
    success "Health checks passed"
else
    error "Health checks failed — rolling back"
    bash scripts/rollback.sh
    exit 1
fi

# ── Cleanup old backups ─────────────────────────────────────────────────────

if [ "$ENV" = "production" ]; then
    log "Cleaning up old backups (>${BACKUP_RETENTION_DAYS} days)..."
    find backups/ -name "*.sql.gz" -mtime +${BACKUP_RETENTION_DAYS} -delete || true
fi

# ── Notify ──────────────────────────────────────────────────────────────────

if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    curl -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-Type: application/json' \
        -d "{ \"text\": \"✅ DRS deployed to ${ENV} (version ${VERSION})\" }" \
        >/dev/null 2>&1 || true
fi

success "Deployment to ${ENV} complete!"
