# Release Dry-Run Report

- Run ID: 20260309T005620Z
- Generated (UTC): 2026-03-09T00:56:20Z
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

- Status: FAIL ❌

```text
make[1]: Entering directory '/workspace/deep-research-spec'
[36mRunning P2 QA checks...[0m

==> Backend test dependency check
Missing backend test dependencies: httpx
Install with: pip install -r backend/requirements.txt pytest pytest-asyncio
[FAIL] Backend test dependency check

==> Frontend toolchain check
[PASS] Frontend toolchain check

==> Backend API contract regression suite
ImportError while loading conftest '/workspace/deep-research-spec/backend/tests/conftest.py'.
backend/tests/conftest.py:6: in <module>
    from httpx import AsyncClient
E   ModuleNotFoundError: No module named 'httpx'
[FAIL] Backend API contract regression suite

==> Backend reliability/HITL race unit suite
.....................                                                    [100%]
21 passed, 3 skipped in 0.06s
[PASS] Backend reliability/HITL race unit suite

==> Frontend typecheck
[PASS] Frontend typecheck

==> Frontend build (warn-mode in constrained env)
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
[WARN] Frontend build (warn-mode in constrained env)

==> Backend /health smoke (warn if service not running)
[WARN] Backend /health smoke (warn if service not running)

===============================
P2 QA summary
PASS: 3
WARN: 2
FAIL: 2
===============================
make[1]: *** [Makefile:211: qa-p2] Error 1
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
python3 -m pytest tests/unit/test_hitl_approval_roundtrip.py tests/unit/test_sse_broker_reliability.py -q
```

- Status: FAIL ❌

```text

2 skipped in 0.04s
```

## Runbook step: deploy staging (disabled)

```bash
echo 'Set ENABLE_STAGING_DEPLOY=1 to execute make deploy-staging && make health-check' && exit 1
```

- Status: WARN ⚠️

```text
Set ENABLE_STAGING_DEPLOY=1 to execute make deploy-staging && make health-check
```

## Summary

- PASS: 1
- WARN: 2
- FAIL: 2

- GO/NO-GO: **NO-GO (blocking failures detected)**
