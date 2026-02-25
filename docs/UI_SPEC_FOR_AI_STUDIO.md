# DRS — UI & Dashboard Specification for AI Studio

> Questo documento contiene TUTTE le informazioni necessarie per costruire
> la dashboard Grafana e la Web UI completa del Deep Research System (DRS).

---

## 1. Cos'è DRS

DRS è un sistema multi-agente AI che genera documenti di ricerca di alta qualità
(1.000–50.000 parole). Riceve in input un topic, un target di parole e un budget
in dollari; produce in output un documento DOCX/PDF/Markdown con fonti verificate.

Tecnologie: Python 3.12, LangGraph (grafo stateful), OpenRouter (API LLM),
Prometheus (metrics), Grafana (dashboard), FastAPI (backend API), PostgreSQL
(storage sezioni), Redis (code async).

---

## 2. Pipeline: Fasi e Agenti

```
FASE A — Setup
  preflight → budget_estimator → planner → await_outline

FASE B — Loop Sezioni (si ripete per ogni sezione N volte)
  researcher → citation_manager → citation_verifier →
  source_sanitizer → source_synthesizer →
    [MoW: writer_a / writer_b / writer_c → jury_multidraft → fusor]
    [Standard: writer_single]
  → post_draft_analyzer → [researcher_targeted →...]
  → style_linter → style_fixer → metrics_collector →
  → budget_controller → jury → aggregator →
    [approved]   → context_compressor → coherence_guard → section_checkpoint
    [fail_style] → style_fixer → style_linter → jury
    [fail_reflector / veto] → reflector →
        [SURGICAL] → span_editor → diff_merger → style_linter
        [PARTIAL]  → writer_single
        [FULL]     → await_human
    [panel]      → panel_discussion → aggregator
    [fail_missing_ev] → researcher_targeted
    [budget_hard_stop] → publisher
  section_checkpoint → [next_section] → researcher
                     → [all_done]    → post_qa

FASE C — Post-QA
  post_qa → [ok] → publisher
          → [length_out_of_range] → length_adjuster → publisher
          → [conflicts] → await_human

FASE D — Output
  publisher → END
  feed_back_collector (async post-delivery)
```

---

## 3. Metriche Prometheus disponibili

Endpoint: `http://localhost:9090/metrics`

| Metric name | Tipo | Label | Descrizione |
|---|---|---|---|
| `drs_llm_calls_total` | Counter | `agent`, `model`, `preset` | Totale chiamate LLM |
| `drs_llm_cost_dollars_total` | Counter | `agent`, `model` | Costo cumulativo USD |
| `drs_llm_latency_seconds` | Histogram | `agent` | Latenza chiamate LLM (bucket: 0.5,1,2,5,10,20,30,60,120s) |
| `drs_tokens_in_total` | Counter | `model` | Token input totali |
| `drs_tokens_out_total` | Counter | `model` | Token output totali |
| `drs_sections_completed_total` | Counter | — | Sezioni approvate dalla jury |
| `drs_iterations_total` | Counter | — | Iterazioni write-judge-reflect totali |
| `drs_jury_css_score` | Gauge | `dimension` (`content`,`style`,`source`) | CSS score attuale |
| `drs_budget_spent_dollars` | Gauge | `doc_id` | Budget speso in USD |
| `drs_budget_remaining_pct` | Gauge | `doc_id` | % budget rimanente |
| `drs_pipeline_duration_seconds` | Histogram | — | Durata pipeline completa (bucket: 30,60,120,300,600,1200,1800,3600s) |
| `drs_jury_pass_rate` | Gauge | `preset` | Tasso approvazione jury (0.0–1.0) |

---

## 4. Grafana Dashboard — Specifiche Dettagliate

### Data Source
- Nome: `Prometheus`
- URL: `http://localhost:9090` (o `http://host.docker.internal:9090` se in Docker)
- Auto-refresh: ogni **5 secondi**
- Time range default: **ultimi 15 minuti**

### Layout (12 colonne, 8 righe)

