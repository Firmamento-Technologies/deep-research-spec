#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="${ROOT_DIR}/docs/RELEASE_DRY_RUN_REPORT.md"
RUN_ID="$(date -u +"%Y%m%dT%H%M%SZ")"
HEALTH_URL="${QA_HEALTH_URL:-http://localhost:8000/health}"

PASS=0
WARN=0
FAIL=0

log_step() {
  local label="$1"
  local cmd="$2"
  local mode="${3:-strict}" # strict|warn

  echo "## ${label}" >> "$REPORT_PATH"
  echo >> "$REPORT_PATH"
  echo '```bash' >> "$REPORT_PATH"
  echo "$cmd" >> "$REPORT_PATH"
  echo '```' >> "$REPORT_PATH"
  echo >> "$REPORT_PATH"

  local out_file
  out_file="$(mktemp)"

  if bash -lc "$cmd" >"$out_file" 2>&1; then
    PASS=$((PASS + 1))
    echo "- Status: PASS ✅" >> "$REPORT_PATH"
  else
    if [[ "$mode" == "warn" ]]; then
      WARN=$((WARN + 1))
      echo "- Status: WARN ⚠️" >> "$REPORT_PATH"
    else
      FAIL=$((FAIL + 1))
      echo "- Status: FAIL ❌" >> "$REPORT_PATH"
    fi
  fi

  echo >> "$REPORT_PATH"
  echo '```text' >> "$REPORT_PATH"
  sed -n '1,220p' "$out_file" >> "$REPORT_PATH"
  echo '```' >> "$REPORT_PATH"
  echo >> "$REPORT_PATH"

  rm -f "$out_file"
}

cat > "$REPORT_PATH" <<HDR
# Release Dry-Run Report

- Run ID: ${RUN_ID}
- Generated (UTC): $(date -u +"%Y-%m-%dT%H:%M:%SZ")
- Scope: qa-p0 + qa-p2(strict) + smoke + SSE/HITL verification + deploy-staging + health-check

HDR

cd "$ROOT_DIR"

log_step "Runbook step: QA P0" "QA_P0_HEALTH_MODE=strict QA_BOOTSTRAP_FRONTEND_DEPS=1 make qa-p0"
log_step "Runbook step: QA P2 (strict release mode)" "QA_STRICT_RELEASE=1 QA_BOOTSTRAP_FRONTEND_DEPS=1 make qa-p2"
log_step "Runbook step: backend smoke" "curl -sf ${HEALTH_URL}"
log_step "Runbook step: SSE/HITL verification (unit reliability)" \
  "python3 -m pytest tests/unit/test_budget_estimator_v2.py tests/unit/test_sse_broker_reliability.py tests/unit/test_run_manager_cancel_race.py tests/unit/test_hitl_approval_roundtrip.py -q"

if [[ "${ENABLE_STAGING_DEPLOY:-0}" == "1" ]]; then
  if docker info >/dev/null 2>&1; then
    log_step "Runbook step: deploy staging" "make deploy-staging"
    log_step "Runbook step: health-check after staging deploy" "make health-check"
  else
    log_step "Runbook step: deploy staging" \
      "echo 'Docker non disponibile: impossibile eseguire deploy staging reale' && exit 1"
    log_step "Runbook step: health-check after staging deploy" \
      "echo 'Docker non disponibile: impossibile eseguire health-check post deploy staging' && exit 1"
  fi
else
  log_step "Runbook step: deploy staging" \
    "echo 'ENABLE_STAGING_DEPLOY must be 1 for a valid release dry-run' && exit 1"
  log_step "Runbook step: health-check after staging deploy" \
    "echo 'ENABLE_STAGING_DEPLOY must be 1 for a valid release dry-run' && exit 1"
fi

{
  echo "## Summary"
  echo
  echo "- PASS: ${PASS}"
  echo "- WARN: ${WARN}"
  echo "- FAIL: ${FAIL}"
  echo
  if [[ "$FAIL" -eq 0 ]]; then
    echo "- GO/NO-GO: **GO (dry-run criteria met)**"
  else
    echo "- GO/NO-GO: **NO-GO (blocking failures detected)**"
  fi
} >> "$REPORT_PATH"

echo "Release dry-run report written to ${REPORT_PATH}"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi

exit 0
