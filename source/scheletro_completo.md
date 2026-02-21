# DEEP RESEARCH SYSTEM — SPECIFICHE DI PROGETTO
## Indice Strutturale Completo v3.0

---

### 1. Visione e Obiettivi
*Cosa conterrà: scopo del sistema, superiorità rispetto al single-model writing, risultato atteso*

#### 1.1 Descrizione del Sistema
*Cosa conterrà: definizione sintetica — agente AI multi-modello per documenti di ricerca verificabili*

#### 1.2 Casi d'Uso Target
*Cosa conterrà: tipologie di documenti (accademici, business, tecnici, investigativi), range 5k–50k parole*

#### 1.3 Tipologie di Utente
*Cosa conterrà: ricercatore, professionista, sviluppatore, enterprise — con user stories*

#### 1.4 Vincoli Fondamentali
*Cosa conterrà: i due soli parametri obbligatori (max_budget_dollars, target_words) e derivazione automatica*

---

### 2. Principi di Design
*Cosa conterrà: gli 11 principi architetturali che governano ogni decisione implementativa*

#### 2.1 Budget-First
*Cosa conterrà: vincolo economico inviolabile, sistema non spende mai oltre max_budget_dollars*

#### 2.2 Granularità Sezione-per-Sezione
*Cosa conterrà: loop isolato per sezione, immutabilità post-approvazione, eliminazione della deriva stilistica*

#### 2.3 Diversità Epistemica della Giuria
*Cosa conterrà: famiglie architetturali diverse (Anthropic, OpenAI, Google, Mistral, Meta, DeepSeek)*

#### 2.4 Minority Veto a Due Livelli
*Cosa conterrà: protezione dalla maggioranza sbagliata, Rogue Judge Detector per prevenire abusi*

#### 2.5 Cascading Economico
*Cosa conterrà: modelli economici prima, premium solo su disaccordo — riduzione costi 60-70%*

#### 2.6 Contesto Accumulato con Compressione Esplicita
*Cosa conterrà: Context Compressor dedicato per gestire finestra di contesto su documenti lunghi*

#### 2.7 Human-in-the-Loop Selettivo
*Cosa conterrà: intervento utente solo in punti critici (outline approval, escalation oscillazione)*

#### 2.8 Observability by Design
*Cosa conterrà: logging strutturato, tracing distribuito e dashboard come parte dell'architettura*

#### 2.9 Resilienza Zero-Downtime
*Cosa conterrà: retry policy, circuit breaker, graceful degradation per ogni API call*

#### 2.10 Sicurezza e Privacy GDPR-Ready
*Cosa conterrà: sanitizzazione input, PII detection, privacy mode self-hosted*

#### 2.11 Testability First
*Cosa conterrà: ogni componente progettato per test in isolamento — nessun agente chiama API esterne direttamente, tutto passa per wrapper iniettabili sostituibili con mock a costo zero; smoke suite obbligatoria per ogni fase MVP prima di procedere alla successiva*

#### 2.12 Token Economy by Design
Cosa conterrà: ogni componente del sistema ha responsabilità esplicita di minimizzare
i token consumati senza perdita informativa. Non è una ottimizzazione post-hoc, è un
vincolo di progettazione primario al pari del budget monetario. Tre livelli:
(1) Input compression: Source Synthesizer obbligatorio prima di ogni Writer call,
Context Compressor obbligatorio dopo ogni sezione approvata, sorgenti deduplicati
prima di entrare nel contesto. 
(2) Output compression: formato machine-readable tipizzato preferito a prosa per qualsiasi output letto da altri agenti (non da umani),
cross-reference §N.M invece di ripetere definizioni. 
(3) Routing economico: cascading giurie tier1→tier2→tier3, modelli leggeri per task estrattivi/deterministici, modelli
premium solo per generazione e ragionamento complesso. Metrica: token/valore-prodotto
tracciata nel Run Report per agente e per sezione.

---

### 3. Input del Sistema
*Cosa conterrà: specifica completa di tutti gli input utente con vincoli e valori di default*

#### 3.1 Input Obbligatori
*Cosa conterrà: topic, target_words, style_profile, output_language, max_budget_dollars — tipi e range*

#### 3.2 Input Opzionali
*Cosa conterrà: output_formats, custom_outline, uploaded_sources, blacklist/whitelist, privacy_mode, quality_preset*

#### 3.3 Parametri Avanzati (YAML)
*Cosa conterrà: override di soglie CSS, max iterazioni, jury weights, modelli specifici per slot*

---

### 3B. Fase -1 — Style Calibration Gate
*Cosa conterrà: fase opzionale eseguita una sola volta prima della Fase A — produce lo Style Exemplar iniettato nel prompt Writer per tutto il documento*

#### 3B.1 Campione di Stile
*Cosa conterrà: Writer produce paragrafo campione di 250 parole sul topic reale; solo mini-giuria S lo valuta; interfaccia approvazione utente con opzioni (approva / feedback libero / rigenera); max 3 tentativi, poi il sistema suggerisce cambio preset*

#### 3B.2 Style Exemplar
*Cosa conterrà: campione approvato salvato nello State, iniettato nel context prompt del Writer ad ogni sezione come riferimento concreto di tono e ritmo — non template da copiare, riferimento di registro e struttura sintattica*

#### 3B.3 Ruleset Congelato
*Cosa conterrà: profilo di stile + regole L1/L2/L3 congelati al momento dell'approvazione, immutabili per tutto il run — unica eccezione: aggiunta di nuove regole FORBIDDEN per sezioni future (non rimozione di quelle attive)*

#### 3B.4 Integrazione con Preset
*Cosa conterrà: utente sceglie preset → sistema mostra regole in linguaggio naturale → utente può modificare → Writer produce campione → ciclo approvazione; ruleset congelato impedisce drift stilistico tra sezioni*

---

### 4. Architettura del Sistema
*Cosa conterrà: flusso macro del sistema dalle fasi A→D, diagramma completo del grafo*

#### 4.1 Fase A — Pre-Flight e Setup
*Cosa conterrà: Pre-Flight Validator, Budget Estimator, Planner, outline approval umano*

#### 4.2 Fase B — Loop per Sezione
Cosa conterrà: sequenza completa per ogni sezione: Researcher→Citation Manager→Citation Verifier→Source Sanitizer→Source Synthesizer→Writer→MoW→Post-Draft Analyzer→Style Linter→Content Gate(RF)→Style Pass(S)→Style Fixer→Coherence Guard→approvazione

#### 4.3 Fase C — Post-Flight QA
*Cosa conterrà: Coherence Guard, Contradiction Detector, Format Validator sul documento assemblato*

#### 4.4 Fase D — Publisher e Output
*Cosa conterrà: assemblaggio sezioni, formattazione, generazione output multi-formato, Feedback Collector*

#### 4.5 Diagramma del Grafo LangGraph
*Cosa conterrà: definizione completa dei nodi, edge condizionali, routing post-aggregatore con tutti i branch (PASS, FAIL→Reflector, SURGICAL→SpanEditor, Panel, Veto, budget_stop)*

#### 4.6 Schema di Stato (DocumentState TypedDict)
*Cosa conterrà: tutti i campi dello State condiviso — input, outline, sezioni, giuria, budget, escalazione, output, style_exemplar, writer_memory*

