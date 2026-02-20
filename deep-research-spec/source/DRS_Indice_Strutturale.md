# DEEP RESEARCH SYSTEM — SPECIFICHE DI PROGETTO
## Indice Strutturale Completo

**Versione:** 2.0 — Post Stress Test Multi-Modello
**Data:** Febbraio 2026

---

## PARTE I — VISIONE E CONTESTO

### 1. Visione e Obiettivi
*Cosa conterrà: scopo del sistema, problema che risolve, superiorità rispetto a single-model LLM*

#### 1.1 Descrizione del Sistema
*Cosa conterrà: definizione sintetica del DRS, cosa produce, a chi è destinato*

#### 1.2 Casi d'Uso Target
*Cosa conterrà: tipologie di documenti (accademici, business, tecnici, investigativi), range lunghezza 5k–50k parole*

#### 1.3 Tipologie di Utente
*Cosa conterrà: tabella utenti (Ricercatore, Professionista, Sviluppatore, Enterprise) con casi d'uso principali*

#### 1.4 User Stories
*Cosa conterrà: storie utente principali in formato narrativo, inclusa generazione spec per coding agent*

#### 1.5 Vincoli di Input Utente
*Cosa conterrà: i due parametri obbligatori (max_budget_dollars, target_words), parametri opzionali derivati*

---

### 2. Principi di Design
*Cosa conterrà: i 10 principi architetturali confermati dallo stress test*

#### 2.1 Budget-First
*Cosa conterrà: vincolo economico inviolabile, derivazione automatica parametri da budget*

#### 2.2 Granularità Sezione-per-Sezione
*Cosa conterrà: loop isolato per sezione, immutabilità post-approvazione, eliminazione drift e regressioni*

#### 2.3 Diversità Epistemica
*Cosa conterrà: decorrelazione bias tramite famiglie architetturali diverse (Anthropic, OpenAI, Google, Mistral, Meta, DeepSeek)*

#### 2.4 Minority Veto a Due Livelli
*Cosa conterrà: protezione dalla maggioranza sbagliata, Rogue Judge Detector come contrappeso*

#### 2.5 Cascading Economico
*Cosa conterrà: modelli economici prima, premium riservati ai casi di disaccordo*

#### 2.6 Contesto Accumulato con Compressione Esplicita
*Cosa conterrà: ruolo del Context Compressor nella gestione della finestra di contesto*

#### 2.7 Human-in-the-Loop Selettivo
*Cosa conterrà: intervento umano solo in punti critici (outline, oscillazione), non nel loop ordinario*

#### 2.8 Observability by Design
*Cosa conterrà: logging strutturato, tracing, dashboard real-time come parte dell'architettura core*

#### 2.9 Resilienza Zero-Downtime
*Cosa conterrà: retry, circuit breaker, graceful degradation per ogni API call*

#### 2.10 Sicurezza e Privacy GDPR-Ready
*Cosa conterrà: sanitizzazione input, PII detection, privacy mode self-hosted*

#### 2.11 Testability First
*Cosa conterrà: ogni componente costruito con dipendenze iniettabili e mockabili; nessun agente chiama API esterne direttamente*

---

## PARTE II — INPUT E CONFIGURAZIONE

### 3. Input del Sistema
*Cosa conterrà: lista completa di tutti i campi configurabili, obbligatori e opzionali*

#### 3.1 Input Obbligatori
*Cosa conterrà: topic, max_budget_dollars, target_words — con tipi, vincoli e descrizioni*

#### 3.2 Input Opzionali — Documento
*Cosa conterrà: stile bibliografico (Harvard, APA, Chicago, Vancouver), lingua output, audience target*

#### 3.3 Input Opzionali — Stile Linguistico
*Cosa conterrà: profilo stile, registro, livello lettura (B2–C2), forbidden patterns personalizzabili*

#### 3.4 Input Opzionali — Fonti
*Cosa conterrà: tipologie abilitate per sezione, soglia reliability score, max fonti per sezione*

#### 3.5 Input Opzionali — Giuria
*Cosa conterrà: CSS threshold, finestra oscillation, hard limit iterazioni, modelli per slot giuria*

#### 3.6 Input Aggiuntivi per Profilo software_spec
*Cosa conterrà: product_goals, user_personas, tech_constraints, target_coding_agent, feature_list, NFR*

