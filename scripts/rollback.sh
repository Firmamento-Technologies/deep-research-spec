#!/bin/bash
# =============================================================================
# DRS Rollback Script
#
# Reverts to previous Docker image version and database state.
# Usage: ./scripts/rollback.sh [version]
# =============================================================================

set -euo pipefail

VERSION=${1:-previous}

echo "Rolling back to version: ${VERSION}"

# Stop current services
echo "Stopping services..."
docker-compose down

# Restore database from latest backup
if [ -d backups ] && [ -n "$(ls -A backups/*.sql.gz 2>/dev/null)" ]; then
    LATEST_BACKUP=$(ls -t backups/*.sql.gz | head -1)
    echo "Restoring database from: ${LATEST_BACKUP}"
    bash scripts/restore.sh "$LATEST_BACKUP"
else
    echo "Warning: No backups found, skipping database restore"
fi

# Pull previous images
if [ "$VERSION" != "previous" ]; then
    echo "Pulling version: ${VERSION}"
    docker-compose pull
fi

# Start services
echo "Starting services..."
docker-compose up -d

echo "Rollback complete"