---

### 5. Agenti del Sistema — Livello Produzione
*Cosa conterrà: catalogo completo di tutti gli agenti con responsabilità singola, input/output, modello, casi di errore*

#### 5.1 Planner
*Cosa conterrà: ruolo, input/output, modello (gemini-2.5-pro), formato outline JSON, document type detection, regole budget parole per sezione*

#### 5.2 Researcher
*Cosa conterrà: ruolo, connettori di fonte, deduplicazione, SourceRanker, fallback scraping, max fonti/sezione, modalità targeted per Post-Draft Analyzer*

#### 5.3 Citation Manager
*Cosa conterrà: costruzione mappa citazioni, formattazione per stile bibliografico (Harvard, APA, Chicago, Vancouver), modulo deterministico*

#### 5.4 Citation Verifier
*Cosa conterrà: HTTP 200 check, DOI resolver, NLI entailment check (DeBERTa), temporal/quantitative consistency, ghost citation detector*

#### 5.5 Source Sanitizer
*Cosa conterrà: estrazione contenuto rilevante, wrapping XML anti-injection, prompt injection guard con tre stadi difesa*

#### 5.6 Source Synthesizer
Cosa conterrà: ruolo compressione semantica fonti verificate pre-Writer, modello claude-sonnet-4-5, input corpus fonti da Source Sanitizer, output corpus compresso ≥60% con claim deduplicati e confirmed_by multipli, graceful degradation su errore, disabilitato se fonti ≤2

#### 5.7 Writer
*Cosa conterrà: ruolo, modello (claude-opus-4-5), system prompt con style_profile, forbidden patterns, Style Exemplar iniettato, WriterMemory, angoli MoW per profilo*

#### 5.8 Metrics Collector
*Cosa conterrà: metriche deterministiche pre-giuria — Flesch-Kincaid, citation coverage ratio, source diversity score, plagiarism check*

#### 5.9 Style Linter
*Cosa conterrà: componente non-LLM deterministico — verifica L1 (regex forbidden) e L2 (elementi required) PRIMA della giuria; se violazioni L1/L2 → testo torna al Style Fixer con lista esatta delle violazioni (posizione, tipo, messaggio, fix_hint); tre categorie: pattern lessicali, pattern strutturali, AI fingerprint patterns*

#### 5.10 Style Fixer
*Cosa conterrà: agente dedicato alla correzione stilistica del draft content-approved — modello claude-sonnet-4; riceve draft + lista violazioni dal Style Linter + Style Exemplar; produce SOLO correzioni di forma senza toccare fatti/numeri/citazioni/struttura argomentativa; vincolo esplicito nel prompt: se correggere richiedesse alterare contenuto → segnalare e lasciare invariato; max 2 iterazioni per sezione*

#### 5.11 Post-Draft Research Analyzer
*Cosa conterrà: agente proattivo (gemini-2.5-flash) che analizza il draft PRIMA della giuria per identificare gap informativi — tre categorie: evidenza mancante, sub-topic emergente, approfondimento forward-looking; se gap trovati (max 3) → ri-attiva Researcher in modalità targeted → Span Editor integra nuove fonti; evita iterazioni sprecate per mancanza di evidenze; attivato solo alla prima iterazione*

#### 5.12 Span Editor
*Cosa conterrà: agente per revisioni con scope SURGICAL — riceve dal Reflector lista span esatti da modificare (citazione testuale precisa + istruzione); interviene solo su quelli preservando tutto il resto; risparmio token ~60-70% vs riscrittura completa; se correggere uno span richiedesse modificare un fatto → segnala come "non correggibile senza alterare contenuto"; disabilitato su iterazione 3+ (rischio degradazione cumulativa)*

#### 5.13 Fusor
*Cosa conterrà: agente di sintesi MoW — modello o3; riceve 3 draft + CSS per draft + best elements identificati dalla giuria; usa come base il draft con CSS più alto; integra genuinamente best elements degli altri due; non aggiunge claim non presenti in nessun draft; gira una sola volta per sezione nella prima iterazione*

#### 5.14 Reflector
*Cosa conterrà: ruolo, modello (o3), feedback strutturato con severity/category/affected_text/action/priority; scope SURGICAL (→ Span Editor), PARTIAL (→ Writer), FULL (→ escalazione umana obbligatoria)*

#### 5.15 Oscillation Detector
*Cosa conterrà: tre tipologie, soglie, early warning, escalazione umana con interfaccia interattiva*

#### 5.16 Context Compressor
*Cosa conterrà: modello qwen3-7b, strategia verbatim/sommario/estratto per posizione, claim load-bearing, invocato dopo ogni approvazione*

#### 5.17 Coherence Guard
*Cosa conterrà: confronto claim fattuali cross-sezione, livelli SOFT (log) e HARD (escalazione umana)*

#### 5.18 Writer Memory
*Cosa conterrà: accumulo errori ricorrenti, glossario tecnico, style drift tracking, tendenza citazioni, feedback proattivo iniettato nel context prompt*

#### 5.19 Publisher
*Cosa conterrà: assemblaggio sezioni, template DOCX, sommario automatico, bibliografia, output multi-formato*

#### 5.20 Feedback Collector
*Cosa conterrà: rating per sezione, highlight errori, blacklist fonti, training loop per miglioramento prompt*

---

### 6. Run Companion
*Cosa conterrà: agente conversazionale sempre attivo durante il run — finestra intelligente sul processo con capacità di modifica*

#### 6.1 Cos'è e Cosa Non È
*Cosa conterrà: NON orchestratore, NON agente del loop di produzione — osservatore con accesso in lettura a tutto lo stato + capacità di eseguire modifiche sicure; riduce token del 29.68% (SupervisorAgent arXiv 2025) anticipando inefficienze prima che si propaghino*

#### 6.2 Accesso allo Stato
*Cosa conterrà: tabella completa dati accessibili — outline, sezioni approvate, sezione in produzione, CSS history, verdetti giuria con motivazioni, feedback Reflector, log errori, budget per agente/sezione, configurazione attiva, Run Report parziale; NON ha accesso a: prompt interni agenti, dati altri run*

#### 6.3 Quattro Tipologie di Risposta
*Cosa conterrà: Tipo 1 domande di stato (perché N iterazioni, CSS breakdown, costo attuale), Tipo 2 domande predittive e di consiglio (opzioni A/B con trade-off espliciti), Tipo 3 richieste di modifica (dirette vs alto impatto con conferma), Tipo 4 notifiche proattive senza che l'utente chieda*

#### 6.4 Modifiche Dirette vs Alto Impatto
*Cosa conterrà: dirette senza conferma — aggiungere forbidden pattern, alzare/abbassare CSS threshold ±0.10, aggiungere uploaded_source, nota Run Report, source_blacklist; con conferma esplicita — quality_preset, scope sezione, sblocco sezione approvata, jury weights, max_iterations, interruzione run*

#### 6.5 Notifiche Proattive
*Cosa conterrà: tabella trigger → messaggio — CSS sezione <0.70 dopo approvazione, budget >60% a metà documento, stessa fonte >3 sezioni consecutive, Judge F trova contraddizione esterna, drift di stile tra sezioni, oscillazione imminente (early warning prima del blocco)*

