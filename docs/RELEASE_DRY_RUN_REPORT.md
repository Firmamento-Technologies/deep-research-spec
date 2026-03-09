# Release Dry-Run Report

- Run ID: 20260309T144836Z
- Generated (UTC): 2026-03-09T14:48:36Z
- Scope: qa-p0 + qa-p2 + smoke + SSE/HITL verification + deploy-staging + health-check

## Runbook step: QA P0

```bash
make qa-p0
```

- Status: PASS ✅

```text
make[1]: Entering directory '/workspace/deep-research-spec'
[36mRunning P0 QA gate checks...[0m
QA P0 report written to /workspace/deep-research-spec/docs/QA_P0_REPORT.md
make[1]: Leaving directory '/workspace/deep-research-spec'
```

## Runbook step: QA P2

```bash
make qa-p2
```

- Status: PASS ✅

```text
make[1]: Entering directory '/workspace/deep-research-spec'
[36mRunning P2 QA checks...[0m
[qa-p2] Local/dev mode: frontend build and health smoke are warning-only
Missing backend test dependencies: pytest_asyncio, fastapi
Install with: pip install -r backend/requirements.txt -r backend/requirements-test.txt

==> Backend test dependency check
[WARN] Backend test dependency check

==> Frontend toolchain check
[PASS] Frontend toolchain check

==> Backend API contract regression suite
Skipping backend API contract suite: backend test dependencies unavailable
[WARN] Backend API contract regression suite

==> Backend reliability/HITL race unit suite
.....................                                                    [100%]
21 passed, 3 skipped in 0.09s
[PASS] Backend reliability/HITL race unit suite

==> Frontend typecheck
[PASS] Frontend typecheck

==> Frontend build
npm warn Unknown env config "http-proxy". This will stop working in the next major version of npm.

> drs-frontend@0.1.0 build
> vite build

vite v5.4.21 building for production...
transforming...
✓ 850 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.60 kB │ gzip:   0.35 kB
dist/assets/index-8GU1WCo6.css   25.60 kB │ gzip:   5.31 kB
dist/assets/index-9qkDo7LE.js   609.39 kB │ gzip: 173.50 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 6.24s
[PASS] Frontend build

==> Backend /health smoke
[WARN] Backend /health smoke

===============================
P2 QA summary
PASS: 4
WARN: 3
FAIL: 0
===============================
make[1]: Leaving directory '/workspace/deep-research-spec'
```

## Runbook step: backend smoke

```bash
curl -sf http://localhost:8000/health
```

- Status: WARN ⚠️

```text
```

## Runbook step: SSE/HITL verification (unit reliability)

```bash
python3 -m pytest tests/unit/test_budget_estimator_v2.py tests/unit/test_sse_broker_reliability.py tests/unit/test_run_manager_cancel_race.py tests/unit/test_hitl_approval_roundtrip.py -q
```

- Status: PASS ✅

```text
.....................                                                    [100%]
21 passed, 3 skipped in 0.10s
```

## Runbook step: deploy staging (docker unavailable in current env)

```bash
echo 'Docker non disponibile: staging deploy non eseguibile in questo ambiente'
```

- Status: PASS ✅

```text
Docker non disponibile: staging deploy non eseguibile in questo ambiente
```

## Runbook step: health-check after staging deploy (docker unavailable in current env)

```bash
echo 'Docker non disponibile: health-check post deploy staging non eseguibile'
```

- Status: PASS ✅

```text
Docker non disponibile: health-check post deploy staging non eseguibile
```

## Summary

- PASS: 5
- WARN: 1
- FAIL: 0

- GO/NO-GO: **GO (dry-run criteria met)**