```
ROW 1: [Budget Gauge (6col)] [Budget Timeline (6col)]
ROW 2: [Sezioni Approvate (3col)] [Iterazioni Totali (3col)] [Jury Pass Rate (3col)] [Pipeline Duration (3col)]
ROW 3: [CSS Scores (12col)]
ROW 4: [LLM Calls per Agent (6col)] [Costo per Agent (6col)]
ROW 5: [Latenza LLM p50/p90/p99 (12col)]
ROW 6: [Token In/Out per Model (6col)] [Style Violations (6col)]
```

### Pannello 1 — Budget Usage Gauge
- **Tipo**: Gauge
- **Query**: `100 - drs_budget_remaining_pct{doc_id=~"$doc_id"}`
- **Titolo**: Budget Consumato
- **Unità**: percent (0–100)
- **Soglie colore**:
  - 0–70%: verde `#73BF69`
  - 70–90%: giallo `#F2CC0C`
  - 90–100%: rosso `#F2495C`
- **Min**: 0, **Max**: 100
- **Threshold labels**: visibili

### Pannello 2 — Budget Timeline
- **Tipo**: Time series
- **Query A**: `drs_budget_spent_dollars{doc_id=~"$doc_id"}` → legend `Speso ($)`
- **Query B**: `drs_budget_spent_dollars{doc_id=~"$doc_id"} / (1 - drs_budget_remaining_pct{doc_id=~"$doc_id"}/100)` → legend `Max Budget ($)`
- **Unità asse Y**: `currencyUSD`
- **Fill opacity**: 20%
- **Line width**: 2

### Pannello 3 — Sezioni Approvate
- **Tipo**: Stat
- **Query**: `drs_sections_completed_total`
- **Titolo**: Sezioni Approvate
- **Color mode**: background
- **Soglie**: 0=red, 1=yellow, 3=green
- **Graph mode**: area

### Pannello 4 — Iterazioni Totali
- **Tipo**: Stat
- **Query**: `drs_iterations_total`
- **Titolo**: Iterazioni Totali
- **Color mode**: value
- **No threshold** (informativo)

### Pannello 5 — Jury Pass Rate
- **Tipo**: Gauge
- **Query**: `drs_jury_pass_rate{preset=~"$preset"}`
- **Titolo**: Jury Pass Rate
- **Unità**: percentunit (0.0–1.0)
- **Soglie**: 0=red, 0.5=yellow, 0.75=green

### Pannello 6 — Pipeline Duration
- **Tipo**: Stat
- **Query**: `rate(drs_pipeline_duration_seconds_sum[5m]) / rate(drs_pipeline_duration_seconds_count[5m])`
- **Titolo**: Durata Media Pipeline
- **Unità**: `s` (secondi)
- **Soglie**: 0=green, 300=yellow, 600=red

### Pannello 7 — CSS Scores Realtime
- **Tipo**: Time series
- **Query A**: `drs_jury_css_score{dimension="content"}` → `CSS Content`
- **Query B**: `drs_jury_css_score{dimension="style"}` → `CSS Style`
- **Query C**: `drs_jury_css_score{dimension="source"}` → `CSS Source`
- **Asse Y**: min=0, max=1
- **Soglie orizzontali**: linea rossa a 0.65 (content threshold), linea arancione a 0.80 (style threshold)
- **Annotazioni**: mostrare quando CSS supera le soglie

### Pannello 8 — LLM Calls per Agent
- **Tipo**: Bar chart
- **Query**: `rate(drs_llm_calls_total[5m])` by agent
- **Legend**: `{{agent}}`
- **Titolo**: Chiamate LLM per Agente (5m rate)
- **Orientation**: horizontal

### Pannello 9 — Costo per Agent
- **Tipo**: Bar chart
- **Query**: `increase(drs_llm_cost_dollars_total[5m])` by agent
- **Legend**: `{{agent}} - {{model}}`
- **Unità**: `currencyUSD`
- **Titolo**: Costo per Agente (5m)

### Pannello 10 — Latenza LLM Percentili
- **Tipo**: Time series
- **Query A**: `histogram_quantile(0.50, rate(drs_llm_latency_seconds_bucket[5m]))` → `p50`
- **Query B**: `histogram_quantile(0.90, rate(drs_llm_latency_seconds_bucket[5m]))` → `p90`
- **Query C**: `histogram_quantile(0.99, rate(drs_llm_latency_seconds_bucket[5m]))` → `p99`
- **Unità**: `s`
- **Fill opacity**: 10%

