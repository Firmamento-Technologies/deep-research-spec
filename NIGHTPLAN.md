# PIANO DI LAVORO NOTTURNO — DRS

Piano organizzato per plugin disponibili su Claude Code.
Ogni task ha un plugin assegnato e un ordine di esecuzione.

---

## Plugin disponibili

| Plugin | Shortcut | Uso ideale |
|--------|----------|------------|
| **Context7** | — | Leggere docs librerie, capire API, risolvere bug con contesto aggiornato |
| **Claude Mem** | — | Memorizzare decisioni, stato avanzamento, contesto tra sessioni |
| **Code Review** | `/code-review` | Audit qualita codice, trovare bug nascosti, suggerire fix |
| **Frontend Design** | — | Migliorare UI/UX, layout, componenti, responsive design |
| **Ralph Loop** | `/ralph` | Iterazione continua: fix → test → fix su problemi complessi |

---

## FASE 1 — Bug critici (prima di tutto)

### 1.1 Fix upload file Knowledge Spaces
**Plugin: Ralph Loop (`/ralph`)**
**Priorita: CRITICA**

Il caricamento file `.md` (e potenzialmente altri) fallisce con `Unsupported file type: application/octet-stream`.

**Problema**: Il fix nel backend (`knowledge_spaces.py` linee 264-278) che fa fallback dal MIME type all'estensione del file c'e' nel codice ma NON funziona. Probabilmente:
- Il `content_type` inferito non viene usato nel posto giusto
- Oppure FastAPI/Starlette sovrascrive il content_type prima di arrivare alla funzione

**Azione**:
```
/ralph Fissa il bug upload file in backend/api/knowledge_spaces.py.
Il browser manda application/octet-stream per file .md.
Il codice di fallback per estensione (linee 264-278) non funziona.
Debugga: stampa il valore di file.content_type e file.filename nei log,
verifica che il codice di inferenza venga effettivamente eseguito,
e testa con un upload reale. Usa Context7 per verificare come
FastAPI/Starlette gestisce UploadFile.content_type.
```

**File coinvolti**:
- `backend/api/knowledge_spaces.py` (linee 264-335)
- `backend/services/space_indexer.py`
- `backend/services/text_extractor.py`

---

### 1.2 Fix pipeline crash PostQA / await_human
**Plugin: Ralph Loop (`/ralph`)**
**Priorita: ALTA**

La pipeline crasha alla fine con:
```
AttributeError: 'NoneType' object has no attribute 'get'
File "src/graph/nodes/await_human.py", line 70, in _determine_reason
    if ro.get("dominant_scope") == "FULL":
```

E anche:
```
PostQA: FAILED (1 issues, 1 high severity)
Pipeline failed: 'NoneType' object has no attribute 'get'
```

**Azione**:
```
/ralph Debugga il crash della pipeline DRS in src/graph/nodes/await_human.py.
Il fix `or {}` alla linea 69 e' gia presente ma il crash arriva
dal nodo post_qa che chiama await_human con stato incompleto.
Traccia il flusso: post_qa_node → routing → await_human_node.
Leggi src/graph/graph.py per capire le condizioni di routing.
Assicurati che tutti i percorsi che portano ad await_human
abbiano reflector_output popolato, oppure gestisci il None.
```

**File coinvolti**:
- `src/graph/nodes/await_human.py`
- `src/graph/nodes/post_qa.py`
- `src/graph/graph.py` (routing conditions)

---

### 1.3 Fix provider non supportati
**Plugin: Context7 + Code Review**
**Priorita: ALTA**

Nei log della pipeline:
- `Unsupported provider: 'perplexity' (model='perplexity/sonar')` — JudgeF micro-search
- `Unsupported provider: 'qwen' (model='qwen/qwen3-7b')` — Context Compressor

**Azione**:
1. Usa **Context7** per verificare i modelli disponibili su OpenRouter
2. Sostituisci i modelli non supportati con alternative OpenRouter valide
3. `/code-review` su `src/llm/routing.py` e i file di configurazione modelli

**File coinvolti**:
- `src/llm/routing.py`
- `src/llm/client.py`
- `config/` o file YAML di configurazione modelli (cercare dove sono definiti i model assignments)

---

## FASE 2 — UI/UX improvements

### 2.1 Icone SVG reali
**Plugin: Frontend Design**
**Priorita: MEDIA**

Tutte le icone in `frontend/src/lib/icons.tsx` sono placeholder (cerchi SVG identici).
Servono icone reali da Lucide React o simili.

**Azione**: Sostituire ogni export in `icons.tsx` con SVG path reali per:
Plus, Folder, Trash2, Search, Upload, FileText, Download, Settings, User, Lock, Mail, LogOut, X, Shield, AlertCircle, CheckCircle, ChevronDown

**File**: `frontend/src/lib/icons.tsx`

---

### 2.2 Migliorare layout pagine dentro AppShell
**Plugin: Frontend Design**
**Priorita: MEDIA**

Le pagine (Dashboard, Spaces, NewResearch, Analytics, Settings) sono dentro AppShell
che ha sidebar, right panel e chat input. Verificare:
- Padding e overflow corretti
- Le pagine non vengono tagliate dalla sidebar o dal ChatInput (pb-20)
- Responsive su schermi piccoli
- Che la navigazione nella Topbar sia chiara e funzionale