#### 3.7 Configurazione YAML
*Cosa conterrà: schema completo del file YAML dichiarativo (modelli, convergence, budget, error_handling)*

#### 3.8 Validazione Configurazione (Pydantic)
*Cosa conterrà: regole di validazione pre-esecuzione, warning e error specifici*

---

## PARTE III — ARCHITETTURA DEL SISTEMA

### 4. Flusso Macro
*Cosa conterrà: diagramma ASCII completo del flusso Fase A→B→C→D con tutti i branch condizionali*

#### 4.1 Fase A — Setup e Pre-Flight
*Cosa conterrà: preflight validator, budget estimator, planner, approvazione outline umana*

#### 4.2 Fase B — Loop per Sezione
*Cosa conterrà: ciclo Researcher→Citation→Writer→Jury→Aggregator→Reflector con tutti i routing*

#### 4.3 Fase C — Post-Flight QA
*Cosa conterrà: coherence guard cross-sezione, contradiction detector, format validator*

#### 4.4 Fase D — Publisher e Output
*Cosa conterrà: assemblaggio, formattazione, generazione multi-formato, feedback collector*

---

### 5. Agenti del Sistema
*Cosa conterrà: catalogo completo di tutti gli agenti con responsabilità, I/O, modelli assegnati*

#### 5.1 Planner
*Cosa conterrà: ruolo, input/output, modello (Gemini 2.5 Pro), generazione outline con budget parole per sezione*

#### 5.2 Researcher
*Cosa conterrà: ruolo, connettori fonte per tipologia, reliability score, modello (Sonar Pro + API dirette)*

#### 5.3 Citation Manager
*Cosa conterrà: costruzione mappa citazioni, formattazione per stile bibliografico, modulo deterministico*

#### 5.4 Citation Verifier
*Cosa conterrà: verifica HTTP HEAD + NLI entailment (DeBERTa), classificazione ghost/mismatch/valid*

#### 5.5 Source Sanitizer
*Cosa conterrà: estrazione abstract da fonti web, wrapping XML anti-injection, protezione prompt*

#### 5.6 Metrics Collector
*Cosa conterrà: analisi pre-giuria del draft (word count, citation density, plagiarism check)*

#### 5.7 Writer
*Cosa conterrà: ruolo, modello (Claude Opus 4.5), input (outline+fonti+reflector+memory), output testo*

#### 5.8 Writer Memory
*Cosa conterrà: accumulo errori ricorrenti, glossario tecnico, tendenza citazioni, feedback proattivo*

#### 5.9 Giurie (Reasoning / Factual / Style)
*Cosa conterrà: composizione 3×3, cascading economico tier1→tier2→tier3, prompt anti-sycophancy*

##### 5.9.1 Mini-Giuria R (Reasoning)
*Cosa conterrà: modelli per tier (qwq-32b → o3-mini → deepseek-r1), criteri valutazione logica*

##### 5.9.2 Mini-Giuria F (Factual)
*Cosa conterrà: modelli per tier (sonar → gemini-flash → sonar-pro), criteri verifica fattuale*

##### 5.9.3 Mini-Giuria S (Style)
*Cosa conterrà: modelli per tier (llama-3.3 → mistral-large → gpt-4.5), adattamento per lingua*

##### 5.9.4 Calibrazione e Normalizzazione Giudici
*Cosa conterrà: golden dataset, normalizzazione severità, confidence scoring (low/medium/high)*

#### 5.10 Aggregatore e CSS
*Cosa conterrà: formula CSS con pesi configurabili (R:0.35, F:0.45, S:0.20), routing post-verdetto*

#### 5.11 Minority Veto
*Cosa conterrà: Livello 1 (singolo giudice, veto_category), Livello 2 (mini-giuria unanime FAIL)*

##### 5.11.1 Rogue Judge Detector
*Cosa conterrà: soglia disagreement >70% su 3+ sezioni, alert, sostituzione temporanea*

#### 5.12 Panel Discussion
*Cosa conterrà: attivazione su CSS < θ_panel, meccanismo anonimizzato, max 2 tornate, escalazione*

#### 5.13 Reflector
*Cosa conterrà: modello (o3), feedback strutturato (severity/category/action), scope SURGICAL/PARTIAL/FULL*

#### 5.14 Oscillation Detector
*Cosa conterrà: tre tipi (CSS, semantico, whack-a-mole), early warning, escalazione umana*