### Pannello 11 — Token Usage
- **Tipo**: Time series
- **Query A**: `rate(drs_tokens_in_total[5m])` by model → `Input {{model}}`
- **Query B**: `rate(drs_tokens_out_total[5m])` by model → `Output {{model}}`
- **Titolo**: Token per Minuto per Modello

### Pannello 12 — Style Violations (derivato da metriche custom)
- **Tipo**: Stat
- **Query**: `drs_iterations_total - drs_sections_completed_total`
- **Titolo**: Iterazioni Senza Approvazione
- **Soglie**: 0=green, 3=yellow, 6=red

### Template Variables
```
$doc_id: query=label_values(drs_budget_spent_dollars, doc_id), refresh=5s
$preset: custom=Economy|Balanced|Premium, default=All
$agent:  query=label_values(drs_llm_calls_total, agent), refresh=1m
```

---

## 5. Web UI — Specifiche Complete

### Stack tecnologico consigliato
- **Frontend**: React 18 + TypeScript + Tailwind CSS
- **Realtime**: SSE (Server-Sent Events) da FastAPI
- **Charts**: Recharts o Tremor
- **State**: Zustand o React Query

### Palette colori
```
Background:     #0F1117  (dark navy)
Surface:        #1A1D27  (dark card)
Surface2:       #242736  (slightly lighter)
Border:         #2E3144
Text primary:   #E8E9F0
Text secondary: #8B8FA8
Accent blue:    #4F6EF7
Green:          #22C55E
Yellow:         #EAB308
Red:            #EF4444
Orange:         #F97316
Purple:         #A855F7
```

### Pagine dell'app

#### A. Dashboard principale (`/`)
Vista overview di tutti i run in corso e completati.

**Header**:
- Logo DRS + nome sistema
- Bottone `+ Nuovo Documento`
- Badge con stato sistema (online/offline)

**Run Cards Grid** (max 3 colonne):
Per ogni run in corso:
```
┌────────────────────────────────────┐
│ [Preset badge] [Status badge]       │
│ "AI Safety Alignment Techniques"    │
│ Target: 1.000 parole               │
│ ━━━━━━━━━━━━━━━━━━━━━━ 62%         │
│ Sezione 2/5 — Writer               │
│ Budget: $0.23 / $50.00 (0.5%)      │
│ ⏱ 4m 32s          [Dettaglio →]    │
└────────────────────────────────────┘
```

#### B. Nuovo Documento (`/new`)
Form wizard in 3 step:

**Step 1 — Contenuto**:
- `Topic` (textarea, required, max 500 chars, placeholder: "Descrivi l'argomento...")
- `Target parole` (slider: 1.000–50.000, step 500)
- `Tipo documento` (select: Survey / Tutorial / Review / Report / Spec / Essay / Blog)

**Step 2 — Qualità e Stile**:
- `Quality Preset` (3 card selezionabili):
  - Economy: 💚 Veloce, economico, 1 giudice, no MoW
  - Balanced: 💛 Standard, 2 giudici, MoW per sezioni >400w
  - Premium: 🔴 Massima qualità, 3 giudici, MoW sempre attivo
- `Profilo stile` (dropdown): Academic / Business Report / Technical Documentation / Journalistic / Narrative Essay / Blog / Software Spec
- `Exemplar` (textarea opzionale): incolla un paragrafo di esempio per clonare lo stile

**Step 3 — Budget e Config**:
- `Budget massimo` (slider: $5–$500, default $50)
- `Stima costo` (calcolata live): mostra range $X–$Y
- `HITL` toggle: Approvazione umana outline e sezioni
- `Formati output` (multi-checkbox): DOCX / PDF / Markdown / LaTeX / HTML / JSON
- `Citation style` (select): APA / Harvard / Chicago / Vancouver
- Bottone `Avvia Pipeline`

#### C. Run Detail (`/run/:doc_id`)
**Layout a 3 colonne**:
- Colonna sinistra (25%): Pipeline Status
- Colonna centrale (50%): Live Preview
- Colonna destra (25%): Metrics

