#!/bin/bash
# =============================================================================
# DRS Database Backup Script
#
# Creates compressed PostgreSQL backup with timestamp.
# Optionally uploads to S3/MinIO.
# =============================================================================

set -euo pipefail

BACKUP_DIR=${BACKUP_DIR:-./backups}
TIMESTAMP=$(date '+%Y-%m-%d-%H-%M-%S')
BACKUP_FILE="${BACKUP_DIR}/drs-${TIMESTAMP}.sql.gz"

DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-drs}
DB_NAME=${DB_NAME:-drs}
PGPASSWORD=${POSTGRES_PASSWORD:-drs_dev_password}

export PGPASSWORD

mkdir -p "$BACKUP_DIR"

echo "Creating backup: ${BACKUP_FILE}"

pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-acl \
    --clean \
    --if-exists \
    | gzip > "$BACKUP_FILE"

echo "Backup complete: ${BACKUP_FILE} ($(du -h "$BACKUP_FILE" | cut -f1))"

# Upload to S3/MinIO (optional)
if [ -n "${S3_BUCKET:-}" ]; then
    echo "Uploading to S3: ${S3_BUCKET}"
    aws s3 cp "$BACKUP_FILE" "s3://${S3_BUCKET}/backups/" || true
fi
