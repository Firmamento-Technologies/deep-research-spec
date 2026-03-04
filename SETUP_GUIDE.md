# Deep Research System - Setup Completo

## 🚀 Quick Start (5 minuti)

### 1. Clone e Checkout Branch

```bash
cd C:\Users\Luca
git clone https://github.com/lucadidomenicodopehubs/deep-research-spec
cd deep-research-spec
git checkout fix/ui-issues-and-docker-config
git pull origin fix/ui-issues-and-docker-config
```

### 2. Avvia Infrastruttura con Docker

```bash
# Avvia PostgreSQL, Redis, MinIO
docker-compose up -d postgres redis minio

# Attendi 15 secondi per l'inizializzazione
```

### 3. Installa Dipendenze Python

```bash
cd backend
pip install -r requirements.txt
pip install -r requirements_knowledge_spaces.txt
```

### 4. Verifica Configurazione

```bash
# Il file .env è già presente nella root del progetto
# Contiene la tua OPENROUTER_API_KEY

# Verifica che PostgreSQL sia running
docker exec -it drs-postgres psql -U drs -d drs -c "SELECT version();"
```

### 5. Avvia Backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Testa

```bash
# Altro terminale
curl http://localhost:8000/health

# Oppure apri browser
start http://localhost:8000/docs
```

---

## 🔧 Troubleshooting

### Errore: `ImportError: cannot import name 'get_db_session'`

**Causa**: Il codice usa `get_db_session()` ma `database/connection.py` esporta `get_db()`.

**Fix**:
```bash
cd backend
# Sostituisci tutte le occorrenze
(Get-Content api/knowledge_spaces.py) -replace 'get_db_session', 'get_db' | Set-Content api/knowledge_spaces.py
```

### Errore: `asyncpg.exceptions.InvalidPasswordError`

**Causa**: PostgreSQL non ha ancora processato la password.

**Fix**:
```bash
# Ricrea container
docker stop drs-postgres && docker rm drs-postgres
docker-compose up -d postgres
Start-Sleep -Seconds 15
```

### Errore: `ModuleNotFoundError: No module named 'langgraph'`

**Fix**: Pull del branch aggiornato
```bash
git pull origin fix/ui-issues-and-docker-config
cd backend
pip install -r requirements.txt
```

---

## 📦 Servizi Docker

| Servizio   | Porta | Credenziali             | URL                       |
|------------|-------|-------------------------|---------------------------|
| PostgreSQL | 5432  | `drs:drs_dev_password`  | localhost:5432            |
| Redis      | 6379  | (nessuna)               | localhost:6379            |
| MinIO      | 9000  | `drs_admin:drs_secret_key` | http://localhost:9000 |
| MinIO UI   | 9001  | `drs_admin:drs_secret_key` | http://localhost:9001 |
| Backend    | 8000  | (nessuna)               | http://localhost:8000     |
| Prometheus | 9091  | (nessuna)               | http://localhost:9091     |
| Grafana    | 3002  | `admin:admin`           | http://localhost:3002     |

---

## 🔐 Variabili Ambiente (`.env`)

Il file `.env` è già configurato con:
- ✅ OPENROUTER_API_KEY (tua chiave)
- ✅ DATABASE_URL corretto
- ✅ Credenziali PostgreSQL/MinIO/Redis

**⚠️ IMPORTANTE**: Il file `.env` è ora in `.gitignore` e **NON verrà committato**.

---

## 🛠️ Comandi Utili

```bash
# Logs di tutti i servizi
docker-compose logs -f

# Logs solo PostgreSQL
docker logs -f drs-postgres

# Entra in PostgreSQL
docker exec -it drs-postgres psql -U drs -d drs

# Restart servizio singolo
docker-compose restart postgres

# Stop tutto
docker-compose down

# Stop e rimuovi volumi (reset completo)
docker-compose down -v
```

---

## 📝 Prossimi Step

1. ✅ Backend funzionante
2. ⏳ Test endpoint API
3. ⏳ Avvio Frontend
4. ⏳ Test workflow completo

---

## 🆘 Supporto

Se hai problemi:
1. Controlla i logs: `docker-compose logs -f`
2. Verifica `.env`: `type .env`
3. Testa connessione DB: `python test_asyncpg.py` (se esiste)