**Colonna sinistra — Pipeline Status**:
Vertical stepper con fasi:
```
✅ FASE A — Setup
   ✅ Preflight
   ✅ Budget Estimator
   ✅ Planner (4 sezioni)
   ✅ Outline Approvato

🔄 FASE B — Sezione 2/4
   ✅ Researcher (12 fonti)
   ✅ Citation Manager
   ✅ Citation Verifier
   ✅ Source Sanitizer
   ✅ Source Synthesizer
   🔄 Writer (iteration 2)
   ⏳ Style Linter
   ⏳ Jury
   ⏳ Aggregator

⏳ FASE C — Post-QA
⏳ FASE D — Publisher
```

Every node ha:
- Icona stato: ✅ ok / 🔄 running / ⏳ waiting / ❌ failed / ⚠️ escalated
- Timestamp di completamento
- Click per espandere dettagli (payload JSON)

**Colonna centrale — Live Preview**:
- Tab `Outline` (Phase A): lista sezioni con titolo, scope, target_words, dipendenze
- Tab `Draft Corrente`: testo del draft section in corso (aggiornato via SSE)
- Tab `Sezioni Approvate`: accordion delle sezioni approvate con CSS score badge
- Tab `Output Finale` (Phase D): preview DOCX/Markdown con bottone download

**Colonna destra — Metrics in realtime**:
```
Budget
████████░░░░░░ 23% ($0.23/$1.00)

CSS Scores
 Content  ████████░░ 0.82 ✅
 Style    ████████░░ 0.85 ✅
 Source   ███████░░░ 0.71

Jury Verdicts (ultima iterazione)
 R1 ✅ medium  R2 ✅ high  R3 ✅ low
 F1 ✅ high    F2 ❌ high  F3 ✅ medium
 S1 ✅ medium  S2 ✅ high  S3 ✅ medium

Iterazioni sezione corrente: 2/4
LLM calls: 47
Costo sessione: $0.23
Latenza ultima call: 3.2s
```

#### D. HITL Review (`/run/:doc_id/review`)
Mostra quando `human_intervention_required = true`.

**Outline Review** (Phase A, se `auto_approve_outline = false`):
- Lista sezioni drag-and-drop riordinabili
- Per ogni sezione: edit titolo, scope, target_words
- Aggiungi/rimuovi sezioni
- Bottone `Approva Outline` / `Rigenera`

**Section Review** (Phase B, per HITL checkpoint):
- Mostra draft completo con highlighting delle violazioni
- Panel dei feedback Reflector con severity badge
- CSS scores con breakdown per dimensione
- Lista fonti usate con reliability score
- Bottoni: `Approva`, `Rigenera`, `Richiedi Modifica Manuale`

**Escalation Review** (oscillation / coherence conflict):
- Banner rosso con tipo escalation
- Dettaglio del conflitto (es. sezione A vs sezione B claim contraddittorio)
- Opzioni: `Risolvi Automatico`, `Modifica Manuale`, `Salta Sezione`

#### E. Analytics (`/analytics`)
Dashboard storico di tutti i run completati.

**Filtri**: date range, preset, topic keyword

**KPI Cards**:
- Run totali completati
- Costo medio per documento
- Parole generate totali
- CSS medio composito
- Tasso successo prima iterazione

**Grafici**:
- Line chart: CSS score nel tempo per documento
- Bar chart: costo per preset
- Scatter: CSS vs costo per run
- Heatmap: iterazioni per sezione

#### F. Settings (`/settings`)
- API Keys (OpenRouter)
- Model assignments per agente
- Default config (preset, budget, stile)
- Connectors attivi (Perplexity Sonar, Tavily, Brave, ecc.)
- Webhook notifications

---

## 6. SSE Events (realtime dal backend)

Endpoint: `GET /api/runs/:doc_id/events`

