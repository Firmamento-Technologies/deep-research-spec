#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${ENV:-development}"
APP_ENV_VAL="${APP_ENV:-$ENVIRONMENT}"

if [[ "$APP_ENV_VAL" =~ ^(prod|production)$ ]]; then
  if [[ -z "${JWT_SECRET_KEY:-}" ]]; then
    echo "[verify_prod_env] ERROR: JWT_SECRET_KEY is required when APP_ENV=${APP_ENV_VAL}" >&2
    exit 1
  fi
fi

echo "[verify_prod_env] OK (ENV=${ENVIRONMENT}, APP_ENV=${APP_ENV_VAL})"
