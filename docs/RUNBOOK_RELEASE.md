# Runbook Release / Rollback

Questo documento definisce la procedura operativa minima per release candidate e rollback sicuro.

## 1. Pre-release checklist

1. Aggiorna branch e verifica working tree pulita.
2. Esegui gate QA:
   - `make qa-p0`
   - `make qa-p2`
3. Verifica smoke locale/ambiente target:
   - `curl -sf http://localhost:8000/health`
4. Conferma compatibilità SSE frontend/backend su `/api/runs/{doc_id}/events`.

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
- Health check verde.
- SSE + HITL verificati su ambiente target.

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
- timestamp deploy/rollback
- eventuali warning non bloccanti e piano di remediation
