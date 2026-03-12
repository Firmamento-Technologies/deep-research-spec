#!/bin/bash
# =============================================================================
# DRS Database Restore Script
#
# Restores PostgreSQL database from compressed backup.
# Usage: ./scripts/restore.sh backups/drs-2026-03-04.sql.gz
# =============================================================================

set -euo pipefail

BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-drs}
DB_NAME=${DB_NAME:-drs}
PGPASSWORD=${POSTGRES_PASSWORD:-drs_dev_password}

export PGPASSWORD

echo "Restoring from: ${BACKUP_FILE}"

# Drop and recreate database
echo "Recreating database..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE ${DB_NAME};"

# Restore from backup
echo "Restoring data..."
gunzip < "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"

echo "Restore complete"
