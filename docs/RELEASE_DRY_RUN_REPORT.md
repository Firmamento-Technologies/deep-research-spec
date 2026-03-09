# Release Dry-Run Report

- Run ID: 20260309T185752Z
- Generated (UTC): 2026-03-09T18:57:52Z
- Scope: qa-p0 + qa-p2(strict) + smoke + SSE/HITL verification + deploy-staging + health-check

## Runbook step: QA P0

```bash
make qa-p0
```

- Status: FAIL ❌

```text
make[1]: Entering directory '/workspace/deep-research-spec'
[36mRunning P0 QA gate checks...[0m
QA P0 report written to /workspace/deep-research-spec/docs/QA_P0_REPORT.md
make[1]: *** [Makefile:207: qa-p0] Error 1
make[1]: Leaving directory '/workspace/deep-research-spec'
```

## Runbook step: QA P2 (strict release mode)

```bash
QA_STRICT_RELEASE=1 make qa-p2
```

- Status: FAIL ❌

```text
make[1]: Entering directory '/workspace/deep-research-spec'
[36mRunning P2 QA checks...[0m
[qa-p2] Strict release mode enabled: frontend build and health smoke are blocking

==> Frontend runtime bootstrap
[frontend-runtime] Missing/incomplete frontend runtime
[frontend-runtime] Run with BOOTSTRAP_FRONTEND_DEPS=1 or execute: npm --prefix frontend ci
[FAIL] Frontend runtime bootstrap
Missing backend test dependencies: pytest_asyncio, fastapi
Install with: pip install -r backend/requirements.txt -r backend/requirements-test.txt
[qa-p2] Backend test dependencies missing: enabling fallback API contract checks

==> Frontend toolchain check
vite runtime missing: frontend/node_modules/vite/dist/node/cli.js
[FAIL] Frontend toolchain check

==> Backend API contract regression suite
Fallback API contract checks passed
[PASS] Backend API contract regression suite

==> Backend reliability/HITL race unit suite (fallback)
.....................                                                    [100%]
21 passed, 3 skipped in 0.10s
[PASS] Backend reliability/HITL race unit suite (fallback)

==> Frontend typecheck
[PASS] Frontend typecheck

==> Frontend build
npm warn Unknown env config "http-proxy". This will stop working in the next major version of npm.

> drs-frontend@0.1.0 build
> vite build

node:internal/modules/esm/resolve:274
    throw new ERR_MODULE_NOT_FOUND(
          ^

Error [ERR_MODULE_NOT_FOUND]: Cannot find module '/workspace/deep-research-spec/frontend/node_modules/vite/dist/node/cli.js' imported from /workspace/deep-research-spec/frontend/node_modules/vite/bin/vite.js
    at finalizeResolution (node:internal/modules/esm/resolve:274:11)
    at moduleResolve (node:internal/modules/esm/resolve:859:10)
    at defaultResolve (node:internal/modules/esm/resolve:983:11)
    at #cachedDefaultResolve (node:internal/modules/esm/loader:731:20)
    at ModuleLoader.resolve (node:internal/modules/esm/loader:708:38)
    at ModuleLoader.getModuleJobForImport (node:internal/modules/esm/loader:310:38)
    at onImport.tracePromise.__proto__ (node:internal/modules/esm/loader:664:36)
    at TracingChannel.tracePromise (node:diagnostics_channel:350:14)
    at ModuleLoader.import (node:internal/modules/esm/loader:663:21)
    at defaultImportModuleDynamicallyForModule (node:internal/modules/esm/utils:222:31) {
  code: 'ERR_MODULE_NOT_FOUND',
  url: 'file:///workspace/deep-research-spec/frontend/node_modules/vite/dist/node/cli.js'
}

Node.js v22.21.1
[FAIL] Frontend build

==> Backend /health smoke
[FAIL] Backend /health smoke

===============================
P2 QA summary
PASS: 3
WARN: 0
FAIL: 4
===============================
make[1]: *** [Makefile:211: qa-p2] Error 1
make[1]: Leaving directory '/workspace/deep-research-spec'
```

## Runbook step: backend smoke

```bash
curl -sf http://localhost:8000/health
```

- Status: FAIL ❌

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

## Runbook step: deploy staging

```bash
echo 'Docker non disponibile: impossibile eseguire deploy staging reale' && exit 1
```

- Status: FAIL ❌

```text
Docker non disponibile: impossibile eseguire deploy staging reale
```

## Runbook step: health-check after staging deploy

```bash
echo 'Docker non disponibile: impossibile eseguire health-check post deploy staging' && exit 1
```

- Status: FAIL ❌

```text
Docker non disponibile: impossibile eseguire health-check post deploy staging
```

## Summary

- PASS: 1
- WARN: 0
- FAIL: 5

- GO/NO-GO: **NO-GO (blocking failures detected)**
