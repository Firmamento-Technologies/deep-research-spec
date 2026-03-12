# Analisi Dettagliata delle Caratteristiche del Software — Deep Research System (DRS)

## 1. Panoramica Generale

Il **Deep Research System (DRS)** e' una pipeline multi-agente basata su intelligenza artificiale, progettata per generare documenti di ricerca long-form (da 500 a 50.000 parole), verificabili e di qualita' editoriale. Il sistema orchestra 41 nodi LangGraph che collaborano attraverso un ciclo iterativo di scrittura, valutazione e raffinamento, con checkpoint human-in-the-loop e un sistema di budget che garantisce il controllo dei costi.

---

## 2. Architettura a 4 Fasi

L'architettura e' organizzata in 4 fasi sequenziali, ciascuna con responsabilita' distinte:

### Fase A — Pre-Flight e Setup
- **Preflight**: validazione delle API key, disponibilita' dei modelli su OpenRouter, schema di configurazione Pydantic
- **Budget Estimator**: stima preventiva dei costi con formula `cost = sum(sections x avg_iter x sum(agent_tokens x price))`; blocca l'esecuzione se la proiezione supera l'80% del budget massimo
- **Planner**: genera l'outline del documento come `List[OutlineSection]` con titolo, scope, target words e dipendenze tra sezioni (modello: Gemini 2.5 Pro)
- **Await Outline**: checkpoint umano dove l'utente puo' riordinare, modificare o rimuovere sezioni prima di procedere

### Fase B — Loop per Sezione
Ciclo iterativo che si ripete per ogni sezione del documento:
1. **Ricerca** (Researcher + Citation Manager + Citation Verifier + Source Sanitizer + Source Synthesizer)
2. **Scrittura** (Writer, con possibile attivazione MoW — Mixture of Writers)
3. **Analisi post-draft** (Post Draft Analyzer per individuare gap informativi)
4. **Controllo stile** (Style Linter + Style Fixer)
5. **Valutazione Jury** (9 giudici paralleli: 3 Reasoning + 3 Factual + 3 Style)
6. **Aggregazione** (calcolo CSS e routing decisionale)
7. **Riflessione e correzione** (Reflector, Span Editor, Diff Merger)
8. **Controllo coerenza** (Coherence Guard tra sezioni)
9. **Compressione contesto** (Context Compressor per le sezioni successive)
10. **Checkpoint sezione** (salvataggio immutabile in PostgreSQL)

### Fase C — QA Post-Flight
- Rilevamento contraddizioni cross-sezione
- Validazione formato (word count entro +-10% del target)
- Verifica completezza (tutte le sezioni dell'outline presenti)
- Length Adjuster per correzioni dirette del conteggio parole

### Fase D — Pubblicazione
- Assemblaggio sezioni dal database
- Generazione formati multipli: DOCX, PDF, Markdown, LaTeX, HTML, JSON
- Generazione bibliografia
- Upload su S3/MinIO
- Raccolta feedback post-consegna

---

## 3. Sistema Jury a 9 Giudici

Il cuore del sistema di qualita' e' una giuria eterogenea composta da 3 mini-giurie indipendenti:

### Mini-Jury Reasoning (R) — 3 giudici
- **Modelli**: DeepSeek-R1, OpenAI o3-mini, Qwen QWQ-32B (decorrelazione epistemica)
- **Valuta**: flusso logico, validita' causale, coerenza inter-sezione, completezza argomentativa
- **Puo' emettere VETO** per: contraddizioni logiche

### Mini-Jury Factual (F) — 3 giudici
- **Modelli**: Perplexity Sonar, Gemini 2.5 Flash, Perplexity Sonar Pro
- **Valuta**: esistenza citazioni, fedelta' claim-fonte, accuratezza quantitativa, affidabilita' fonti
- **Puo' emettere VETO** per: fonti fabbricate, errori fattuali
- **Micro-Search**: capacita' di verifica esterna tramite ricerche web adversariali per falsificare claim ad alto rischio

### Mini-Jury Style (S) — 3 giudici
- **Modelli**: LLaMA 3.3 70B, Mistral Large, GPT-4.5
- **Valuta**: assenza pattern vietati, aderenza al registro stilistico, leggibilita', fedelta' all'exemplar
- **Non puo' emettere VETO** (nessuna autorita' di veto per questioni stilistiche)

