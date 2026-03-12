#!/usr/bin/env bash
set -euo pipefail

NPM_CI_TIMEOUT_SEC="${FRONTEND_NPM_CI_TIMEOUT_SEC:-120}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

needs_install=0

if [[ ! -d frontend/node_modules ]]; then
  needs_install=1
fi

if [[ ! -f frontend/node_modules/vite/dist/node/cli.js ]]; then
  needs_install=1
fi

if [[ ! -f frontend/node_modules/typescript/bin/tsc ]]; then
  needs_install=1
fi

if [[ "$needs_install" == "1" ]]; then
  if [[ "${BOOTSTRAP_FRONTEND_DEPS:-0}" == "1" ]]; then
    if [[ ! -f frontend/package-lock.json ]]; then
      echo "[frontend-runtime] Missing frontend/package-lock.json: cannot run npm ci safely"
      echo "[frontend-runtime] Generate lockfile first or install dependencies manually"
      exit 1
    fi
    echo "[frontend-runtime] Installing frontend dependencies (npm ci)"
    timeout "$NPM_CI_TIMEOUT_SEC" npm --prefix frontend ci --no-audit --no-fund --prefer-offline
  else
    echo "[frontend-runtime] Missing/incomplete frontend runtime"
    echo "[frontend-runtime] Run with BOOTSTRAP_FRONTEND_DEPS=1 or execute: npm --prefix frontend ci"
    exit 1
  fi
fi

if [[ ! -f frontend/node_modules/.bin/vite ]]; then
  echo "[frontend-runtime] vite binary shim missing after bootstrap"
  exit 1
fi

if [[ ! -f frontend/node_modules/vite/dist/node/cli.js ]]; then
  echo "[frontend-runtime] vite runtime missing after bootstrap"
  exit 1
fi

if [[ ! -f frontend/node_modules/typescript/bin/tsc ]]; then
  echo "[frontend-runtime] TypeScript compiler missing after bootstrap"
  exit 1
fi

echo "[frontend-runtime] Frontend runtime/toolchain ready"
