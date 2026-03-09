#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="${ROOT_DIR}/docs/QA_P0_REPORT.md"

PASS=0
WARN=0
FAIL=0

echo "# QA P0 Gate Report" > "$REPORT_PATH"
echo >> "$REPORT_PATH"
echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$REPORT_PATH"
echo >> "$REPORT_PATH"

action() {
  local label="$1"
  local cmd="$2"
  local mode="${3:-strict}" # strict|warn

  echo "## ${label}" >> "$REPORT_PATH"
  echo >> "$REPORT_PATH"
  echo '\`\`\`bash' >> "$REPORT_PATH"
  echo "$cmd" >> "$REPORT_PATH"
  echo '\`\`\`' >> "$REPORT_PATH"
  echo >> "$REPORT_PATH"

  local out_file
  out_file="$(mktemp)"
  if bash -lc "$cmd" >"$out_file" 2>&1; then
    PASS=$((PASS+1))
    echo "- Status: PASS ✅" >> "$REPORT_PATH"
  else
    if [[ "$mode" == "warn" ]]; then
      WARN=$((WARN+1))
      echo "- Status: WARN ⚠️" >> "$REPORT_PATH"
    else
      FAIL=$((FAIL+1))
      echo "- Status: FAIL ❌" >> "$REPORT_PATH"
    fi
  fi
  echo >> "$REPORT_PATH"
  echo '\`\`\`text' >> "$REPORT_PATH"
  sed -n '1,160p' "$out_file" >> "$REPORT_PATH"
  echo '\`\`\`' >> "$REPORT_PATH"
  echo >> "$REPORT_PATH"
  rm -f "$out_file"
}

cd "$ROOT_DIR"

action "Unit suite (budget + SSE + cancel race + HITL roundtrip)" \
  "python3 -m pytest tests/unit/test_budget_estimator_v2.py tests/unit/test_sse_broker_reliability.py tests/unit/test_run_manager_cancel_race.py tests/unit/test_hitl_approval_roundtrip.py -q"

action "Frontend TypeScript check" \
  "node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json"

action "Frontend build" \
  "npm --prefix frontend run build" warn

action "Backend health smoke (requires running backend on :8000)" \
  "curl -sf http://localhost:8000/health" warn

{
  echo "## Summary"
  echo
  echo "- PASS: ${PASS}"
  echo "- WARN: ${WARN}"
  echo "- FAIL: ${FAIL}"
} >> "$REPORT_PATH"

echo "QA P0 report written to ${REPORT_PATH}"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