#### 6.6 Modello e Persistenza
*Cosa conterrà: google/gemini-2.5-pro (context window ampio, risposta <3s), fallback claude-sonnet-4; conversazione salvata nel Run Report come audit trail conversazionale con timestamp e riferimento iterazione/sezione per ogni modifica applicata*

---

### 7. Mixture-of-Writers e Fusor
*Cosa conterrà: architettura MoW basata su paper MoA/FusioN, condizioni di attivazione, impatto budget*

#### 7.1 Condizioni di Attivazione
*Cosa conterrà: solo prima iterazione di ogni sezione; disabilitato in Economy / sezioni <400 parole / post-escalazione umana con istruzioni specifiche*

#### 7.2 I Tre Writer Proposer (W-A, W-B, W-C)
*Cosa conterrà: stesso modello claude-opus-4-5, temperature diverse (0.30/0.60/0.80), angoli diversi — Coverage (completezza), Argumentation (solidità logica), Readability (fluidità narrativa)*

#### 7.3 Angoli per Profilo di Stile
*Cosa conterrà: tabella angoli specifici per profilo (academic, business, technical, blog, software_spec, journalistic, narrative_essay)*

#### 7.4 Fusor Agent
*Cosa conterrà: modello o3, selezione draft base per CSS (tie-break a Judge F), integrazione best elements, regola conservativa (non aggiunge claim assenti in tutti e tre i draft), gira una sola volta*

#### 7.5 Valutazione Multi-Draft della Giuria
*Cosa conterrà: prima valutazione parallela sui 3 draft con best elements per draft non-vincitore; selezione draft base per Fusor; seconda valutazione ufficiale sul draft fuso; solo il CSS del draft fuso entra nella css_history*

#### 7.6 Impatto sul Budget
*Cosa conterrà: costo prima iterazione 3.5-4× baseline; break-even a 1.5 iterazioni risparmiate; A/B test implicito tracking mow_enabled=true/false; tabella quality_preset → strategia → iterazioni attese*

---

### 8. Sistema di Valutazione — Giuria
*Cosa conterrà: panoramica delle 3 mini-giurie, formula CSS, separazione Content Gate / Style Pass*

#### 8.1 Mini-Giuria Reasoning (R)
*Cosa conterrà: 3 giudici (deepseek-r1, o3-mini, qwq-32b), valutazione solidità logica, coerenza inter-sezione, causalità*

#### 8.2 Mini-Giuria Factual (F)
*Cosa conterrà: 3 giudici (sonar, gemini-flash, gpt-4o-search), claim supportati, ghost citation, mismatch fonte/testo*

##### 8.2.1 Micro-Search del Judge F (Agent-as-a-Judge)
*Cosa conterrà: tool di ricerca web (Tavily, fallback Brave) per FALSIFICARE i claim ad alto posta — query progettate per trovare contraddizioni non conferme; trigger: statistica specifica, relazione causale non banale, reliability fonte <0.75, confidence low; max 3 claim e 2 query/claim; throttling per quality_preset (disabilitato Economy, parziale Balanced, completo Premium); campo external_sources_consulted nel verdetto; costo target <8% run totale*

#### 8.3 Mini-Giuria Style (S)
*Cosa conterrà: 3 giudici (gpt-4.5, mistral-large, llama-3.3), forbidden patterns, registro, readability, conformità allo Style Exemplar*

#### 8.4 Calibrazione e Normalizzazione Giudici
*Cosa conterrà: golden dataset calibrazione (20 documenti con CSS ground truth umano); normalizzazione severità per giudici sistematicamente severi/generosi (z-score su history run); confidence scoring obbligatorio nel verdetto (low/medium/high) — confidence low attiva micro-search nel Judge F; disagreement analysis: log sistematico disaccordi per identificare pattern di conflitto legittimi vs bug di prompt*

#### 8.5 Cascading Economico delle Mini-Giurie
*Cosa conterrà: tier1 prima → se unanimità stop; se disaccordo → tier2 → tier3; parallelo asincrono tra le tre mini-giurie; risparmio atteso 60-70%*

#### 8.6 Formato Verdetto dei Giudici
*Cosa conterrà: struttura JSON con dimension_scores, pass_fail, veto_category, confidence, comments, external_sources_consulted (Judge F), failed_claims, missing_evidence*

---

### 9. Aggregatore e Formula CSS
*Cosa conterrà: logica completa dell'Aggregatore, due fasi di approvazione sequenziali, formula CSS separata per contenuto e stile*

#### 9.1 Calcolo del Consensus Strength Score (CSS)
*Cosa conterrà: formula CSS_content = 0.44×(pass_R/n_R) + 0.56×(pass_F/n_F); CSS_style = pass_S/n_S; CSS_finale = media ponderata per il Run Report; range 0-1, semantica dei valori*

#### 9.2 Pesi delle Mini-Giurie
*Cosa conterrà: weights configurabili (reasoning 0.35, factual 0.45, style 0.20 nel CSS finale); motivazione pesi; vincolo somma = 1.0*

#### 9.3 Separazione Content Gate e Style Pass
*Cosa conterrà: fase 1 Content Gate — solo R+F, soglia CSS_content ≥ 0.65; fase 2 Style Pass — solo S, soglia CSS_style ≥ 0.80 (più alta: tolleranza zero); se Content Gate passa ma Style Pass fallisce → Style Fixer, NON il Writer; due numeri distinti nel Run Report*

#### 9.4 Routing Post-Aggregatore
*Cosa conterrà: tabella condizioni/azioni — PASS completo, FAIL Content→Reflector, FAIL Style→Style Fixer, SURGICAL→Span Editor, Panel, Veto, missing_evidence→Researcher, budget_stop*

---

### 10. Minority Veto
*Cosa conterrà: specifica completa dei due livelli di veto e del Rogue Judge Detector*

#### 10.1 Livello 1 — Veto Individuale
*Cosa conterrà: veto_category valide (fabricated_source, factual_error, logical_contradiction, plagiarism); singolo giudice blocca indipendentemente dal CSS*

#### 10.2 Livello 2 — Veto Unanime di Mini-Giuria
*Cosa conterrà: se 0/3 PASS in una mini-giuria → sezione bloccata indipendentemente dal CSS globale*

#### 10.3 Rogue Judge Detector
*Cosa conterrà: rilevamento disagreement rate >70% su 3+ sezioni consecutive; notifica utente tramite Run Companion; sostituzione temporanea con modello fallback; log per analisi post-run*

---

### 11. Panel Discussion
*Cosa conterrà: meccanismo completo di discussione tra giudici in caso di forte disaccordo*

#### 11.1 Condizione di Attivazione
*Cosa conterrà: CSS_content < css_panel_threshold (default 0.50) dopo iterazione ordinaria*

#### 11.2 Meccanismo di Discussione
*Cosa conterrà: anonimizzazione commenti, scambio motivazioni tra giudici, revisione voto, max 2 tornate, archivio log in PostgreSQL*

#### 11.3 Esito Post-Panel
*Cosa conterrà: CSS ≥ threshold → approvazione; ancora < threshold → escalation umana*

---

### 12. Reflector
*Cosa conterrà: ruolo, input/output, modello (o3), formato feedback strutturato*