**File**: Tutti i file in `frontend/src/pages/` e `frontend/src/components/layout/`

---

### 2.3 Pagina risultati / download ricerche
**Plugin: Frontend Design + Ralph Loop**
**Priorita: MEDIA**

Manca completamente la possibilita di vedere e scaricare i risultati delle ricerche completate.
Serve:
- Una vista dettaglio per ogni run completato (`/runs/:docId`)
- Preview del documento generato (Markdown rendered)
- Bottone download DOCX/MD
- Link nella tabella "Ricerche recenti" della Dashboard

**File da creare**: `frontend/src/pages/RunDetail.tsx`
**File da modificare**: `frontend/src/App.tsx` (aggiungere route), `backend/api/runs.py` (endpoint output)

---

## FASE 3 — Robustezza pipeline

### 3.1 Code Review completo pipeline
**Plugin: Code Review (`/code-review`)**
**Priorita: MEDIA**

```
/code-review Fai un audit completo dei nodi della pipeline in src/graph/nodes/.
Cerca: variabili non definite (come il bug state in post_draft_analyzer),
import mancanti, None non gestiti, edge case nei routing conditions.
Controlla anche src/graph/graph.py per la definizione del grafo.
```

---

### 3.2 Fix Writer Memory import
**Plugin: Ralph Loop**
**Priorita: BASSA**

```
WARNING: WriterMemory update failed: cannot import name 'update_writer_memory'
from 'src.graph.internals.writer_memory'
```

**File**: `src/graph/internals/writer_memory.py`, `src/graph/nodes/section_checkpoint.py`

---

### 3.3 Test end-to-end pipeline
**Plugin: Ralph Loop (`/ralph`)**
**Priorita: MEDIA**

Dopo aver fixato i bug sopra, eseguire una pipeline completa:
```
/ralph Esegui una pipeline DRS completa da CLI con:
python -m src.main --topic "Test: AI in healthcare" --preset Economy
Monitora i log, identifica e fixa ogni errore fino a completamento.
```

---

## FASE 4 — Companion & integrazione

### 4.1 Test flow Companion → Pipeline → UI
**Plugin: Ralph Loop**
**Priorita: ALTA (dopo fase 1)**

Testare il flusso completo dall'interfaccia:
1. Utente scrive nel ChatInput
2. Companion risponde e propone START_RUN
3. Pipeline parte, SSE events arrivano al frontend
4. PipelineCanvas mostra il grafo animato
5. HITL modal appare quando serve
6. Pipeline completa e risultato disponibile

---

### 4.2 Memorizzare contesto progetto
**Plugin: Claude Mem**
**Priorita: BASSA**

Salvare in memoria:
- Decisioni architetturali prese
- Bug risolti e pattern ricorrenti
- Preferenze dell'utente (lingua italiana, approccio diretto)
- Stato avanzamento del progetto

---

## Ordine di esecuzione consigliato

```
SESSIONE 1 (setup + bug critici):
  1. Claude Mem    → Carica contesto da HANDOVER.md
  2. /ralph        → 1.1 Fix upload file
  3. /ralph        → 1.2 Fix pipeline crash
  4. Context7      → 1.3 Trova modelli OpenRouter validi
  5. /code-review  → 1.3 Fix routing modelli

SESSIONE 2 (UI):
  6. Frontend Design → 2.1 Icone reali
  7. Frontend Design → 2.2 Layout fix
  8. Frontend Design + /ralph → 2.3 Pagina risultati

SESSIONE 3 (robustezza):
  9. /code-review   → 3.1 Audit pipeline
  10. /ralph         → 3.2 Fix writer memory
  11. /ralph         → 3.3 Test e2e pipeline

SESSIONE 4 (integrazione):
  12. /ralph         → 4.1 Test flow completo UI
  13. Claude Mem     → 4.2 Salva stato
```

---

## File chiave da conoscere

| Area | File | Descrizione |
|------|------|-------------|
| Entry point backend | `backend/main.py` | FastAPI app |
| API spaces | `backend/api/knowledge_spaces.py` | CRUD + upload + search |
| API runs | `backend/api/runs.py` | Pipeline runs CRUD + SSE |
| API companion | `backend/api/companion.py` | Chat AI |
| Pipeline graph | `src/graph/graph.py` | Definizione grafo LangGraph |
| Pipeline nodes | `src/graph/nodes/*.py` | 20+ nodi (writer, jury, reflector...) |
| LLM client | `src/llm/client.py` | Multi-provider (OpenRouter) |
| LLM routing | `src/llm/routing.py` | Model selection per preset |
| Frontend routes | `frontend/src/App.tsx` | Router React |
| State machine | `frontend/src/store/useAppStore.ts` | App state |
| Run state | `frontend/src/store/useRunStore.ts` | Pipeline state |
| SSE hook | `frontend/src/hooks/useSSE.ts` | Real-time events |
| Pipeline viz | `frontend/src/components/pipeline/PipelineCanvas.tsx` | Grafo interattivo |
| Layout | `frontend/src/components/layout/AppShell.tsx` | Root layout |
