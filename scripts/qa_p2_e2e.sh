#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PASS=0
WARN=0
FAIL=0

run_check() {
  local mode="$1"
  local label="$2"
  shift 2

  echo ""
  echo "==> ${label}"

  if "$@"; then
    echo "[PASS] ${label}"
    PASS=$((PASS + 1))
  else
    if [[ "$mode" == "warn" ]]; then
      echo "[WARN] ${label}"
      WARN=$((WARN + 1))
    else
      echo "[FAIL] ${label}"
      FAIL=$((FAIL + 1))
    fi
  fi
}

check_backend_test_dependencies() {
  python3 - <<'PY'
import importlib.util
import sys
required = ["httpx", "pytest"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    print("Missing backend test dependencies:", ", ".join(missing))
    print("Install with: pip install -r backend/requirements.txt pytest pytest-asyncio")
    sys.exit(1)
PY
}

check_frontend_toolchain() {
  if [[ ! -d "frontend/node_modules" ]]; then
    echo "Missing frontend/node_modules. Run: npm --prefix frontend ci"
    return 1
  fi

  if [[ -f "frontend/node_modules/.bin/vite" ]]; then
    chmod +x frontend/node_modules/.bin/vite 2>/dev/null || true
  fi

  if [[ ! -x "frontend/node_modules/.bin/vite" ]]; then
    echo "vite binary is not executable at frontend/node_modules/.bin/vite"
    return 1
  fi
}

run_check fail "Backend test dependency check" check_backend_test_dependencies
run_check fail "Frontend toolchain check" check_frontend_toolchain

run_check fail "Backend API contract regression suite" \
  python3 -m pytest backend/tests/test_api_endpoints.py -q

run_check fail "Backend reliability/HITL race unit suite" \
  python3 -m pytest \
    tests/unit/test_sse_broker_reliability.py \
    tests/unit/test_hitl_approval_roundtrip.py \
    tests/unit/test_run_manager_cancel_race.py \
    tests/unit/test_budget_estimator_v2.py \
    -q

run_check fail "Frontend typecheck" \
  node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json

run_check warn "Frontend build (warn-mode in constrained env)" \
  npm --prefix frontend run build

run_check warn "Backend /health smoke (warn if service not running)" \
  curl -sf http://localhost:8000/health

echo ""
echo "==============================="
echo "P2 QA summary"
echo "PASS: ${PASS}"
echo "WARN: ${WARN}"
echo "FAIL: ${FAIL}"
echo "==============================="

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi

exit 0
