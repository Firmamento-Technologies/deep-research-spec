# HANDOVER — Deep Research System (DRS)

Documento di continuita per trasferimento su nuovo PC.
Ultimo aggiornamento: 2026-03-13

---

## Stack tecnologico

### Backend
| Componente | Versione |
|-----------|---------|
| Python | 3.11+ |
| FastAPI | >= 0.115 |
| Uvicorn | >= 0.32 |
| SQLAlchemy (async) | >= 2.0 |
| asyncpg | >= 0.29 |
| LangGraph | >= 0.2 |
| Pydantic | >= 2.0 |
| httpx | >= 0.27 |
| Redis (client) | >= 5.0 |
| MinIO (client) | >= 7.2 |
| Alembic | >= 1.13 |
| python-docx | >= 1.1 |
| tiktoken | >= 0.7 |
| prometheus-client | >= 0.21 |

### Frontend
| Componente | Versione |
|-----------|---------|
| Node.js | >= 24.x (usato 24.13.1) |
| React | 18.3 |
| TypeScript | 5.5+ |
| Vite | 5.3+ |
| Tailwind CSS | 3.4+ |
| Zustand | 4.5+ (state management) |
| React Router DOM | 6.26+ |
| Recharts | 2.12+ (analytics charts) |
| Framer Motion | 11.3+ (animazioni) |
| @dnd-kit | 6.1+ / 8.0+ (drag & drop HITL) |
| react-markdown | 9.0+ |

### Infrastruttura (Docker)
| Servizio | Immagine |
|----------|---------|
| PostgreSQL 16 | postgres:16-alpine |
| Redis 7 | redis:7-alpine |
| MinIO | minio/minio:latest |
| Prometheus | prom/prometheus:latest |
| Grafana | grafana/grafana:latest |

### LLM
| Provider | Uso |
|----------|-----|
| OpenRouter | Companion chat (Claude Sonnet 4), Writer, Jury judges, Reflector |
| Modelli usati | gemini-2.5-flash (economy), claude-sonnet-4 (balanced/premium) |

---

## Struttura cartelle principali

```
deep-research-spec/
├── backend/                # FastAPI app
│   ├── api/                # Route handlers (runs, spaces, companion, auth, settings)
│   ├── database/           # Models SQLAlchemy, schemas Pydantic, connection
│   ├── services/           # Business logic (run_manager, space_indexer, embedder, auth)
│   ├── config/             # Settings da env vars
│   ├── prompts/            # System prompt per Companion chat
│   └── main.py             # App FastAPI entry point
├── frontend/               # React + Vite SPA
│   ├── src/
│   │   ├── pages/          # Dashboard, NewResearch, KnowledgeSpaces, SpaceDetail, Analytics, Settings
│   │   ├── components/     # UI (layout/, pipeline/, chat/, hitl/, panel/, ui/)
│   │   ├── store/          # Zustand stores (useAppStore, useRunStore, useConversationStore)
│   │   ├── hooks/          # useSSE (Server-Sent Events), useKeyboardShortcuts
│   │   ├── lib/            # api.ts (HTTP client), query.tsx (custom hooks), icons.tsx
│   │   ├── types/          # TypeScript types (run.ts, api.ts)
│   │   ├── contexts/       # AuthContext
│   │   └── constants/      # pipeline-layout.ts, pipeline-edges.ts
│   └── package.json
├── src/                    # LangGraph pipeline (core DRS engine)
│   ├── graph/
│   │   ├── nodes/          # Tutti i nodi del grafo (writer, jury, reflector, planner, ecc.)
│   │   ├── internals/      # writer_memory, state helpers
│   │   └── graph.py        # build_graph() — definizione del grafo LangGraph
│   ├── llm/                # client.py (multi-provider), routing.py (model selection)
│   └── main.py             # CLI entry point per pipeline
├── output/                 # Output delle ricerche (gitignored)
├── config/                 # Prometheus, Grafana configs
├── docker/                 # init.sql, Dockerfiles
├── docker-compose.yml      # Stack completo
├── docker-compose.override.yml  # Override per dev (hot reload, porta 5433)
├── .env.example            # Template variabili d'ambiente
└── requirements.txt        # Dipendenze Python
```

---

## Cosa e' stato fatto

### Infrastruttura
- [x] Docker Compose con PostgreSQL 16 + pgvector, Redis 7, MinIO, Prometheus, Grafana
- [x] Backend FastAPI con autenticazione JWT (register/login/roles)
- [x] Frontend React + Vite + Tailwind con dark theme DRS
- [x] CORS configurato, health check endpoints