#### 12.1 Formato del Feedback
*Cosa conterrà: severity (CRITICAL/HIGH/MEDIUM/LOW), category, affected_text (citazione esatta), action, priority; regola conflitto: severity più alta prevale, a parità prevale Judge Factual*

#### 12.2 Scope del Rewrite
*Cosa conterrà: SURGICAL (→ Span Editor, 1-2 span isolati), PARTIAL (→ Writer, molti span interdipendenti), FULL (→ escalazione umana obbligatoria, struttura argomentativa sbagliata)*

#### 12.3 Regola di Conflitto tra Feedback
*Cosa conterrà: severity più alta prevale; a parità prevale Judge Factual; feedback contraddittori risolti dal Reflector con prioritizzazione esplicita*

---

### 13. Oscillation Detector
*Cosa conterrà: tre tipologie di oscillazione rilevate e comportamento di escalazione*

#### 13.1 CSS Oscillation
*Cosa conterrà: varianza CSS sotto threshold per N≥4 iterazioni consecutive — sistema non converge*

#### 13.2 Semantic Oscillation
*Cosa conterrà: cosine similarity >85% tra draft_N e draft_{N-2} con divergenza su draft_{N-1} — testo torna e ritorna*

#### 13.3 Whack-a-Mole Detection
*Cosa conterrà: categorie di errore che cambiano completamente a ogni iterazione; escalazione dopo N=3 cicli*

#### 13.4 Escalazione Umana
*Cosa conterrà: interfaccia interattiva con CSS history e log draft — modifica inline sezione, riscrittura outline, override manuale con log motivazione, abbandono sezione*

---

### 14. Context Compressor
*Cosa conterrà: agente dedicato alla gestione della finestra di contesto per documenti lunghi*

#### 14.1 Regola di Compressione per Posizione
*Cosa conterrà: verbatim (ultime 2 sezioni), sommario strutturato (sezioni 3-5), estratto tematico (sezione 6+)*

#### 14.2 Identificazione Claim Load-Bearing
*Cosa conterrà: claim presupposti da sezioni future identificati dall'outline e preservati verbatim indipendentemente dalla posizione*

#### 14.3 Modello e Invocazione
*Cosa conterrà: qwen3-7b (leggero, task estrattivo), invocato dopo ogni approvazione di sezione — non prima della successiva*

---

### 15. Coherence Guard e Post-Flight QA
*Cosa conterrà: meccanismi di verifica coerenza inter-sezione e qualità finale*

#### 15.1 Coherence Guard
*Cosa conterrà: confronto claim fattuali cross-sezione prima dell'approvazione definitiva; livelli SOFT (log + warning) e HARD (escalazione umana con diff visuale)*

#### 15.2 Contradiction Detector
*Cosa conterrà: scan cross-sezione sul documento assemblato post-produzione; rilevamento affermazioni contraddittorie tra sezioni approvate in momenti diversi*

#### 15.3 Format Validator
*Cosa conterrà: verifica riferimenti formattati, sezioni outline presenti, lunghezza ±10% target_words*

---

### 16. Writer Memory
*Cosa conterrà: modulo di memoria degli errori ricorrenti del Writer nel corso del documento*

#### 16.1 Pattern Proibiti Ricorrenti
*Cosa conterrà: tracking forbidden patterns usati più di una volta, iniezione nel context prompt come avviso proattivo*

#### 16.2 Glossario Tecnico e Style Drift
*Cosa conterrà: terminologia coerente tra sezioni, monitoraggio variazione voce, alert se drift supera soglia*

#### 16.3 Tendenza alle Citazioni
*Cosa conterrà: tracking sotto-citazione o sovra-citazione storica, reminder proattivo al Writer con media run*

---

### 17. Layer di Ricerca Fonti
*Cosa conterrà: architettura dei connettori di fonte con interfaccia uniforme e Source Diversity Analyzer*

#### 17.1 Connettore Accademico
*Cosa conterrà: CrossRef, Semantic Scholar, arXiv, DOAJ — DOI, abstract, anno, reliability ≥0.80*

#### 17.2 Connettore Istituzionale
*Cosa conterrà: domini .gov/.eu/.un.org, Tavily con filtro, reliability ≥0.85*

#### 17.3 Connettore Web Generale
*Cosa conterrà: Tavily / Brave Search senza filtri, heuristics per reliability 0.40-0.70*

#### 17.4 Connettore Social
*Cosa conterrà: Reddit, Twitter/X Academic, reliability 0.20-0.40, utile per sentiment analysis*

#### 17.5 Scraper Fallback
*Cosa conterrà: BeautifulSoup + Playwright se API down, respect robots.txt*

#### 17.6 Upload Fonti Utente
*Cosa conterrà: PDF/DOCX caricati, processing locale, chunking + embedding, zero invio a provider cloud*

#### 17.7 Source Ranker
*Cosa conterrà: scoring per rilevanza, qualità abstract, recency, deduplication, adversarial source detection*

#### 17.8 Source Diversity Analyzer
*Cosa conterrà: verifica concentrazione fonti — max 40% stesso publisher, max 30% stesso autore, max 50% stesso anno; se concentrazione rilevata → Researcher ri-attivato con istruzione esplicita di diversificare; diversity_score nel Run Report per sezione*

#### 17.9 Interfaccia SourceConnector
*Cosa conterrà: firma `async def search(query, max_results) -> list[Source]`, plugin architecture per connettori custom*

---

### 18. Gestione e Verifica Citazioni
*Cosa conterrà: pipeline completa dalla raccolta fonti alla verifica nel draft*

#### 18.1 Mappa Citazioni e Formattazione
*Cosa conterrà: mapping source_id → stringa citazione; stili supportati (Harvard, APA, Chicago, Vancouver)*

#### 18.2 Verifica Deterministica
*Cosa conterrà: HTTP 200 check, DOI resolver via doi.org, titolo corrispondente*

#### 18.3 NLI Entailment Check
*Cosa conterrà: DeBERTa per verifica coerenza claim↔fonte, temporal consistency, quantitative consistency*

#### 18.4 Gestione Fonti senza URL
*Cosa conterrà: libri (ISBN), monografie, atti di conferenza, materiale d'archivio*

#### 18.5 Hallucination Rate Tracker
*Cosa conterrà: tracking storico per ogni modello del tasso di citazioni ghost non rilevate; tabella PostgreSQL model_id/run_id/ghost_count/total; dashboard Grafana; soglia alert: hallucination_rate >5% su 10+ run consecutive → valutare sostituzione modello*

---

### 19. Budget Controller
*Cosa conterrà: architettura completa del controllo economico deterministico*

#### 19.1 Pre-Run Budget Estimator
*Cosa conterrà: formula di stima costo per sezione (token_writer × price + token_jury_cascading × price × iter_medio + token_reflector × price + token_researcher × price); blocco se stima supera 80% del cap con proposta opzioni*

#### 19.2 Regime di Qualità Adattivo
*Cosa conterrà: Economy / Balanced / Premium — tabella budget_per_word / CSS_threshold / jury_size / max_iter / modelli; adattamento dinamico durante run a 70%/90%/100% del budget*