```json
// Cambio stato nodo
{"event": "NODE_STARTED",   "data": {"node": "writer", "ts": "2026-02-25T00:22:00Z"}}
{"event": "NODE_COMPLETED", "data": {"node": "jury",   "ts": "2026-02-25T00:22:05Z", "duration_s": 4.2}}
{"event": "NODE_FAILED",    "data": {"node": "researcher", "error": "connector_down"}}

// Sezione approvata
{"event": "SECTION_APPROVED", "data": {
  "section_idx": 2,
  "css_final": 0.81,
  "iterations_used": 2,
  "approved_at": "2026-02-25T00:22:10Z"
}}

// CSS update
{"event": "CSS_UPDATE", "data": {
  "content": 0.82,
  "style": 0.85,
  "composite": 0.83
}}

// Budget update
{"event": "BUDGET_UPDATE", "data": {
  "spent": 0.23,
  "max": 50.0,
  "remaining_pct": 99.5
}}

// HITL richiesto
{"event": "HUMAN_REQUIRED", "data": {
  "type": "outline_approval",
  "options": ["approve", "edit", "regenerate"]
}}

// Oscillazione rilevata
{"event": "OSCILLATION_DETECTED", "data": {
  "type": "CSS",
  "section_idx": 3,
  "css_history": [0.72, 0.68, 0.71, 0.69]
}}

// Draft aggiornato (streaming testo)
{"event": "DRAFT_CHUNK", "data": {"text": "...next tokens..."}}

// Pipeline completata
{"event": "PIPELINE_DONE", "data": {
  "output_paths": {"markdown": "s3://...", "docx": "s3://..."},
  "total_words": 1023,
  "total_cost": 0.41,
  "duration_s": 287
}}
```

---

## 7. API REST (FastAPI)

```
POST /api/runs
  Body: {topic, target_words, quality_preset, style_profile, max_budget, output_formats}
  → {doc_id, status: "initializing"}

GET  /api/runs
  → [{doc_id, topic, status, progress_pct, cost_spent, created_at}]

GET  /api/runs/:doc_id
  → DocumentState (full)

GET  /api/runs/:doc_id/events
  → SSE stream

POST /api/runs/:doc_id/approve-outline
  Body: {sections: [OutlineSection]}
  → {accepted: true}

POST /api/runs/:doc_id/approve-section
  Body: {section_idx, action: "approve"|"regenerate"|"edit", edit_content?}
  → {accepted: true}

POST /api/runs/:doc_id/resolve-escalation
  Body: {action: "auto"|"manual"|"skip", resolution?}
  → {accepted: true}

GET  /api/runs/:doc_id/output/:format
  → file download (docx|pdf|markdown|json)

DELETE /api/runs/:doc_id
  → {cancelled: true}

GET  /api/metrics
  → {llm_calls, total_cost, sections_approved, avg_css}
```

---

## 8. Quality Preset — Parametri

| Parametro | Economy | Balanced | Premium |
|---|---|---|---|
| Jury size | 1 (R1,F1,S1) | 2 (R1-2,F1-2,S1-2) | 3 (R1-3,F1-3,S1-3) |
| MoW abilitato | ❌ Mai | ✅ Se >400w, iter=1 | ✅ Sempre |
| CSS Content threshold | 0.65 | 0.70 | 0.78 |
| CSS Style threshold | 0.80 | 0.80 | 0.80 |
| Max iterazioni/sezione | 2 | 4 | 8 |
| Panel Discussion | ❌ | ✅ | ✅ |
| PostDraftAnalyzer | ❌ | ✅ | ✅ |
| Costo stimato 5k parole | ~$1–3 | ~$5–15 | ~$20–60 |

---

## 9. Status Stati del DocumentState

| Status | Colore UI | Descrizione |
|---|---|---|
| `initializing` | 🔵 blu | Setup in corso |
| `running` | 🟢 verde pulsante | Pipeline attiva |
| `paused` | 🟡 giallo | In attesa (non usato attualmente) |
| `awaiting_approval` | 🟠 arancione | HITL: attesa input umano |
| `completed` | ✅ verde | Documento generato |
| `failed` | ❌ rosso | Errore fatale |
| `cancelled` | ⚪ grigio | Annullato dall'utente |

---

## 10. CSS Score — Logica di Routing

