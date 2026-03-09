# QA GO/NO-GO Checklist (Definitiva)

Questa checklist definisce il gate minimo per dichiarare il software pronto al test QA integrato.

## 1) Frontend Build (bloccante)

- [ ] `npm ci` in `frontend/` completa senza errori.
- [ ] `npm run build` in `frontend/` produce `dist/`.
- [ ] Nessun errore TypeScript (`tsc --noEmit`) sulla codebase frontend.

**GO** solo se tutti i punti sono verdi.

## 2) Backend Core Health (bloccante)

- [ ] Backend avviabile con `uvicorn main:app` da `backend/`.
- [ ] `GET /health` risponde 200.
- [ ] Companion endpoint disponibile: `POST /api/companion/chat`.

## 3) Run Companion (bloccante funzionale)

- [ ] Da UI è possibile aprire Companion durante run attivo.
- [ ] Toggle Companion ↔ Grafo funzionante durante stato `PROCESSING`.
- [ ] In assenza chiave OpenRouter, errore utente chiaro e non-crash.

## 4) Grafo Architettura (bloccante UX)

- [ ] Modalità grafo disponibili: Core / Quality / Full.
- [ ] Nodi/edge coerenti con modalità selezionata.
- [ ] Minimap coerente con subset visibile.
- [ ] Leggibilità verificata (lane di fase + labels non sovraccariche).

## 5) API/HITL (bloccante funzionale)

- [ ] Endpoint `approve-outline`/`approve-section` testati.
- [ ] Resume del grafo da HITL verificato end-to-end (outline + section approval).
- [ ] Endpoint SSE `GET /api/runs/{doc_id}/events` disponibile (compatibilità frontend).

## 6) Test automatici minimi richiesti

- [ ] `python3 -m pip install -r backend/requirements.txt -r backend/requirements-test.txt`
- [ ] `python3 -m pytest tests/unit/test_budget_estimator_v2.py -q`
- [ ] `node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json`
- [ ] `npm --prefix frontend run build`

## 7) Evidenze esecuzione gate

Compilare ad ogni release candidate:

- [ ] `make qa-p0` (genera `docs/QA_P0_REPORT.md` con evidenze)
- [ ] `make qa-p2` (suite P2: contract API + HITL/race + frontend type/build + smoke)
- [ ] In CI release: `QA_STRICT_RELEASE=1 make qa-p2` (build frontend + smoke health diventano bloccanti)
- [ ] `make release-dry-run` (report unico con timestamp + GO/NO-GO)
- [ ] `python3 -m pytest backend/tests/test_api_endpoints.py -q`
- [ ] Smoke API: `curl -sf http://localhost:8000/health`
- [ ] NO skip strutturali: deploy/health staging devono essere realmente eseguiti nel dry-run

---

## Criterio finale

- **GO QA**: sezioni 1, 2, 3, 4, 5, 6 e 7 complete con evidenze archiviate (`docs/QA_P0_REPORT.md`, `docs/RELEASE_DRY_RUN_REPORT.md`).
- **NO-GO QA**: fallimento di uno qualsiasi dei gate bloccanti o regressioni runtime.