#### 5.15 Context Compressor
*Cosa conterrà: modello (Qwen3-7B), strategia per livello (verbatim/sommario/estratto), claim load-bearing*

#### 5.16 Coherence Guard
*Cosa conterrà: confronto claim cross-sezione, livelli SOFT/HARD conflict, escalazione su contraddizioni*

#### 5.17 Publisher
*Cosa conterrà: formati output (DOCX, PDF, MD, HTML, LaTeX, JSON), section cache, assemblaggio finale*

#### 5.18 Feedback Collector
*Cosa conterrà: rating per sezione, highlight errori, style feedback, source blacklist, training loop*

---

### 6. Schema di Stato LangGraph
*Cosa conterrà: definizione completa del DocumentState TypedDict con tutti i campi*

#### 6.1 Stato Input e Configurazione
*Cosa conterrà: campi topic, config, budget nel state*

#### 6.2 Stato Outline e Sezioni
*Cosa conterrà: outline, current_section_idx, approved_sections, current_draft, current_iteration*

#### 6.3 Stato Giuria e Convergenza
*Cosa conterrà: jury_verdicts, css_history, reflector_notes, oscillation_detected, oscillation_type*

#### 6.4 Stato Budget
*Cosa conterrà: BudgetState nested (spent, remaining, projections, warnings)*

#### 6.5 Stato Escalazione e Human-in-the-Loop
*Cosa conterrà: human_intervention_required, coherence_conflict, rogue_judge_alerts*

#### 6.6 Stato Post-QA e Output
*Cosa conterrà: contradictions_found, format_validation_passed, final_document, output_paths, run_metrics*

---

### 7. Grafo LangGraph — Nodi e Transizioni
*Cosa conterrà: codice Python del grafo con tutti i nodi, edge, conditional_edges, routing functions*

#### 7.1 Definizione Nodi
*Cosa conterrà: registrazione di tutti i nodi nel StateGraph (preflight → publisher)*

#### 7.2 Transizioni Condizionali
*Cosa conterrà: route_outline_approval, route_after_aggregator, route_next_section, route_budget_check*

#### 7.3 Checkpoint e Persistenza
*Cosa conterrà: AsyncPostgresSaver, salvataggio thread_id, resume da crash*

---

## PARTE IV — SISTEMA DI VALUTAZIONE

### 8. Formula CSS (Consensus Strength Score)
*Cosa conterrà: formula matematica, pesi, range [0,1], semantica dei valori, derivazione soglie*

#### 8.1 Calcolo e Pesi
*Cosa conterrà: formula CSS = Σ w_k × (pass_k / n_k), pesi default R:0.35 F:0.45 S:0.20*

#### 8.2 Tabella Routing Post-CSS
*Cosa conterrà: condizioni (CSS≥θ, veto, panel, missing_evidence, budget esaurito) → azioni corrispondenti*

#### 8.3 Adattamento Dinamico del Threshold
*Cosa conterrà: come il Budget Controller modifica la soglia CSS in base al regime Economy/Balanced/Premium*

---

### 9. Meccanismi di Convergenza
*Cosa conterrà: cascata majority vote → panel discussion, stopping conditions*

#### 9.1 Cascading Economico nelle Mini-Giurie
*Cosa conterrà: logica tier1→tier2→tier3, condizioni di escalation, risparmio atteso 60-70%*

#### 9.2 Panel Discussion — Protocollo Completo
*Cosa conterrà: anonimizzazione, revisione voti, max tornate, ricalcolo CSS, archivio log PostgreSQL*

#### 9.3 Oscillation Detection — Tre Tipologie
*Cosa conterrà: CSS oscillation (varianza), semantic oscillation (cosine similarity), whack-a-mole*

#### 9.4 Early Warning e Escalation UI
*Cosa conterrà: alert preventivi, interfaccia modifica inline, override manuale, log motivazione*

---

## PARTE V — BUDGET CONTROLLER

### 10. Gestione Economica
*Cosa conterrà: architettura completa del modulo Budget Controller*

#### 10.1 Pre-Run Budget Estimator
*Cosa conterrà: formula di stima costo (sezioni × token × prezzi × iter_medio), blocco se oltre cap*

#### 10.2 Regime di Qualità Adattivo
*Cosa conterrà: tabella Economy/Balanced/Premium con soglie CSS, max iter, jury size, modelli*