### Pipeline di ricerca (LangGraph)
- [x] Grafo completo con 40+ nodi: Planner, Researcher, Writer, Jury (3 giudici x 3 tipi), Reflector, Aggregator, PostQA, Coherence Guard, Budget Controller, ecc.
- [x] Preset qualita (Economy/Balanced/Premium) con routing modelli diversi
- [x] Budget controller con allarmi 70%/90% e hard stop
- [x] CSS scoring (Content, Style, Source) con soglie configurabili
- [x] HITL (Human-in-the-Loop): approvazione outline, revisione sezioni, escalation
- [x] Output in Markdown e DOCX
- [x] Pipeline eseguibile da CLI (`python -m src.main`)
- [x] SSE (Server-Sent Events) per streaming stato in tempo reale

### Frontend UI
- [x] Navigazione completa: Dashboard, Nuova Ricerca, Spaces, Analytics, Settings
- [x] Pagina "Nuova Ricerca" con form completo (topic, preset, budget, parole, stile, knowledge space)
- [x] Knowledge Spaces: creazione, lista, upload documenti, ricerca semantica
- [x] AppShell layout con Topbar, DocumentSidebar, MainArea, RightPanel, ChatInput
- [x] PipelineCanvas: visualizzazione grafo interattivo con zoom/pan, nodi animati
- [x] Companion Chat via OpenRouter (Claude Sonnet 4)
- [x] Dashboard con banner run attivo, lista ricerche recenti
- [x] Dark theme coerente su tutte le pagine
- [x] Auth flow: Login, Register, ProtectedRoute con ruoli

### Backend API
- [x] `POST /api/runs` — avvia ricerca
- [x] `GET /api/runs` — lista ricerche
- [x] `GET /api/runs/:id/events` — SSE stream
- [x] `POST /api/runs/:id/approve-outline` — HITL outline
- [x] `POST /api/runs/:id/approve-section` — HITL sezione
- [x] `POST /api/companion/chat` — Companion AI
- [x] CRUD completo Knowledge Spaces + upload + indexing + semantic search
- [x] Auth endpoints (register, login, token refresh)

---

## Cosa resta da fare (priorita)

### Alta priorita
- [ ] **Fix upload file in Knowledge Spaces**: il MIME type detection dal backend non funziona per file `.md` (invia `application/octet-stream`). Il fix nel codice c'e' ma va verificato che uvicorn lo carichi correttamente
- [ ] **Fix `post_draft_analyzer`**: il nodo funziona ma il PostQA alla fine della pipeline crasha con `'NoneType' object has no attribute 'get'` in `await_human.py` quando `reflector_output` e' None in certi edge case
- [ ] **Companion chat → pipeline**: quando il Companion emette `START_RUN`, la transizione a `PROCESSING` e visualizzazione pipeline va testata end-to-end
- [ ] **SSE events rendering**: verificare che tutti gli eventi SSE (NODE_STARTED, NODE_COMPLETED, CSS_UPDATE, BUDGET_UPDATE, HUMAN_REQUIRED, PIPELINE_DONE) aggiornino correttamente la UI

### Media priorita
- [ ] **Export documenti**: il bottone "Esporta tutto" nella sidebar non e' ancora collegato
- [ ] **Ricerche completate**: visualizzazione e download dei documenti generati dalle ricerche precedenti
- [ ] **Context compressor**: usa provider `qwen` che non e' supportato, fallback su heuristic
- [ ] **JudgeF micro-search**: usa provider `perplexity` che non e' supportato, fallisce silenziosamente
- [ ] **Writer Memory**: `update_writer_memory` import fallisce nel section_checkpoint
- [ ] **Database migrations**: eseguire Alembic migrations su setup iniziale

### Bassa priorita
- [ ] **Model selector dropdown** nella Topbar (attualmente fisso su claude-sonnet-4)
- [ ] **Profilo utente** pagina `/profile` (referenziata ma non implementata)
- [ ] **Sidebar completed runs**: click su run completati per rivederli
- [ ] **Progress reale upload**: `fetch` API non supporta upload progress come XMLHttpRequest
- [ ] **Icone SVG reali**: tutte le icone in `icons.tsx` sono placeholder (cerchi), servono icone reali (Lucide o simili)
- [ ] **SHINE LoRA**: integrazione opzionale per fine-tuning stile scrittura
- [ ] **RLM mode**: Recursive Language Models (disattivato, sperimentale)

---

