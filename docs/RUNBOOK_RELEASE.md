# Runbook Release / Rollback

Questo documento definisce la procedura operativa minima per release candidate e rollback sicuro.

## 1. Pre-release checklist

1. Aggiorna branch e verifica working tree pulita.
2. Prepara ambiente QA:
   - `python3 -m pip install -r backend/requirements.txt -r backend/requirements-test.txt`
   - `npm --prefix frontend ci`
3. Esegui gate QA:
   - `make qa-p0`
   - `make qa-p2`
   - In release CI: `QA_STRICT_RELEASE=1 make qa-p2`
4. Esegui dry-run release con evidenze aggregate:
   - `make release-dry-run`
5. Verifica smoke locale/ambiente target:
   - `curl -sf http://localhost:8000/health`
6. Conferma compatibilità SSE frontend/backend su `/api/runs/{doc_id}/events`.

### Variabili utili per i gate

- `QA_STRICT_RELEASE=1`: promuove check build/health a bloccanti in `qa-p2`.
- `QA_HEALTH_URL=<url>`: override endpoint smoke health (default `http://localhost:8000/health`).
- `QA_BOOTSTRAP_FRONTEND_DEPS=1`: abilita bootstrap automatico dipendenze frontend durante i gate (`ensure_frontend_runtime.sh`).
- `QA_P0_HEALTH_MODE=warn|strict`: in `qa-p0` rende lo smoke health warning-only (`warn`, default) o bloccante (`strict`).


## 2. Deploy standard

1. Deploy su staging:
   - `make deploy-staging`
2. Verifica servizi:
   - `make health-check`
3. Validazione funzionale minima:
   - apertura UI
   - creazione run (`POST /api/runs`)
   - connessione SSE (`/api/runs/{doc_id}/events`)
   - almeno un ciclo HITL (`approve-outline` o `approve-section`)

4. Deploy production (dopo GO esplicito):
   - `make deploy-prod`

## 3. GO / NO-GO decision

### GO se:
- Gate `qa-p0` e `qa-p2` senza failure bloccanti.
- In release CI, nessun warning residuo sui check frontend build e `/health` (promossi a fail via `QA_STRICT_RELEASE=1`).
- Health check verde.
- SSE + HITL verificati su ambiente target.
- Nessun pass di contesto/skip strutturale (deploy staging e health-check post deploy realmente eseguiti).

### NO-GO se:
- Errori build frontend o regressioni API contrattuali.
- Failure su endpoint critici (`/health`, `/api/runs`, approve HITL).
- Event stream non ricevibile da frontend.

## 4. Rollback

1. Identifica versione stabile precedente (`VERSION`).
2. Esegui rollback:
   - `make rollback VERSION=<tag>`
3. Riesegui health check:
   - `make health-check`
4. Riesegui smoke endpoint critici:
   - `/health`
   - `/api/runs`
   - `/api/runs/{doc_id}/events`
5. Registra incidente + evidenze nei log release.

## 5. Post-release evidences

Archivia sempre:
- output `make qa-p0`
- output `make qa-p2`
- output `make release-dry-run` (`docs/RELEASE_DRY_RUN_REPORT.md`)
- timestamp deploy/rollback
- eventuali warning non bloccanti e piano di remediation