#### 10.3 Real-Time Cost Tracker
*Cosa conterrà: contatore per agente/sezione/iterazione, allarmi WARN 70%, ALERT 90%, HARD STOP 100%*

#### 10.4 Strategie di Risparmio Dinamico
*Cosa conterrà: fallback cascade, early stopping economico, cache Redis, section cache, batching jury*

#### 10.5 Costo Target e Proiezioni
*Cosa conterrà: target $20–80/doc 10k parole, cost-per-word, esempio pratico con budget $50*

---

## PARTE VI — LAYER DI RICERCA FONTI

### 11. Connettori di Fonte
*Cosa conterrà: architettura del layer di ricerca, interfaccia uniforme, deduplicazione*

#### 11.1 Fonti Accademiche
*Cosa conterrà: CrossRef, Semantic Scholar, arXiv, DOAJ — API dirette senza LLM, reliability ≥0.80*

#### 11.2 Fonti Istituzionali
*Cosa conterrà: domini .gov, .eu, .un.org, WHO, OECD, Banca Mondiale — reliability ≥0.85*

#### 11.3 Fonti Web Generali
*Cosa conterrà: Tavily / Brave Search con filtri categoria, reliability 0.40–0.70*

#### 11.4 Fonti Social
*Cosa conterrà: Reddit API, Twitter/X Academic, reliability 0.20–0.40, uso per sentiment*

#### 11.5 Custom Source Connector
*Cosa conterrà: interfaccia per fonti proprietarie (SQL, Elasticsearch, vector DB), document upload PDF/DOCX*

#### 11.6 Reliability Score e Source Diversity Analyzer
*Cosa conterrà: calcolo score per tipo, verifica concentrazione su singolo publisher/autore/anno*

---

### 12. Gestione e Verifica Citazioni
*Cosa conterrà: pipeline completa dalla raccolta alla verifica*

#### 12.1 Citation Manager — Costruzione Mappa
*Cosa conterrà: formattazione per stile (Harvard, APA, Chicago, Vancouver), stringa inline e bibliografica*

#### 12.2 Citation Verifier — Verifica Automatica
*Cosa conterrà: HTTP HEAD check, NLI entailment con DeBERTa, classificazione ghost/mismatch/valid*

#### 12.3 Re-attivazione Researcher su missing_evidence
*Cosa conterrà: percorso condizionale nell'Aggregatore, query mirate, half-loop prima del Reflector*

#### 12.4 Hallucination Rate Tracker
*Cosa conterrà: tracking storico per modello del tasso di citazioni ghost, base per sostituzione giudici*

---

## PARTE VII — PROFILI DI STILE

### 13. Sistema di Profili Linguistici
*Cosa conterrà: architettura dei profili, regole per Writer e giuria S, forbidden patterns*

#### 13.1 Profilo: academic
*Cosa conterrà: tono neutro, coverage citazioni >85%, forbidden patterns specifici, struttura frasi*

#### 13.2 Profilo: business
*Cosa conterrà: tono diretto, coverage >60%, forbidden patterns corporate, voce attiva*

#### 13.3 Profilo: technical
*Cosa conterrà: precisione, definizioni alla prima occorrenza, coverage >70%, metriche obbligatorie*

#### 13.4 Profilo: blog
*Cosa conterrà: tono conversazionale, coverage >30%, hyperlink inline, forbidden patterns formali*

#### 13.5 Profilo: software_spec (Spec-Driven Development)
*Cosa conterrà: output multi-file, formati misti (prosa+YAML+Mermaid+Gherkin+SQL), forbidden patterns vaghi*

#### 13.6 Internazionalizzazione e Adattamento Linguistico
*Cosa conterrà: selezione modelli per lingua, cross-lingual citation, locale-aware forbidden patterns*

---

## PARTE VIII — PROFILI SOFTWARE: SPEC-DRIVEN DEVELOPMENT

### 14. Modalità Software Specification
*Cosa conterrà: architettura per generazione spec software in due/tre step*

#### 14.1 Rationale: DRS Genera la Spec, Non il Codice
*Cosa conterrà: motivazione (giuria valuta prosa non codice), spec come bottleneck reale*

#### 14.2 I Tre Livelli di Astrazione
*Cosa conterrà: COSA (functional), COME (technical), ESECUZIONE (software_spec) — dove DRS interviene*