### Consensus Strength Score (CSS)
Il punteggio di qualita' si articola in due gate sequenziali:
- **Content Gate**: `CSS_content = (pass_R/n_R x 0.44) + (pass_F/n_F x 0.56)` — i coefficienti sono derivati dinamicamente dai pesi della giuria
- **Style Pass**: `CSS_style = pass_S / n_S` — eseguito solo dopo il superamento del Content Gate

### Sistema a Cascata Economica
- **Tier 1**: modelli economici, sempre eseguiti per primi
- **Tier 2**: attivati solo in caso di disaccordo (~40%)
- **Tier 3**: modelli premium, usati in regime Premium
- Se tutti e 3 i giudici tier-1 concordano unanimemente, si risparmia il 60-70% del costo jury

---

## 4. Mixture of Writers (MoW)

Quando attivato (preset Balanced/Premium, sezione >= 400 parole, prima iterazione), il sistema genera 3 bozze parallele con approcci diversi:

| Writer | Ruolo | Temperatura | Focus |
|--------|-------|-------------|-------|
| W-A | Copertura | 0.30 | Completezza, struttura argomentativa |
| W-B | Argomentazione | 0.60 | Solidita' logica, gerarchia argomenti |
| W-C | Leggibilita' | 0.80 | Fluenza narrativa, varieta' sintattica |

Le 3 bozze vengono valutate da una giuria interna (27 chiamate LLM: 9 giudici x 3 bozze), poi il **Fusor** (modello o3) sintetizza la bozza migliore integrando i migliori elementi dalle altre. Costo: 3.5-4x la prima iterazione, ma con un risparmio netto di ~1.5 iterazioni successive.

---

## 5. Layer di Ricerca

Sistema multi-connettore per la raccolta di fonti verificate:

| Connettore | Tipo Fonte | Affidabilita' Base | Tecnologia |
|------------|-----------|-------------------|------------|
| Academic | Accademiche | 0.80-0.95 | CrossRef, Semantic Scholar, arXiv, DOAJ |
| Institutional | Istituzionali | 0.85-0.95 | Tavily con filtro domini (.gov, .eu, .un.org, ecc.) |
| Web General | Web generiche | 0.40-0.70 | Tavily + Brave Search |
| Social | Social media | 0.20-0.40 | Reddit API, Twitter Academic API |
| User Upload | Documenti utente | 1.00 | Elaborazione locale (sentence-transformers) |
| Scraper Fallback | Fallback | Variabile | BeautifulSoup + Playwright |

### Analisi Diversita' Fonti
Il sistema rileva automaticamente la concentrazione eccessiva per editore (>40%), autore (>30%) o anno (>50%), e attiva una ricerca diversificata supplementare.

### Ranking Fonti
Formula composita: `affidabilita' (40%) + rilevanza (35%) + recenza (15%) + qualita' abstract (10%)`, con deduplicazione (cosine similarity >= 0.90) e rilevamento fonti avversariali.

---

## 6. Controllo Budget Dinamico

### Tre Regimi di Qualita'

| Regime | Budget/Parola | Soglia CSS | Max Iterazioni | Giudici | MoW |
|--------|--------------|------------|----------------|---------|-----|
| Economy | < $0.002 | 0.65 | 2 | 1 su 3 | Disabilitato |
| Balanced | $0.002-$0.005 | 0.70 | 4 | 2 su 3 | Abilitato |
| Premium | > $0.005 | 0.78 | 8 | 3 su 3 | Abilitato |

### Strategie di Risparmio Dinamiche
- **70% budget speso**: downgrade modello Writer, jury_size -1
- **90% budget speso**: soglie CSS al minimo (Economy), max 1 iterazione, jury_size=1, MoW disabilitato
- **100% budget speso**: hard stop, salvataggio checkpoint, documento parziale
- **Anomalia sezione > $15**: pausa automatica, richiesta approvazione umana

### Tracker Real-Time
Ogni chiamata LLM viene tracciata con entry atomiche (PostgreSQL + Redis) contenenti: doc_id, section_idx, iteration, agent, model, tokens_in/out, cost_usd, latency_ms.

---

## 7. Sicurezza e Privacy

### Tre Modalita' di Privacy
- **Cloud**: PII anonimizzati prima dell'invio ai provider
- **Self-Hosted**: zero dati escono dall'infrastruttura (Ollama/vLLM)
- **Hybrid**: dati sensibili locali, giudici su cloud

### Pipeline PII a 3 Stadi
1. **Regex NER**: EMAIL, PHONE, SSN, IBAN, IP, DOB, ADDRESS, CARD
2. **Presidio**: PII strutturati con contesto
3. **SpaCy locale**: PERSON, ORG, LOCATION (mai inviato al cloud)