#### 19.3 Real-Time Cost Tracker
*Cosa conterrà: contatore token/costo per agente/sezione/iterazione; allarmi WARN 70%, ALERT 90%, HARD STOP 100%*

#### 19.4 Strategie di Risparmio Dinamico
*Cosa conterrà: fallback cascade, early stopping economico (approva con 2/3 giuria se budget critico), cache Redis, section cache, batching jury*

#### 19.5 Parametri di Severità come Variabili
*Cosa conterrà: CSS threshold, max iter, jury size, minority veto strictness come leve adattive al regime*

---

### 20. Error Handling Matrix e Resilienza
*Cosa conterrà: comportamento deterministico per ogni scenario di errore*

#### 20.1 Matrice Errori Completa
*Cosa conterrà: tabella errore → prima risposta → seconda risposta → escalazione; scenari: API 429, API 500/Timeout, output malformato, ghost citation, context overflow, crash processo*

#### 20.2 Retry Policy
*Cosa conterrà: exponential backoff (2s→4s→8s), jitter, max 3 retry, libreria tenacity*

#### 20.3 Circuit Breaker
*Cosa conterrà: stato CLOSED/OPEN/HALF-OPEN per ogni combinazione (slot, modello); apertura dopo 3 fallimenti in 60s; reset dopo 5 min; oggetto indipendente per ogni slot*

#### 20.4 Fallback Chain
*Cosa conterrà: cascata modelli per ogni slot agente configurata in YAML; circuit breaker indipendente per ogni livello della chain; JURY_DEGRADED warning se giuria opera con meno di 3 giudici*

#### 20.5 Graceful Degradation
*Cosa conterrà: giuria ridotta (1/3) con warning se giudici irraggiungibili; CSS ricalcolato su giudici effettivi; produzione continua; log escalazione*

---

### 21. Persistenza e Checkpointing
*Cosa conterrà: backend di persistenza, schema database, meccanismo di recovery*

#### 21.1 Backend PostgreSQL
*Cosa conterrà: tabelle documents, outlines, sections (Store permanente), jury_rounds, costs, sources, runs; sezioni approvate nello Store sono immutabili e sopravvivono ai crash del run*

#### 21.2 Checkpointing Automatico
*Cosa conterrà: AsyncPostgresSaver LangGraph dopo ogni super-step; thread_id salvato immediatamente alla creazione del run; resume automatico dall'ultimo nodo completato via thread_id*

#### 21.3 Cache Redis
*Cosa conterrà: fonti, valutazioni citazioni (riuso se cosine similarity >0.90), sommari Compressor, TTL 24h*

---

### 22. Sicurezza e Privacy
*Cosa conterrà: layer di sicurezza completo con compliance GDPR*

#### 22.1 Autenticazione e Autorizzazione
*Cosa conterrà: OAuth2 + JWT, user_id per documento, audit log accessi*

#### 22.2 Encryption
*Cosa conterrà: AES-256 at rest, TLS 1.3 in transit*

#### 22.3 PII Detection
*Cosa conterrà: presidio-analyzer (Microsoft) prima di ogni invio a modelli esterni; regex per email/telefoni/CF/IBAN; NER locale per nomi/organizzazioni/luoghi*

#### 22.4 Prompt Injection Guard (Source Sanitizer)
*Cosa conterrà: tre stadi — regex deterministico per pattern noti, isolamento strutturale XML nei prompt, monitoring output per jailbreak riusciti*

#### 22.5 Privacy Mode
*Cosa conterrà: cloud (default) / self_hosted (Ollama/VLLM, zero dati fuori infrastruttura) / hybrid (dati sensibili locale, giudici cloud); configurazione per utente Enterprise*

#### 22.6 GDPR Compliance
*Cosa conterrà: right to deletion, data export, data retention policy, audit log permanente*

#### 22.7 Dati Inviati a Provider Esterni
*Cosa conterrà: elenco esplicito di quali dati (topic, draft, fonti estratte) vanno a quali provider; mai invio di uploaded_sources in privacy mode*

---

### 23. Observability Stack
*Cosa conterrà: stack completo di monitoring, tracing e alerting*

#### 23.1 OpenTelemetry — Distributed Tracing
*Cosa conterrà: span per ogni agente call con attributi (run_id, section_idx, iteration, agent, model, tokens_in, tokens_out, cost_usd, latency_ms, outcome); trace ID propagato in tutti gli artefatti*

#### 23.2 Prometheus — Metriche Operative
*Cosa conterrà: counters/gauges/histograms — sections_approved, css_per_section, cost_per_run, api_failures_per_provider, oscillation_count, jury_degraded_count*

#### 23.3 Grafana — Dashboard
*Cosa conterrà: progress real-time, CSS trend, cost accumulator, latency P50/P95/P99, Rogue Judge monitor, hallucination rate per modello*

#### 23.4 Sentry — Error Tracking
*Cosa conterrà: errori strutturati con doc_id/section_idx/agent/contesto, stack trace, correlazione con trace_id*

#### 23.5 Async Progress Dashboard (Frontend Utente)
*Cosa conterrà: SSE standard — eventi SECTION_APPROVED, JURY_VERDICT, REFLECTOR_FEEDBACK, ESCALATION_REQUIRED, BUDGET_WARNING, RUN_COMPLETED; supporto Last-Event-ID per riconnessione*

#### 23.6 Log Strutturati JSON
*Cosa conterrà: formato obbligatorio doc_id/section_idx/iteration/agent/timestamp_iso/cost_delta/latency; testo libero vietato in produzione*

#### 23.7 Alerting
*Cosa conterrà: trigger — oscillazione rilevata, budget >80%, API failure consecutive N+, hallucination rate >5%, documento completato*

---

### 24. API REST e Integrazione Esterna
*Cosa conterrà: specifiche complete delle API esposte per integrazioni e DRS chain*

#### 24.1 Endpoint Principali
*Cosa conterrà: POST /v1/runs (avvia run), GET /v1/runs/{id} (stato), DELETE /v1/runs/{id} (cancella, sezioni approvate rimangono), GET /v1/documents/{id} (documento completo), GET /v1/documents/{id}/export?format=docx|pdf|markdown|latex (redirect S3 pre-firmato 15 min)*

#### 24.2 Streaming Real-Time (SSE)
*Cosa conterrà: GET /v1/runs/{id}/stream — eventi JSON tipizzati; chiusura automatica su RUN_COMPLETED; riconnessione via Last-Event-ID*

#### 24.3 Endpoint Human-in-the-Loop
*Cosa conterrà: POST /v1/runs/{id}/approve (outline_approval con modifiche opzionali, escalation_response con action/instructions), POST /v1/runs/{id}/pause (attende completamento sezione corrente), POST /v1/runs/{id}/resume*

#### 24.4 Autenticazione API
*Cosa conterrà: API key header X-DRS-Key per machine-to-machine, JWT Bearer per sessioni utente; rate limiting per key*

---

### 25. Testing Framework
*Cosa conterrà: strategia di test completa per sistema multi-agente*

#### 25.1 Golden Dataset
*Cosa conterrà: 20 documenti approvati su domini diversi con citazioni verificate e CSS ground truth umano*