#### 14.3 Step 1 — functional_spec
*Cosa conterrà: input (product_vision, personas, features, NFR), output (PRD, user stories, acceptance criteria)*

#### 14.4 Step 2 — technical_spec
*Cosa conterrà: input obbligatorio functional_spec, output (architecture.md, data_schema, api_spec, etc.)*

#### 14.5 Traceability Matrix tra Step
*Cosa conterrà: collegamento acceptance criteria → componenti architetturali, verifica Coherence Guard*

#### 14.6 Step 3 — software_spec (Output Multi-File)
*Cosa conterrà: struttura directory output (AGENTS.md, architecture.md, data_schema.sql, features/), formati*

#### 14.7 Pipeline Orchestrator per Step Sequenziali
*Cosa conterrà: modalità full_pipeline, checkpoint obbligatorio tra step, approvazione umana inter-step*

#### 14.8 Adattamento Giuria per Profili Software
*Cosa conterrà: Judge F verifica testabilità, Judge S diventa AI-Readability Judge, forbidden patterns*

---

## PARTE IX — RESILIENZA E FAULT TOLERANCE

### 15. Error Handling Matrix
*Cosa conterrà: matrice completa errore → retry → fallback → escalation*

#### 15.1 Errori API (429, 500, Timeout)
*Cosa conterrà: exponential backoff, circuit breaker (5 min), modello fallback, rate limit globale*

#### 15.2 Output Malformato
*Cosa conterrà: parsing Pydantic, retry con prompt semplificato, default a FAIL con parse_error*

#### 15.3 Citation Ghost e Missing Evidence
*Cosa conterrà: researcher retry query, skip claim, flag nel report*

#### 15.4 Context Overflow
*Cosa conterrà: compressor aggressivo, skip sezioni lontane, alert umano*

#### 15.5 Tecnologie di Resilienza
*Cosa conterrà: tenacity (retry), aiohttp-circuitbreaker, Redis cache, semafori rate limiting*

---

### 16. Persistenza e Checkpointing
*Cosa conterrà: strategia di recovery da crash per processi multi-ora*

#### 16.1 LangGraph + PostgreSQL
*Cosa conterrà: stato persistente (outline, sezioni approvate, jury history, CSS), thread_id salvato*

#### 16.2 Redis per Cache
*Cosa conterrà: cache fonti, retry state, riutilizzo valutazioni per query simili (cosine >0.90)*

#### 16.3 Resume Automatico da Checkpoint
*Cosa conterrà: ripresa da ultimo checkpoint dopo crash, nessuna rielaborazione sezioni approvate*

---

## PARTE X — SICUREZZA E PRIVACY

### 17. Security & Privacy Layer
*Cosa conterrà: architettura completa del layer di sicurezza*

#### 17.1 Source Sanitizer
*Cosa conterrà: estrazione abstract, wrapping XML anti-execution, protezione da prompt injection*

#### 17.2 PII Detection
*Cosa conterrà: presidio-analyzer prima di ogni LLM call, rimozione dati personali*

#### 17.3 Privacy Mode (Self-Hosted)
*Cosa conterrà: sostituzione modelli cloud con Ollama/VLLM locali, nessun dato fuori dalla macchina*

#### 17.4 GDPR Compliance
*Cosa conterrà: right-to-deletion, data export, data minimization, elenco dati per provider*

#### 17.5 Audit Log
*Cosa conterrà: tracciamento completo accessi, fonti consultate, modelli chiamati*

---

## PARTE XI — OBSERVABILITY

### 18. Stack di Monitoring
*Cosa conterrà: architettura completa dell'observability stack*

#### 18.1 OpenTelemetry — Tracing Distribuito
*Cosa conterrà: span per agente (latenza, token I/O, costo, modello), trace completo per documento*

#### 18.2 Prometheus + Grafana — Metriche
*Cosa conterrà: avg CSS/iterazioni, approval rate, cost/section, api_failures_per_provider*

#### 18.3 Sentry — Error Tracking
*Cosa conterrà: errori strutturati con doc_id, section_idx, agent, contesto*

#### 18.4 Progress Dashboard Real-Time
*Cosa conterrà: WebSocket via Redis pub/sub, sezione corrente, iterazione, CSS trend, costo, ETA*

#### 18.5 Logging Strutturato JSON
*Cosa conterrà: formato obbligatorio (doc_id, section_idx, iteration, agent, timestamp_iso)*

