#!/usr/bin/env bash
set -u

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
    echo "[frontend-runtime] Installing frontend dependencies (npm ci)"
    timeout 120 npm --prefix frontend ci
  else
    echo "[frontend-runtime] Missing/incomplete frontend runtime"
    echo "[frontend-runtime] Run with BOOTSTRAP_FRONTEND_DEPS=1 or execute: npm --prefix frontend ci"
    exit 1
  fi
fi

if [[ -f frontend/node_modules/.bin/vite ]]; then
  chmod +x frontend/node_modules/.bin/vite 2>/dev/null || true
fi

test -x frontend/node_modules/.bin/vite
test -f frontend/node_modules/vite/dist/node/cli.js
test -f frontend/node_modules/typescript/bin/tsc

echo "[frontend-runtime] Frontend runtime/toolchain ready"
