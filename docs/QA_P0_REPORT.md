# QA P0 Gate Report

Generated: 2026-03-09T16:28:16Z

## Unit suite (budget + SSE + cancel race + HITL roundtrip)

\`\`\`bash
python3 -m pytest tests/unit/test_budget_estimator_v2.py tests/unit/test_sse_broker_reliability.py tests/unit/test_run_manager_cancel_race.py tests/unit/test_hitl_approval_roundtrip.py -q
\`\`\`

- Status: PASS ✅

\`\`\`text
.....................                                                    [100%]
21 passed, 3 skipped in 0.08s
\`\`\`

## Frontend TypeScript check

\`\`\`bash
node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json
\`\`\`

- Status: PASS ✅

\`\`\`text
\`\`\`

## Frontend build

\`\`\`bash
npm --prefix frontend run build
\`\`\`

- Status: FAIL ❌

\`\`\`text
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
\`\`\`

## Backend health smoke (requires running backend on :8000)

\`\`\`bash
curl -sf http://localhost:8000/health
\`\`\`

- Status: FAIL ❌

\`\`\`text
\`\`\`

## Summary

- PASS: 2
- WARN: 0
- FAIL: 2