#### 25.2 Unit Test
*Cosa conterrà: moduli deterministici — Citation Manager, Verifier, Publisher, Metrics Collector, Style Linter, Source Sanitizer; coverage target 90%*

#### 25.3 Integration Test con Mock LLM
*Cosa conterrà: MockLLMClient intercetta API, output predefiniti per ogni agente, test logica orchestratore a costo zero*

#### 25.4 Prompt Unit Test
*Cosa conterrà: set {input, expected_output_structure} per ogni prompt; verifica ad ogni modifica; fallimento = PR bloccata*

#### 25.5 Regression Test
*Cosa conterrà: validazione su golden dataset ad ogni modifica prompt/soglia; rollback automatico se CSS medio cala >0.05*

#### 25.6 Cost Test
*Cosa conterrà: verifica costo stimato sotto soglia preconfigurata per ogni run; alert se delta stima/reale >20%*

#### 25.7 Oscillation Simulation Test
*Cosa conterrà: input sintetici per innescare loop; verifica escalazione entro N iterazioni attese*

#### 25.8 Chaos Test
*Cosa conterrà: simula API down (429, 500, timeout) per testare fault tolerance; verifica circuit breaker e fallback chain*

#### 25.9 Evaluation Framework Qualità
*Cosa conterrà: BERTScore, citation validity rate, style compliance regex, inter-judge agreement (Cohen's kappa)*

#### 25.10 Dependency Injection Architecture
*Cosa conterrà: pattern di iniezione per ogni agente — LLMClient, SearchClient, DBClient come dipendenze iniettate al costruttore; in produzione: client reali; in test: mock; nessun agente istanzia direttamente client esterni; divieto import diretti di openai/anthropic/requests nei moduli agente*

#### 25.11 Smoke Suite per Fase MVP
*Cosa conterrà: suite eseguibile con singolo comando (make test-phase1/2/3/4); verifica funzionamento non qualità — "Writer produce output parsabile?", "Budget Estimator rispetta cap?", "retry si attiva su 429?"; durata <2 minuti; fase considerata completata SOLO dopo che la smoke suite passa*

---

### 26. Profili di Stile e Sistema L1/L2/L3
*Cosa conterrà: architettura completa dei profili linguistici con tre livelli di enforcement e preset predefiniti*

#### 26.1 Architettura a Tre Livelli L1/L2/L3
*Cosa conterrà: L1 FORBIDDEN — regex deterministico, blocco automatico zero eccezioni, verificato dallo Style Linter prima della giuria; L2 REQUIRED — elemento obbligatorio, blocco se assente; L3 GUIDE — valutato dalla mini-giuria S, abbassa CSS_style ma non blocca; formato regola YAML con id/level/category/enforcement/message/fix_hint*

#### 26.2 Profilo: scientific_report
*Cosa conterrà: registro formale C1/C2, forbidden patterns specifici (elenchi puntati, "it is important to note", "delve into"), required (abstract, bibliography ≥5 peer-reviewed, hedging su claim non certi), guide stile (variazione sintattica, nessuna ripetizione lessicale)*

#### 26.3 Profilo: business_report
*Cosa conterrà: linguaggio diretto, frasi brevi, struttura problem→evidence→recommendation, forbidden buzzword (synergy, leverage, paradigm shift), required (executive summary 200 parole, azione specifica per ogni raccomandazione)*

#### 26.4 Profilo: technical_documentation
*Cosa conterrà: logica procedurale, prerequisiti espliciti, comandi in code block, forbidden (simply/just/easily, metriche senza numero), required (output atteso dopo ogni comando non banale)*

#### 26.5 Profilo: journalistic
*Cosa conterrà: piramide rovesciata, lede forte, fonte primaria nominata, forbidden (apertura con definizione dizionario, "recentemente" senza data), required (dichiarazione esplicita se affermazione non verificata)*

#### 26.6 Profilo: narrative_essay
*Cosa conterrà: variazione ritmica, apertura con elemento concreto, filo narrativo tra sezioni, forbidden (meta-riferimenti al documento, connettivi meccanici)*

#### 26.7 Profilo: ai_instructions
*Cosa conterrà: ottimizzato per coding agent — chiarezza meccanica come valore, elenchi benvenuti, forbidden (vago, TBD, "se necessario", "best practice" senza elencarle), required (esempio concreto per ogni comportamento, conseguenza per ogni vincolo violato)*

#### 26.8 Profilo: blog
*Cosa conterrà: tono conversazionale, engagement, narrazione con inizio/sviluppo/conclusione, hyperlink inline, forbidden (formalismi accademici, strutture passive)*

#### 26.9 Forbidden Patterns Universali
*Cosa conterrà: lista pattern LLM trasversali a tutti i profili — "it is worth noting", "in conclusion", "as we can see", strutture triadiche "X, Y, and Z" ripetute, primo paragrafo con definizione dal dizionario; esempi buono/cattivo per ognuno*

#### 26.10 Personalizzazione Preset in Tre Modalità
*Cosa conterrà: Modo 1 linguaggio naturale (sistema converte in YAML, max 2 cicli raffinamento), Modo 2 form guidato visuale (tipo/condizione/messaggio/suggerimento), Modo 3 YAML diretto per utenti avanzati; salvataggio preset personalizzati con nome/descrizione/visibilità (solo io / team / pubblico)*

#### 26.11 Internazionalizzazione
*Cosa conterrà: forbidden patterns per lingua target, language-specific model selection per giuria Style, gestione cross-lingual citazioni (fonte in inglese, documento in italiano)*

---

### 27. Prompt Layer
*Cosa conterrà: architettura dei prompt come componente formale trasversale*

#### 27.1 Struttura dei Prompt (System / Context / Task)
*Cosa conterrà: system immutabile (identità, ruolo, vincoli assoluti, formato output), context dinamico (stato corrente, sezioni precedenti, fonti, feedback), task specifico per invocazione (istruzione precisa, vincolo parole, sezione corrente)*

#### 27.2 Anti-Sycophancy nei Giudici
*Cosa conterrà: istruzione esplicita a cercare errori attivamente — "non validare il testo, cerca prove che sia sbagliato"; tecnica con placebo draft; prompt persona "revisore severo"*

#### 27.3 Versionamento dei Prompt
*Cosa conterrà: prompt come file versionati con codice sorgente; log fallimenti per prompt version; revisione periodica programmata*

#### 27.4 Prompt Management e A/B Testing
*Cosa conterrà: prompt registry con metriche per versione, rollback automatico se CSS cala, DSPy per ottimizzazione automatica, Langfuse per tracking*

---

### 28. Modelli LLM — Assegnazione e Rationale
*Cosa conterrà: tabella completa modello→agente con giustificazione task-fit*

#### 28.1 Tabella Modelli per Agente
*Cosa conterrà: modello primario + fallback 1 + fallback 2 per ogni ruolo (Planner, Writer W-A/B/C, Fusor, Judge R1/R2/R3, Judge F1/F2/F3, Judge S1/S2/S3, Reflector, Context Compressor, Post-Draft Analyzer, Style Fixer, Span Editor, Run Companion)*

#### 28.2 Principio Task-Fit
*Cosa conterrà: selezione per capacità specifiche non per classifica benchmark assoluta; esempi di capacità decisive per ruolo*

#### 28.3 Model Verification Procedure
*Cosa conterrà: validazione pre-run che i modelli in YAML esistano su OpenRouter; fallback immediato se modello non disponibile*

#### 28.4 Prezzi e Aggiornamento
*Cosa conterrà: dizionario MODEL_PRICING $/M token; procedura aggiornamento periodico; impatto su Budget Estimator*

---

### 29. Configurazione YAML Completa
*Cosa conterrà: schema completo del file di configurazione con tutti i parametri*

#### 29.1 Sezione Utente
*Cosa conterrà: max_budget, target_words, language, style_profile, quality_preset*

#### 29.2 Sezione Modelli
*Cosa conterrà: modelli per agente, tier per giuria, fallback chains, temperature per Writer proposer*

#### 29.3 Sezione Convergenza
*Cosa conterrà: soglie CSS content/style, oscillation window/threshold, panel max rounds, jury weights*

#### 29.4 Sezione Fonti
*Cosa conterrà: connettori abilitati, max fonti/sezione, reliability score per tipo, diversity thresholds*

#### 29.5 Sezione Stile
*Cosa conterrà: riferimento a file profilo, extra_forbidden, extra_required, disabled_rules, style_calibration_gate enabled/disabled*

#### 29.6 Validazione Pydantic
*Cosa conterrà: schema validation pre-esecuzione, errori espliciti per valori fuori range, warning per configurazioni borderline*

---

### 30. Output del Sistema
*Cosa conterrà: specifiche complete di tutti i deliverable prodotti dal sistema*

#### 30.1 Proprietà del Documento Finale
*Cosa conterrà: lunghezza ±10% target_words, citazioni verificate, zero forbidden patterns L1, coerenza interna certificata dal Coherence Guard*

#### 30.2 Formati di Output
*Cosa conterrà: DOCX (python-docx con template), PDF (weasyprint/pandoc), Markdown, LaTeX (BibTeX), HTML (CSS responsive), JSON strutturato {sections[], citations[], metadata, metrics}*

#### 30.3 Publisher
*Cosa conterrà: assemblaggio sezioni dallo Store permanente, template grafico, sommario automatico, bibliografia, section cache*

#### 30.4 Run Report
*Cosa conterrà: JSON con costo totale per agente, iterazioni per sezione, CSS history, fonti per sezione, escalazioni, tempi, verdetti completi, conversazione Run Companion, hallucination_rate per modello*

#### 30.5 Output Multi-File per software_spec
*Cosa conterrà: directory strutturata (AGENTS.md, architecture.md, data_schema.sql, api_spec.yaml, features/ con file Gherkin), zip o git init*

#### 30.6 Feedback Collector
*Cosa conterrà: rating per sezione, highlight errori, blacklist fonti, training loop per miglioramento prompt nel tempo*

---

### 31. Pipeline Orchestrator — DRS Chain per Software
*Cosa conterrà: meccanismo di tre DRS in sequenza per produzione specifiche software con checkpoint umani*

#### 31.1 Tre Step Sequenziali
*Cosa conterrà: DRS#1 profilo functional_spec (COSA: PRD, user stories, acceptance criteria testabili con Given/When/Then), DRS#2 profilo technical_spec (COME: architecture.md, data_schema.sql, api_spec.yaml, feature files), DRS#3 profilo software_spec (output multi-file per coding agent); ogni DRS identico internamente, profilo e criteri giuria diversi*

#### 31.2 Pipeline Orchestrator
*Cosa conterrà: logica di coordinamento pura zero LLM — avvia DRS#1, genera Summary, attende approvazione umana, passa output + Decision Log a DRS#2, ripete; checkpoint obbligatorio tra step non opzionale*

#### 31.3 Decision Log
*Cosa conterrà: JSON prodotto dal Reflector accumulando decisioni non ovvie durante ogni DRS — struttura: decisione + motivazione + alternativa scartata; passa al DRS successivo come contesto aggiuntivo per preservare il "perché"*

#### 31.4 Summary Inter-Step
*Cosa conterrà: documento separato generato da agente leggero (gemini-2.5-flash) per approvazione in 5 min — struttura: cosa ha prodotto lo step, 5 decisioni chiave con motivazione, domande aperte per step successivo*

#### 31.5 Traceability Matrix
*Cosa conterrà: ogni sezione di technical_spec dichiara quale acceptance criterion di functional_spec soddisfa; Coherence Guard del DRS#2 verifica che nessun AC rimanga scoperto; formato: AC-007 → satisfies: [componente] → mechanism: [dettaglio misurabile]*

#### 31.6 Modalità Operative
*Cosa conterrà: functional_spec standalone, technical_spec standalone (con functional scritto dall'utente), full_pipeline automatizzato con checkpoint; regola pratica: functional spec >30 min riflessione → due step separati*

---

### 32. Interfaccia Utente e Human-in-the-Loop
*Cosa conterrà: tutti i punti di interazione utente-sistema*

#### 32.1 Wizard di Configurazione
*Cosa conterrà: form step-by-step per topic, stile, fonti, budget — style profile presets con preview esempio output*

#### 32.2 Outline Editor Visuale
*Cosa conterrà: drag-and-drop sezioni, inline editing titoli/scopo, outline revision request se Researcher trova fonti insufficienti*

#### 32.3 Progress Dashboard Real-Time
*Cosa conterrà: % completamento, sezione corrente, iterazione, CSS trend per sezione, costo accumulato, ETA stimata*

#### 32.4 Escalation Interface
*Cosa conterrà: modifica inline sezione problematica, riscrittura outline, override manuale con log motivazione, diff visuale*

#### 32.5 Section Regeneration e Versioning
*Cosa conterrà: sblocco sezione approvata con costo stimato, rigenerazione con istruzioni aggiuntive, versioni archiviate*

#### 32.6 Style Override su Sezione Approvata
*Cosa conterrà: correzione stile di sezione già approvata SENZA interrompere produzione sezioni successive — accodata per Style Fixer con istruzioni utente; versione originale rimane nello Store fino ad approvazione nuova; diff visuale prima/dopo*

#### 32.7 Interfaccia Run Companion
*Cosa conterrà: chat sidebar sempre visibile durante il run, notifiche proattive badge, log conversazione nel Run Report*

---

### 33. Stack Tecnologico
*Cosa conterrà: tabella completa di tutte le tecnologie con motivazione*

#### 33.1 Orchestrazione e Runtime
*Cosa conterrà: LangGraph (cicli condizionali nativi, state persistente, checkpointing PostgreSQL)*

#### 33.2 Backend e API
*Cosa conterrà: FastAPI + Uvicorn, Pydantic per validazione, WebSocket/SSE per streaming*

#### 33.3 Frontend
*Cosa conterrà: Streamlit (MVP) → Next.js (produzione)*

#### 33.4 Job Queue
*Cosa conterrà: Celery + Redis per documenti lunghi in background, pub/sub per progress events*

#### 33.5 Database e Cache
*Cosa conterrà: PostgreSQL (stato, sezioni Store permanente, log, jury_rounds), Redis (cache fonti, pub/sub), S3/MinIO (documenti finali)*

#### 33.6 LLM Routing
*Cosa conterrà: OpenRouter — accesso unificato, fallback automatico, rate limiting, MODEL_PRICING aggiornabile*

#### 33.7 NLP Utilities
*Cosa conterrà: sentence-transformers (similarity), DeBERTa (NLI entailment), textstat (Flesch-Kincaid), presidio-analyzer (PII), tenacity (retry)*

#### 33.8 Output Generation
*Cosa conterrà: python-docx (DOCX), weasyprint/pandoc (PDF), markdown (MD), BibTeX (LaTeX)*

#### 33.9 Containerizzazione e CI/CD
*Cosa conterrà: Docker Compose (dev/staging con Mock LLM), Kubernetes (prod con autoscaling), GitHub Actions (test su PR, deploy su merge main)*

#### 33.10 Dipendenze Complete (pyproject.toml)
*Cosa conterrà: lista completa dipendenze Python con versioni e motivazione per ogni pacchetto*

---

### 34. Deployment e Infrastruttura
*Cosa conterrà: ambienti, scalabilità, rate limiting verso provider*

#### 34.1 Ambienti (Dev / Staging / Prod)
*Cosa conterrà: Dev con Mock LLM e PostgreSQL locale, Staging con modelli reali a budget ridotto e dati anonimi, Prod con autoscaling e backup PostgreSQL ogni ora*

#### 34.2 Rate Limiting verso Provider
*Cosa conterrà: OpenRouter 60 req/min, CrossRef 50 req/s, Tavily rispetto Retry-After; semafori asyncio per throttling*

#### 34.3 Scalabilità
*Cosa conterrà: agenti come microservizi scalabili, Celery 1000 job/giorno, hierarchical summarization per documenti >50k parole*

#### 34.4 Struttura del Progetto (Directory Tree)
*Cosa conterrà: albero completo delle directory — src/agents/, src/jury/, src/pipeline/, config/, prompts/, tests/unit/ tests/integration/ tests/smoke/, scripts/*

---

### 35. Roadmap MVP — Piano a 4 Fasi
*Cosa conterrà: piano di implementazione incrementale con obiettivi, scope e smoke suite per fase*

#### 35.1 Fase 1 — MVP Core (4 settimane)
*Cosa conterrà: 1 Writer + 1 Judge F + 1 Judge S, fonti web Tavily, output Markdown, max 1 iterazione, budget cap fisso deterministico; smoke suite: Writer produce output parsabile, budget rispettato, pipeline end-to-end su topic campione*

#### 35.2 Fase 2 — Multi-Judge (4 settimane)
*Cosa conterrà: giurie 3×3 complete, minority veto, CSS, Reflector, Panel Discussion, Oscillation Detector, checkpointing PostgreSQL; smoke suite: oscillazione rilevata su input sintetico, veto blocca sezione, resume da crash*

#### 35.3 Fase 3 — Advanced Features (6 settimane)
*Cosa conterrà: Planner, fonti accademiche CrossRef/Semantic Scholar, NLI DeBERTa, Context Compressor, Coherence Guard, Style Calibration Gate, Style Fixer, MoW+Fusor, DOCX+PDF, Privacy Mode; smoke suite: Style Exemplar salvato e iniettato, Compressor riduce contesto, Coherence Guard rileva contraddizione sintetica*

#### 35.4 Fase 4 — Production (8 settimane)
*Cosa conterrà: Web UI Next.js, Celery queue, OpenTelemetry+Prometheus+Grafana, Run Companion, Pipeline Orchestrator DRS chain, security audit GDPR, load testing 1000 job/giorno, plugin system; smoke suite: Run Companion risponde in <3s, DRS chain completa functional→technical, alert Grafana si attivano su oscillazione simulata*

---

### 36. KPI e Metriche di Successo
*Cosa conterrà: definizione quantitativa del successo del sistema*

#### 36.1 Metriche di Qualità
*Cosa conterrà: human acceptance rate >90%, citation accuracy >98%, L1 violation rate post-Style Fixer <1%, error density <1/1000 parole*

#### 36.2 Metriche di Efficienza Economica
*Cosa conterrà: cost/doc $20-50 per 10k parole, cost/word <$0.004, first-time approval >60%, avg iterations <2.5*

#### 36.3 Metriche di Affidabilità
*Cosa conterrà: uptime >99.5%, recovery rate 100%, API failure recovery >95%, MTTR <5 min*

#### 36.4 Metriche di Convergenza
*Cosa conterrà: oscillation rate <5%, panel discussion rate <15%, budget overrun 0%, style drift index <0.05*

#### 36.5 Metriche MoW
*Cosa conterrà: first-attempt approval >55%, delta vs single-writer >+15pp, fusor integration rate >60%, break-even a ≤1.5 iterazioni risparmiate*

#### 36.6 Metriche Run Companion
*Cosa conterrà: response time <3s, proactive alert relevance >70%, pre-escalation intervention rate >30%, modification execution rate >40%*

#### 36.7 Metriche Style Gate
*Cosa conterrà: Style Gate pass rate primo tentativo >70%, Style Fixer convergence rate >90%, style drift index <0.05*

---

### 37. Estendibilità e Plugin System
*Cosa conterrà: interfacce standard per estensione senza modifica del codice core*

#### 37.1 Interfaccia SourceConnector
*Cosa conterrà: contratto `async def search(query, max_results) -> list[Source]` per connettori custom (database aziendali, Elasticsearch, vector DB)*

#### 37.2 Interfaccia Judge
*Cosa conterrà: hook per aggiungere mini-giurie domain-specific (es. Judge Legal, Judge Medical) senza modificare l'Aggregatore*

#### 37.3 Interfaccia OutputFormatter
*Cosa conterrà: plugin per formati di output aggiuntivi oltre i 6 standard*

#### 37.4 Multi-Document Mode
*Cosa conterrà: glossario condiviso tra documenti della stessa serie, citation reuse (fonti già verificate non rielaborate), cross-referencing, style consistency cross-document*

---

### 38. Regole Operative per l'AI Builder
*Cosa conterrà: istruzioni imperative non negoziabili per l'agente AI che implementerà il sistema*

#### 38.1 Ordine delle Operazioni
*Cosa conterrà: preflight prima di ogni run, thread_id salvato immediatamente alla creazione (non dopo prima iterazione), Pydantic per ogni JSON parsing (mai json.loads diretto), default FAIL su parse_error*

#### 38.2 Regole di Parallelismo
*Cosa conterrà: tre mini-giurie in asyncio.gather parallelo, Writer proposer MoW in parallelo, Reflector sempre sequenziale; mai await in loop su operazioni parallelizzabili*

#### 38.3 Regole di Logging
*Cosa conterrà: JSON strutturato con doc_id/section_idx/iteration/agent/timestamp_iso obbligatori; testo libero vietato in produzione; ogni log correlabile a trace_id*

#### 38.4 Regole WebSocket e Progress
*Cosa conterrà: worker Celery pubblica su Redis pub/sub; WebSocket endpoint inoltra al client; mai polling, sempre push*

#### 38.5 Dependency Injection Obbligatoria
*Cosa conterrà: mai chiamate API esterne dirette nei moduli agente — sempre attraverso client iniettati al costruttore; import diretti di openai/anthropic/requests vietati nei file src/agents/*; ogni agente testabile con MockLLMClient senza connessione di rete*
