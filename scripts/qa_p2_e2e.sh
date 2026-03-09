#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PASS=0
WARN=0
FAIL=0
BACKEND_TESTS_READY=1

STRICT_RELEASE_MODE="${QA_STRICT_RELEASE:-0}"
if [[ "$STRICT_RELEASE_MODE" == "1" ]]; then
  BUILD_CHECK_MODE="fail"
  HEALTH_CHECK_MODE="fail"
  BACKEND_DEPS_CHECK_MODE="fail"
  echo "[qa-p2] Strict release mode enabled: frontend build and health smoke are blocking"
else
  BUILD_CHECK_MODE="warn"
  HEALTH_CHECK_MODE="warn"
  BACKEND_DEPS_CHECK_MODE="warn"
  echo "[qa-p2] Local/dev mode: frontend build and health smoke are warning-only"
fi

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
required = ["pytest", "pytest_asyncio", "fastapi"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    print("Missing backend test dependencies:", ", ".join(missing))
    print("Install with: pip install -r backend/requirements.txt -r backend/requirements-test.txt")
    sys.exit(1)
PY
}

mark_backend_tests_unavailable() {
  BACKEND_TESTS_READY=0
  return 1
}

run_backend_api_contract_suite() {
  if [[ "$BACKEND_TESTS_READY" != "1" ]]; then
    echo "Skipping backend API contract suite: backend test dependencies unavailable"
    return 1
  fi
  python3 -m pytest backend/tests/test_api_endpoints.py -q
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

  if [[ ! -f "frontend/node_modules/vite/dist/node/cli.js" ]]; then
    echo "vite runtime missing: frontend/node_modules/vite/dist/node/cli.js"
    return 1
  fi

  if [[ ! -f "frontend/node_modules/typescript/bin/tsc" ]]; then
    echo "TypeScript compiler missing: frontend/node_modules/typescript/bin/tsc"
    return 1
  fi
}

if check_backend_test_dependencies; then
  run_check "$BACKEND_DEPS_CHECK_MODE" "Backend test dependency check" true
else
  BACKEND_TESTS_READY=0
  run_check "$BACKEND_DEPS_CHECK_MODE" "Backend test dependency check" false
fi

run_check fail "Frontend toolchain check" check_frontend_toolchain

run_check "$BACKEND_DEPS_CHECK_MODE" "Backend API contract regression suite" \
  run_backend_api_contract_suite

run_check "$BACKEND_DEPS_CHECK_MODE" "Backend reliability/HITL race unit suite" \
  python3 -m pytest \
    tests/unit/test_sse_broker_reliability.py \
    tests/unit/test_hitl_approval_roundtrip.py \
    tests/unit/test_run_manager_cancel_race.py \
    tests/unit/test_budget_estimator_v2.py \
    -q

run_check fail "Frontend typecheck" \
  node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json

run_check "$BUILD_CHECK_MODE" "Frontend build" \
  npm --prefix frontend run build

run_check "$HEALTH_CHECK_MODE" "Backend /health smoke" \
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
