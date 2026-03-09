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

## 6) Test automatici minimi richiesti

- [ ] `python3 -m pytest tests/unit/test_budget_estimator_v2.py -q`
- [ ] `node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json`
- [ ] `npm --prefix frontend run build`

---

## Criterio finale

- **GO QA**: sezioni 1,2,3,4,5,6 complete.
- **NO-GO QA**: fallimento di uno qualsiasi dei gate bloccanti o regressioni runtime.


## 7) Evidenze esecuzione gate

Compilare ad ogni release candidate:

- [ ] `make qa-p0` (genera `docs/QA_P0_REPORT.md` con evidenze)

- [ ] `python3 -m pytest tests/unit/test_budget_estimator_v2.py tests/unit/test_sse_broker_reliability.py tests/unit/test_run_manager_cancel_race.py -q`
- [ ] `node frontend/node_modules/typescript/bin/tsc --noEmit -p frontend/tsconfig.json`
- [ ] `npm --prefix frontend run build`
- [ ] Smoke API: `curl -sf http://localhost:8000/health`
- [ ] HITL API smoke: `POST /api/runs/{doc_id}/approve-outline` + `POST /api/runs/{doc_id}/approve-section` su run attivo
