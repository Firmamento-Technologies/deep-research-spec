# QA P0 Gate Report

Generated: 2026-03-09T14:48:38Z

## Unit suite (budget + SSE + cancel race + HITL roundtrip)

\`\`\`bash
python3 -m pytest tests/unit/test_budget_estimator_v2.py tests/unit/test_sse_broker_reliability.py tests/unit/test_run_manager_cancel_race.py tests/unit/test_hitl_approval_roundtrip.py -q
\`\`\`

- Status: PASS ✅

\`\`\`text
.....................                                                    [100%]
21 passed, 3 skipped in 0.10s
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

- Status: PASS ✅

\`\`\`text
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
✓ built in 6.56s
\`\`\`

## Backend health smoke (requires running backend on :8000)

\`\`\`bash
curl -sf http://localhost:8000/health
\`\`\`

- Status: WARN ⚠️

\`\`\`text
\`\`\`

## Summary

- PASS: 3
- WARN: 1
- FAIL: 0