## Bug aperti / problemi noti

1. **Upload .md fallisce** — Il browser invia `application/octet-stream` per file `.md`. Il fix di fallback per estensione e' nel codice (`knowledge_spaces.py`) ma potrebbe non essere stato caricato dal server
2. **Pipeline crash su PostQA** — `await_human.py:70` puo' crashare quando `reflector_output` e' None. Fix `or {}` presente ma il nodo PostQA a valle ha un bug separato
3. **`post_draft_analyzer` NameError** — Fixato: `_analyse_draft()` usava `state` non definito, ora usa parametro `quality_preset`
4. **Provider non supportati nei log** — `perplexity/sonar` (JudgeF) e `qwen/qwen3-7b` (context_compressor) non sono configurati in OpenRouter
5. **`onUploadProgress` fake** — Il client `api.ts` usa `fetch` nativo che non supporta upload progress; la callback emette solo 0% e 100%
6. **Icone tutte uguali** — `lib/icons.tsx` esporta tutte le icone come cerchi SVG placeholder

---

## Setup da zero su nuova macchina

### Prerequisiti
- Python 3.11+
- Node.js 24+ (o 20+)
- Docker Desktop (per PostgreSQL, Redis, MinIO)
- Git

### Step 1: Clone e setup ambiente
```bash
git clone https://github.com/Firmamento-Technologies/deep-research-spec.git
cd deep-research-spec

# Crea .env da template
cp .env.example .env
# MODIFICA .env con le tue API keys (almeno OPENROUTER_API_KEY)
```

### Step 2: Avvia i servizi Docker
```bash
docker-compose up -d postgres redis minio
# Aspetta che siano healthy:
docker-compose ps
```

### Step 3: Setup backend
```bash
python -m venv venv
# Windows:
source venv/Scripts/activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt

cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Setup frontend
```bash
cd frontend
npm install
npm run dev
# Apri http://localhost:3001
```

### Step 5: Primo accesso
1. Vai su http://localhost:3001/register
2. Crea un utente
3. Login
4. Vai su "Nuova Ricerca" dalla navbar per avviare una ricerca

### Comandi utili
```bash
# Pipeline da CLI (senza UI):
cd deep-research-spec
source venv/Scripts/activate
python -m src.main --topic "Il tuo argomento" --preset Balanced

# Build frontend per produzione:
cd frontend && npx vite build

# Test Python:
pytest tests/ -v

# Docker completo (backend + frontend + infra):
docker-compose up --build
```

---

## Variabili d'ambiente necessarie

| Variabile | Descrizione | Obbligatoria |
|-----------|-------------|:---:|
| `OPENROUTER_API_KEY` | Chiave API OpenRouter (per LLM e Companion) | Si |
| `POSTGRES_PASSWORD` | Password PostgreSQL (default: `drs_dev_password`) | Si |
| `DATABASE_URL` | Connection string PostgreSQL async | Si |
| `REDIS_URL` | Connection string Redis | Si |
| `MINIO_ROOT_USER` | MinIO admin user | No |
| `MINIO_ROOT_PASSWORD` | MinIO admin password | No |
| `MINIO_ENDPOINT` | MinIO endpoint | No |
| `ANTHROPIC_API_KEY` | Chiave Anthropic (opzionale, alternativa a OpenRouter) | No |
| `OPENAI_API_KEY` | Chiave OpenAI (opzionale) | No |
| `GOOGLE_API_KEY` | Chiave Google AI (opzionale) | No |
| `MAX_BUDGET` | Budget massimo default ($) | No |
| `RLM_MODE` | Abilita Recursive Language Models (default: false) | No |
| `SHINE_SERVING_URL` | URL endpoint LoRA serving (opzionale) | No |
| `LOG_LEVEL` | Livello log (default: INFO) | No |
| `API_HOST` | Host API (default: 0.0.0.0) | No |
| `API_PORT` | Porta API (default: 8000) | No |

---

## Note architetturali

- **Il frontend comunica col backend via API REST + SSE**. Non ci sono WebSocket.
- **La pipeline LangGraph gira in-process** nel backend FastAPI come task asincrono.
- **L'auth usa JWT** con token in localStorage (frontend) e Bearer header.
- **Il Companion Chat** usa OpenRouter con `anthropic/claude-sonnet-4` e response_format JSON.
- **Knowledge Spaces** usano pgvector (384 dim, all-MiniLM-L6-v2) per semantic search.
- **PostgreSQL sulla porta 5433** in dev (override) per evitare conflitti con installazioni locali.
