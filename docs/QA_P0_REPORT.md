# QA P0 Gate Report

Generated: 2026-03-11T13:23:38Z

## Frontend runtime bootstrap

```bash
BOOTSTRAP_FRONTEND_DEPS=0 bash scripts/ensure_frontend_runtime.sh
```

- Status: PASS ✅

```text
[frontend-runtime] Frontend runtime/toolchain ready
```

## Unit suite (budget + SSE + cancel race + HITL roundtrip)

```bash
python3 -m pytest tests/unit/test_budget_estimator_v2.py tests/unit/test_sse_broker_reliability.py tests/unit/test_run_manager_cancel_race.py tests/unit/test_hitl_approval_roundtrip.py -q
```

- Status: PASS ✅

```text
.....................                                                    [100%]
21 passed, 3 skipped in 0.07s
```

## Frontend TypeScript check

```bash
node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json
```

- Status: PASS ✅

```text
```

## Frontend build

```bash
node frontend/node_modules/vite/bin/vite.js build frontend
```

- Status: PASS ✅

```text
vite v5.4.21 building for production...
transforming...

warn - The `content` option in your Tailwind CSS configuration is missing or empty.
warn - Configure your content sources or your generated CSS will be missing styles.
warn - https://tailwindcss.com/docs/content-configuration
✓ 850 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.60 kB │ gzip:   0.35 kB
dist/assets/index-CpydsCvG.css    5.64 kB │ gzip:   1.70 kB
dist/assets/index-CXtD2Kxe.js   609.39 kB │ gzip: 173.50 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 4.24s
```

## Backend health smoke (requires running backend)

```bash
curl -sf http://localhost:8000/health
```

- Status: WARN ⚠️

```text
```

## Summary

- PASS: 4
- WARN: 1
- FAIL: 0
