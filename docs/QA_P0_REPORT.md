# QA P0 Gate Report

Generated: 2026-03-09T00:29:58Z

## Unit suite (budget + SSE + cancel race + HITL roundtrip)

\`\`\`bash
python3 -m pytest tests/unit/test_budget_estimator_v2.py tests/unit/test_sse_broker_reliability.py tests/unit/test_run_manager_cancel_race.py tests/unit/test_hitl_approval_roundtrip.py -q
\`\`\`

- Status: PASS ✅

\`\`\`text
.....................                                                    [100%]
21 passed, 3 skipped in 0.07s
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

- Status: WARN ⚠️

\`\`\`text
npm warn Unknown env config "http-proxy". This will stop working in the next major version of npm.

> drs-frontend@0.1.0 build
> vite build

sh: 1: vite: Permission denied
\`\`\`

## Backend health smoke (requires running backend on :8000)

\`\`\`bash
curl -sf http://localhost:8000/health
\`\`\`

- Status: WARN ⚠️

\`\`\`text
\`\`\`

## Summary

- PASS: 2
- WARN: 2
- FAIL: 0