```
css_content ≥ threshold AND css_style ≥ 0.80  →  APPROVED
css_content OK  AND css_style < 0.80           →  FAIL_STYLE → StyleFixer
css_content < threshold (≥ 0.50)              →  FAIL_REFLECTOR → Reflector
css_content < 0.50                            →  PANEL_REQUIRED → PanelDiscussion
Any judge VETO                                →  VETO → Reflector
Judge F: missing_evidence not empty           →  FAIL_MISSING_EV → ResearcherTargeted
budget.spent ≥ budget.max                     →  BUDGET_HARD_STOP → Publisher (partial)
force_approve = True (max iter reached)       →  FORCE_APPROVE → CoherenceGuard (warning log)
```

---

## 11. Agenti — Modelli LLM Assegnati

| Agente | Modello primario | Fallback |
|---|---|---|
| Planner | `google/gemini-2.5-pro` | gemini-2.5-flash |
| Researcher | `perplexity/sonar-pro` | Tavily → Brave → Scraper |
| SourceSynthesizer | `anthropic/claude-sonnet-4` | claude-haiku-3 |
| Writer (single) | `anthropic/claude-opus-4-5` | claude-sonnet-4 |
| Writer A (Coverage) | `anthropic/claude-opus-4-5` | — |
| Writer B (Argument) | `anthropic/claude-opus-4-5` | temp=0.8 |
| Writer C (Readability)| `anthropic/claude-opus-4-5` | temp=0.6 |
| StyleFixer | `anthropic/claude-sonnet-4` | claude-haiku-3 |
| SpanEditor | `anthropic/claude-sonnet-4` | Writer |
| Reflector | `openai/o3` | o3-mini |
| Fusor | `openai/o3` | o3-mini → claude-opus |
| PostDraftAnalyzer | `google/gemini-2.5-flash` | llama-3.3-70b |
| CoherenceGuard | `google/gemini-2.5-flash` | gemini-1.5-flash |
| ContextCompressor | `qwen/qwen3-7b` | llama-3.3-70b |
| Jury R (Reasoning) | `openai/o3` (R1) | o3-mini (R2,R3) |
| Jury F (Factual) | `google/gemini-2.5-pro` (F1) | gemini-2.5-flash |
| Jury S (Style) | `anthropic/claude-sonnet-4` (S1) | claude-haiku-3 |

---

## 12. Struttura Cartelle Progetto (riferimento)

```
src/
  graph/
    graph.py          # LangGraph graph definition
    state.py          # DocumentState TypedDict
    nodes/
      preflight.py
      planner.py
      researcher.py
      writer.py
      style_linter.py
      style_fixer.py
      jury.py
      aggregator.py
      reflector.py
      ...
  llm/
    client.py         # LLMClient (OpenRouter)
    routing.py        # route_model() function
  observability/
    metrics.py        # Prometheus metrics
  config/
    schema.py         # DRSYAMLConfig Pydantic
  main.py             # CLI entrypoint
config/
  drs.yaml            # Config file
  grafana_dashboard.json
docs/
  UI_SPEC_FOR_AI_STUDIO.md  # Questo file
```

---

## 13. Note Implementative per AI Studio

1. **SSE è la fonte primaria di verità** per lo stato UI — non fare polling REST.
2. **Grafana**: importare il JSON da `config/grafana_dashboard.json`, configurare Prometheus come data source.
3. **CSS thresholds variano per preset** — Economy: 0.65, Balanced: 0.70, Premium: 0.78. Mostrare sempre il threshold corretto nel gauge.
4. **HITL flow**: quando arriva `HUMAN_REQUIRED` via SSE, mostrare un modal bloccante che richiede azione prima di procedere.
5. **Budget hard stop**: quando `budget.hard_stop_fired = true`, mostrare un banner permanente arancione nella run detail page.
6. **Oscillation detected**: quando `oscillation_detected = true`, mostrare nel pipeline stepper un badge `⚠️ OSCILLAZIONE` sul nodo corrente con il tipo (CSS/SEMANTIC/WHACK_A_MOLE).
7. **Force approve**: quando `force_approve = true`, mostrare un badge `⚡ FORCE APPROVED` sulla sezione con tooltip "Iterazioni massime raggiunte".
8. **Veto judge**: nella jury verdict card, se `veto_category` è presente, mostrare il giudice in rosso con il tipo di veto.
