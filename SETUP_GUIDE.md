# Deep Research System — Setup operativo (stato corrente)

Guida aggiornata per avviare e testare il progetto in modo consistente.

## 1) Prerequisiti

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose

## 2) Repository e branch

```bash
git clone https://github.com/lucadidomenicodopehubs/deep-research-spec.git
cd deep-research-spec
# checkout del branch su cui vuoi lavorare
```

## 3) Backend (canonico)

Il backend applicativo è sotto `backend/`.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Avvio backend:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

## 4) Frontend

```bash
cd frontend
npm ci
npm run dev
```

UI: `http://localhost:3001`

## 5) Infrastruttura Docker (opzionale ma consigliata)

```bash
docker compose up -d postgres redis minio
```

## 6) Test minimi consigliati

```bash
# backend (dal root repo)
python3 -m pytest tests/unit/test_budget_estimator_v2.py -q

# frontend
npm --prefix frontend run build
```

## Troubleshooting rapido

- Se `npm ci` fallisce: verifica proxy/registry npm e autorizzazioni di rete.
- Se il backend non parte: ricontrolla variabili `.env` e dipendenze Python installate.
- Se Docker non è disponibile, puoi avviare backend/frontend senza stack completo (ma alcune feature non saranno operative).