---

## PARTE XII — TESTING FRAMEWORK

### 19. Strategia di Test
*Cosa conterrà: framework completo per validazione del sistema*

#### 19.1 Golden Dataset
*Cosa conterrà: 20 documenti umani su topic diversi per calibrazione e benchmark*

#### 19.2 Metriche di Test
*Cosa conterrà: factual accuracy, style compliance (regex), inter-judge agreement (Cohen's kappa), citation validity*

#### 19.3 Mock LLM
*Cosa conterrà: intercettazione API, output predefiniti per test logica flusso, zero costi*

#### 19.4 Regression Testing
*Cosa conterrà: ogni modifica prompt → validazione automatica su golden dataset*

#### 19.5 Load Testing
*Cosa conterrà: target 1000 job/giorno, stress test API, benchmarking latenza*

#### 19.6 Dependency Injection Architecture
*Cosa conterrà: pattern di iniezione delle dipendenze per ogni agente — wrapper iniettabili che sostituiscono chiamate reali con mock in test*

#### 19.7 Smoke Suite per Fase MVP
*Cosa conterrà: suite eseguibile con singolo comando (make test-phaseN) che certifica il funzionamento di ogni fase prima di procedere alla successiva*

---

## PARTE XIII — ESCALAZIONI UMANE

### 20. Human-in-the-Loop — Protocollo Completo
*Cosa conterrà: tabella trigger → informazioni presentate → azioni disponibili*

#### 20.1 Approvazione Outline
*Cosa conterrà: proposta Planner, azioni (approva/modifica/rigenera)*

#### 20.2 Oscillazione Rilevata
*Cosa conterrà: tipo oscillazione, log draft, CSS history, modifica inline/override/abbandono*

#### 20.3 Reflector Scope FULL
*Cosa conterrà: motivazione, bozza corrente, riscrivi outline/approva/abbandona*

#### 20.4 Coherence Guard HARD Conflict
*Cosa conterrà: sezioni in conflitto, diff visuale, correggi/sblocca/accetta con warning*

#### 20.5 Budget >90% Speso
*Cosa conterrà: costo corrente, proiezione, sezioni rimanenti, continua/pubblica parziale/aumenta*

#### 20.6 Rogue Judge Rilevato
*Cosa conterrà: log voti anomali, sezioni coinvolte, disabilita/ignora*

---

## PARTE XIV — OUTPUT E PUBLISHER

### 21. Formati di Output
*Cosa conterrà: tutti i formati supportati con tecnologie e configurazione*

#### 21.1 DOCX
*Cosa conterrà: python-docx con template, stili formattati, sommario, bibliografia*

#### 21.2 PDF
*Cosa conterrà: generazione via pandoc, zero dipendenze LLM*

#### 21.3 Markdown
*Cosa conterrà: formato intermedio disponibile durante produzione*

#### 21.4 HTML
*Cosa conterrà: pubblicazione web con CSS responsive*

#### 21.5 LaTeX
*Cosa conterrà: submission accademica con gestione bibliography BibTeX*

#### 21.6 JSON Strutturato
*Cosa conterrà: {sections[], citations[], metadata, metrics} per consumo programmatico*

#### 21.7 Output Multi-File per software_spec
*Cosa conterrà: directory strutturata (AGENTS.md, architecture.md, data_schema.sql, features/), zip o git init*

---

### 22. Post-Flight QA
*Cosa conterrà: pipeline QA finale prima della pubblicazione*

#### 22.1 Consistency Check
*Cosa conterrà: terminologia coerente nell'intero documento*

#### 22.2 Format Validation
*Cosa conterrà: tutti i riferimenti formattati, nessuna citazione orfana*

#### 22.3 Completeness Check
*Cosa conterrà: tutte le sezioni dell'outline presenti*

#### 22.4 Contradiction Final Scan
*Cosa conterrà: scan cross-sezione ulteriore post-assemblaggio*

---

## PARTE XV — STACK TECNOLOGICO

### 23. Tabella Tecnologie
*Cosa conterrà: tabella completa layer → tecnologia → motivazione*

#### 23.1 Orchestrazione — LangGraph
*Cosa conterrà: cicli condizionali nativi, state persistente, checkpointing*

#### 23.2 LLM Routing — OpenRouter
*Cosa conterrà: accesso unificato, fallback automatico, model assignment statico da YAML*

#### 23.3 Backend — FastAPI + Uvicorn
*Cosa conterrà: API REST, WebSocket per progress*

#### 23.4 Frontend — Streamlit (MVP) → Next.js (Prod)
*Cosa conterrà: wizard configurazione, outline editor visuale, progress dashboard*

#### 23.5 Job Queue — Celery + Redis
*Cosa conterrà: gestione documenti lunghi in background, pub/sub per WebSocket*

#### 23.6 Persistenza — PostgreSQL + Redis + S3/MinIO
*Cosa conterrà: stato e log (PG), cache (Redis), documenti finali (S3)*

#### 23.7 Containerizzazione — Docker Compose / Kubernetes
*Cosa conterrà: dev locale, staging, produzione con autoscaling*

#### 23.8 CI/CD — GitHub Actions
*Cosa conterrà: test automatici su PR, deploy su merge main*

---

### 24. Modelli LLM Assegnati agli Agenti
*Cosa conterrà: tabella completa agente → modello primario → fallback 1 → fallback 2 → giustificazione*

#### 24.1 Rationale Scelta Modelli
*Cosa conterrà: principio task-fit, non classifica benchmark, capacità specifiche per ruolo*

#### 24.2 Tabella Assegnazione Completa
*Cosa conterrà: tutti gli agenti con modelli primari e fallback chain per ogni slot*

#### 24.3 Configurazione Privacy Mode
*Cosa conterrà: sostituzione modelli cloud con Llama 3.3 70B, Mistral, Qwen via Ollama*

#### 24.4 Sostituibilità e Aggiornamento
*Cosa conterrà: cambio modello = modifica una riga YAML, nessun impatto sul codice*

---

## PARTE XVI — PROMPT LAYER

### 25. Architettura dei Prompt
*Cosa conterrà: struttura system/context/task per ogni agente, separazione responsabilità*

#### 25.1 Struttura a Tre Livelli
*Cosa conterrà: System prompt (identità), Context prompt (stato), Task prompt (istruzione specifica)*

#### 25.2 Anti-Sycophancy nei Giudici
*Cosa conterrà: istruzione esplicita nel system prompt per resistere al bias di conferma*

#### 25.3 Forbidden Patterns per Profilo
*Cosa conterrà: liste complete dei pattern vietati per ogni profilo (academic, business, technical, blog, software_spec)*

---

## PARTE XVII — INTERFACCIA UTENTE

### 26. Web UI
*Cosa conterrà: componenti dell'interfaccia utente*

#### 26.1 Wizard di Configurazione
*Cosa conterrà: form step-by-step per topic, stile, fonti, budget*

#### 26.2 Style Profile Presets
*Cosa conterrà: template predefiniti con live preview esempio output*

#### 26.3 Outline Editor Visuale
*Cosa conterrà: drag-and-drop sezioni, inline editing titoli/scopo*

#### 26.4 Progress Dashboard
*Cosa conterrà: real-time updates (% completamento, sezione, iterazioni, CSS trend, costo)*

#### 26.5 Interfaccia Escalation
*Cosa conterrà: modifica inline sezione, riscrittura outline, override manuale, diff visuale*

---

## PARTE XVIII — FUNZIONALITÀ AVANZATE

### 27. Versioning e Collaboration
*Cosa conterrà: gestione versioni, multi-utente, rigenerazione sezioni*

#### 27.1 Document Versioning
*Cosa conterrà: sezioni immutabili ma versionate, rollback, fork*

#### 27.2 Section Regeneration
*Cosa conterrà: sblocco sezione approvata, rigenerazione con istruzioni aggiuntive*

#### 27.3 Multi-User Mode
*Cosa conterrà: permessi (owner/editor/reviewer), commenti inline, change tracking*

---

### 28. Multi-Document Mode
*Cosa conterrà: supporto "document series" per progetti di ricerca grandi*

#### 28.1 Glossario Condiviso
*Cosa conterrà: terminologia consistente tra documenti della stessa serie*

#### 28.2 Citation Reuse
*Cosa conterrà: fonti già verificate riutilizzate senza rielaborazione*

#### 28.3 Cross-Referencing
*Cosa conterrà: un documento può citare un altro della serie*

---

### 29. Feedback Loop e Apprendimento
*Cosa conterrà: ciclo di miglioramento continuo del sistema*

#### 29.1 Feedback Collector Post-Produzione
*Cosa conterrà: rating per sezione, errori marcati, style feedback, source blacklist*

#### 29.2 Training Loop
*Cosa conterrà: miglioramento prompt e configurazioni nel tempo basato su feedback*

---

## PARTE XIX — DEPLOYMENT E INFRASTRUTTURA

### 30. Ambienti
*Cosa conterrà: configurazione dev, staging, produzione*

#### 30.1 Dev — Docker Compose Locale
*Cosa conterrà: Mock LLM attivo, PostgreSQL locale, zero costi API*

#### 30.2 Staging — Kubernetes
*Cosa conterrà: modelli reali a budget ridotto, dati anonimizzati*

#### 30.3 Produzione — Kubernetes con Autoscaling
*Cosa conterrà: full stack, backup PostgreSQL ogni ora, rate limiting*

#### 30.4 Rate Limiting verso Provider
*Cosa conterrà: OpenRouter 60 req/min, CrossRef 50 req/s, Tavily rispetto Retry-After*

#### 30.5 Scalabilità
*Cosa conterrà: agenti come microservizi, Celery fino a 1000 job/giorno, hierarchical summarization >50k parole*

---

## PARTE XX — KPI E METRICHE DI SUCCESSO

### 31. Definizione del Successo
*Cosa conterrà: tutte le metriche target quantitative*

#### 31.1 Metriche di Qualità del Documento
*Cosa conterrà: human acceptance rate >90%, citation accuracy >98%, style compliance 100%, error density <1/1000 parole*

#### 31.2 Metriche di Efficienza Economica
*Cosa conterrà: cost per document $20–50, cost per word <$0.004, first-time approval rate >60%, avg iterations <2.5*

#### 31.3 Metriche di Affidabilità
*Cosa conterrà: uptime >99.5%, recovery rate 100%, API failure recovery >95%*

#### 31.4 Metriche di Convergenza
*Cosa conterrà: oscillation rate <5%, panel discussion rate <15%, budget overrun rate 0%*

---

## PARTE XXI — ROADMAP MVP (4 FASI)

### 32. Piano di Implementazione
*Cosa conterrà: roadmap incrementale dalle fondamenta alla produzione*

#### 32.1 Fase 1 — MVP Core (4 settimane)
*Cosa conterrà: 1 Writer + 1 Judge F + 1 Judge S, fonti web, Markdown, max 1 iter, budget cap fisso*

#### 32.2 Fase 2 — Multi-Judge (4 settimane)
*Cosa conterrà: giurie 3×3, minority veto, CSS completo, Reflector, Panel, Oscillation, checkpointing PG*

#### 32.3 Fase 3 — Advanced Features (6 settimane)
*Cosa conterrà: Planner, Researcher completo, Citation Verifier NLI, Context Compressor, DOCX+PDF+MD, Privacy Mode*

#### 32.4 Fase 4 — Production (8 settimane)
*Cosa conterrà: Web UI, Celery queue, OpenTelemetry+Prometheus+Grafana, security audit, load test, plugin system*

---

## PARTE XXII — REGOLE OPERATIVE

### 33. Regole per l'AI Developer
*Cosa conterrà: istruzioni operative non negoziabili per chi costruisce il sistema*

#### 33.1 Pre-Flight Check Obbligatorio
*Cosa conterrà: verifica API key, modelli su OpenRouter, connettori fonti prima di ogni run*

#### 33.2 Parsing con Pydantic
*Cosa conterrà: mai json.loads diretto, retry con prompt semplificato, default FAIL su parse_error*

#### 33.3 Parallelismo Asincrono
*Cosa conterrà: mini-giurie in asyncio.gather, solo Reflector sequenziale*

#### 33.4 WebSocket e Progress
*Cosa conterrà: worker Celery pubblica su Redis pub/sub, WebSocket endpoint inoltra al client*

#### 33.5 Logging JSON Strutturato
*Cosa conterrà: campi obbligatori (doc_id, section_idx, iteration, agent, timestamp_iso), mai plaintext*

#### 33.6 Dependency Injection Obbligatoria
*Cosa conterrà: mai chiamate API esterne dirette nel codice agenti — sempre attraverso wrapper iniettabili configurati all'inizializzazione*

---

*Fine indice — Deep Research System v2.0*
*Basato su stress test multi-modello (febbraio 2026) con 5 analisi critiche indipendenti*