### Protezione Prompt Injection (3 stadi)
1. **Pre-LLM (Regex)**: rilevamento pattern di injection ("ignore previous instructions", "[SYSTEM]", ecc.)
2. **Isolamento strutturale**: wrapping XML + istruzioni nel system prompt
3. **Post-LLM (Output monitoring)**: rilevamento indicatori di jailbreak nell'output degli agenti

### GDPR Compliance
- Diritto alla cancellazione con certificato crittografico
- Retention differenziata (bozze: 30gg, documenti: 365gg, audit log: 10 anni)
- Minimizzazione dati: ogni agente riceve solo i campi necessari
- Invariante: i documenti caricati dall'utente non vengono MAI inviati ai provider cloud

### Autenticazione
- JWT/OAuth2 con token di accesso (24h) e refresh (7d)
- API key con scope (run/read/admin), rate limit e budget limit
- Rate limiting: 60 req/min per key, 10 req/min per IP non autenticato

---

## 8. Osservabilita'

### OpenTelemetry — Distributed Tracing
Ogni chiamata LLM e nodo agente emette uno span con attributi obbligatori: run_id, section_idx, iteration, agent, model, tokens, cost, latency, outcome.

### Prometheus — 17+ Metriche
Metriche chiave: runs totali/attivi, sezioni approvate/fallite, escalation, durata run/sezione, latenza agente, errori, costi, token, distribuzione CSS, violazioni stile, stato circuit breaker, tasso allucinazioni, panel discussion.

### Grafana — 4 Dashboard
1. **Operations Overview**: run attivi, tasso completamento, errori, coda, costi orari
2. **Quality Monitor**: distribuzione CSS, iterazioni medie, tasso escalation, allucinazioni
3. **Cost Tracker**: costi per agente, token per modello, utilizzo budget
4. **Infrastructure**: latenza API P50/P95/P99, circuit breaker, durata sezioni

### Sentry — Error Tracking
Eccezioni non gestite e output compromessi catturati con contesto completo (doc_id, run_id, section, agent, model, trace_id).

### Alerting (11 alert configurati)
Alert critici (PagerDuty): run failure rate >5%, circuit breaker aperto. Warning (Slack): anomalie di costo, backlog coda, drift qualita' CSS, tasso allucinazioni alto, latenza elevata.

### SLO
- Run completion rate: 99.0%
- API availability: 99.5%
- P95 latency < 200ms
- SSE delivery < 2s

---

## 9. Profili Stilistici

5 profili built-in con regole specifiche:

| Profilo | Caratteristiche |
|---------|----------------|
| Academic | Formale, citazioni, voce passiva, struttura IMRaD |
| Business | Executive summary, bullet points, ROI, raccomandazioni |
| Technical | Esempi codice, step-by-step, prerequisiti, specifiche |
| Journalistic | Piramide invertita, citazioni dirette, paragrafi brevi |
| Narrative | Storytelling, aneddoti, ritmo variato |

Ciascun profilo definisce pattern L1 (vietati), L2 (obbligatori) e L3 (guida soft). Il sistema include una **Style Calibration Gate** pre-Fase A per calibrare lo stile su un campione approvato dall'utente.

---

## 10. Meccanismi Anti-Oscillazione

### 3 Tipi di Oscillazione Rilevati
- **CSS**: punteggio oscilla tra iterazioni senza convergenza
- **Semantica**: embedding delle bozze troppo simili tra iterazioni (cosine similarity >= 0.85)
- **Whack-a-Mole**: correzione di un problema ne introduce un altro

### Routing Post-Oscillazione
- Oscillazione rilevata → escalation umana
- Nessuna oscillazione + scope SURGICAL → Span Editor (editing chirurgico)
- Nessuna oscillazione + scope PARTIAL → Writer (riscrittura parziale)
- Scope FULL → sempre escalation umana

---

## 11. Panel Discussion

Quando il CSS non raggiunge la soglia ma non c'e' consenso chiaro sulla direzione del miglioramento, viene attivata una **Panel Discussion**: i giudici discutono anonimamente per massimo 2 round per raggiungere un verdetto. Se dopo 2 round il CSS rimane sotto soglia, si procede con escalation umana.

---

## 12. Human-in-the-Loop

### 2 Checkpoint Programmati
1. **Outline Approval**: approvazione struttura del documento
2. **Escalation Intervention**: intervento su oscillazione o richiesta esplicita

### Interrupt di Emergenza (non programmati)
- Conflitto di coerenza HARD tra sezioni
- Anomalia costo singola sezione > $15
- CSS sotto soglia dopo 2 round di panel discussion
- Conflitto cross-sezione nel QA post-flight

---

## 13. Persistenza e Crash Recovery

- **PostgreSQL**: stato completo del documento, checkpoint per ogni sezione approvata, audit log append-only
- **Redis**: cache fonti (TTL 24h), pub/sub per SSE, contatori rate limit, sessioni
- **MinIO (S3)**: output finali (DOCX/PDF/ZIP), documenti caricati, backup
- **LangGraph Checkpointing**: `AsyncPostgresSaver` con `thread_id` per ripresa da qualsiasi punto

---

## 14. Stack Tecnologico

### Backend
- **Orchestrazione**: LangGraph 0.2+ (StateGraph, cicli condizionali, checkpointing)
- **API**: FastAPI 0.111+ (async-native, SSE, Pydantic v2)
- **Server**: Uvicorn 0.30+ (ASGI)
- **Coda**: Celery 5.4+ con Redis broker

### Frontend
- **MVP**: Streamlit 1.35+
- **Produzione**: Next.js 14+ (React Server Components, EventSource SSE)

### Database e Cache
- PostgreSQL 16 (JSONB, TDE AES-256)
- Redis 7 (cache, broker, pub/sub)
- MinIO (S3-compatible)

### LLM
- OpenRouter (API unificata, routing multi-provider)
- Ollama (modalita' self-hosted/air-gapped)

### NLP
- sentence-transformers (oscillazione semantica, cache)
- DeBERTa-v3-large (NLI entailment verification)
- Presidio + SpaCy (PII detection)
- textstat (readability metrics)

### Output
- python-docx (DOCX)
- WeasyPrint (PDF)
- Pandoc (LaTeX, HTML)

---

## 15. Deployment

### Ambienti
- **Dev**: Docker Compose con MockLLM, tutti i servizi in locale
- **Staging**: Kubernetes con modelli reali, budget cap $5/run, PII enforcement
- **Prod**: Kubernetes con autoscaling KEDA (min 1, max 20 worker), mTLS via Istio, backup PostgreSQL orari

### CI/CD (GitHub Actions)
1. `make lint` (ruff, mypy --strict)
2. `make test-unit` (deterministici, no LLM, <30s)
3. `make test-smoke` (mock LLM, <120s)
4. `make test-integration` (LLM reali, gated)
5. Deploy staging → approvazione manuale → rollout prod (10% → 50% → 100%)

---

## 16. Tipi di Documenti Supportati

| Tipo | Range Parole | Complessita' |
|------|-------------|-------------|
| Report scientifico | 5.000-50.000 | Molto alta |
| Report business | 3.000-20.000 | Alta |
| Documentazione tecnica | 2.000-30.000 | Alta |
| Giornalistico | 1.500-10.000 | Standard |
| Saggio narrativo | 2.000-15.000 | Standard |
| Istruzioni AI | 1.000-8.000 | Alta |
| Blog | 500-5.000 | Standard |

---

## 17. Formati di Output

- DOCX (con template, stili Heading, TOC automatico)
- PDF (WeasyPrint CSS-based, Pandoc fallback)
- Markdown
- LaTeX (con bibliografia BibTeX)
- HTML
- JSON (metadati strutturati)

Tutti gli output includono bibliografia formattata, vengono caricati su MinIO/S3 con URL pre-firmato (scadenza 15 minuti).

---

## 18. Resilienza

- **Circuit Breaker** per ogni coppia (slot, modello): CLOSED → OPEN → HALF-OPEN
- **Retry con backoff esponenziale** (tenacity): 2s → 4s → 8s, max 3 tentativi
- **Fallback chain** per ogni slot di giuria e agente
- **Rate limiting** per provider con semafori asincroni
- **Force Approve**: se una sezione raggiunge il massimo di iterazioni senza convergenza CSS, viene forzatamente approvata con log WARNING
- **Crash recovery**: ripresa da qualsiasi checkpoint grazie a LangGraph + PostgreSQL

---

## 19. KPI e Metriche di Qualita'

| Metrica | Target |
|---------|--------|
| Tasso approvazione primo tentativo MoW | > 55% |
| Delta MoW vs single writer | > +15% |
| Iterazioni risparmiate con MoW | < -0.8 |
| Tasso integrazione Fusor | > 60% |
| Break-even MoW soddisfatto | > 70% |
| Run completion rate | 99.0% |
| API availability | 99.5% |
| Tasso allucinazioni | < 5% |
