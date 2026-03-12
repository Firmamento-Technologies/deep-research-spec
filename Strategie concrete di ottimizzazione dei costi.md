## Architettura del sistema

Il cuore dell’architettura è il grafo LangGraph definito in `src/graph/graph.py`, con 32 nodi reali che coprono l’intero ciclo di vita del documento: preflight/budgeting, pianificazione, loop di sezione (researcher → citation pipeline → SHINE/Writer → jury/aggregator → reflector/panel/coherence) e fase di post‑QA/publishing. La struttura è chiaramente sezionata in fasi (“Phase A: Pre-Flight \& Setup”, “Phase B: Section Loop — Research Pipeline”, “Phase C: Post-Flight QA”, “Phase D: Publisher \& Output”), con il controllo del flusso espresso tramite router puramente funzionali (`src/graph/routers/*.py`), il che rende leggibile il percorso di esecuzione pur nella complessità complessiva.

Lo stato globale condiviso è modellato da un grande `TypedDict` `DocumentState` in `src/graph/state.py`, che include sottostati specializzati (`BudgetState`, `JudgeVerdict`, `AggregatorVerdict`, `ReflectorOutput`, `SectionCSSReport`, ecc.) e riduttori bounded per cronologie (es. `css_history` e `draft_embeddings`) per evitare blow‑up di memoria e contesto. Questo è un punto di forza perché rende esplicito il contratto tra i nodi, ed è coerente con le raccomandazioni su memory e state management nei survey recenti sui sistemi multi‑agent LLM. Tuttavia, il `DocumentState` è diventato chiaramente monolitico: contiene responsabilità eterogenee (config utente, stato di RAG/SHINE, RLM, budget, panel discussion, human‑in‑the‑loop, output paths) in un unico tipo, aumentando il rischio di regressioni quando si modifica il modello dati.[^1_1][^1_2]

L’entrypoint CLI `src/main.py` costruisce uno stato iniziale minimale (_build_initial_state) e poi delega tutto al grafo, con checkpointer pluggable (Postgres o MemorySaver). Qui c’è una discrepanza: molti campi che il commento in `DocumentState` dichiara “CONTRATTO LANGGRAPH: campo OBBLIGATORIO” (`rlm_mode`, `section_budget_usd`, `status`, `doc_id`, `user_id`, ecc.) non sono popolati in `_build_initial_state` e devono quindi essere inizializzati implicitamente in nodi successivi come `preflight_node` e `budget_estimator_node`. Questo rompe il principio “single source of truth” e rende fragile il ripristino da checkpoint: se un nodo dimentica di impostare un campo obbligatorio, il resume può produrre stati inconsitenti senza errori espliciti.

Il pattern architetturale globale è quello tipico dei sistemi di deep research agentici descritti nella survey “Deep Research: A Survey of Autonomous Research Agents”: pianificazione, esplorazione iterativa del web/delle fonti, compressione/integrazione del contesto, generazione, valutazione multi‑criterio, riflessione e revisione, con loop e possibili escalation a human‑in‑the‑loop. L’uso di un planner dedicato (`planner_node`), di un researcher asincrono (`researcher_node`), di un writer complesso con SHINE/RLM (`writer_node`), di un jury multi‑modello (`jury_node`) e di moduli di riflessione/panel/coerenza (`reflector_node`, `panel_discussion_node`, `coherence_guard_node`) è in linea con i pattern emersi in framework come AutoAgents e AgentScope, che promuovono architetture modulari e specializzate per agenti LLM multi‑ruolo.[^1_3][^1_4][^1_2][^1_5]

D’altro lato, molti nodi sono “God node” di fatto. `writer_node` in `src/graph/nodes/writer.py` incorpora tre path distinti (SHINE LoRA, RLM, standard), gestisce budget guard, costruzione del prompt, format di citazione, caricamento profili di stile da YAML e interazione diretta con l’LLM client, tutto in una singola funzione. Questo viola la Single Responsibility in modo piuttosto netto e rende molto difficile testare o sostituire singolarmente le componenti (es. cambiare solo la policy RLM senza toccare la logica SHINE). Similmente, `context_compressor.run` in `src/graph/nodes/context_compressor.py` mescola policy di budget token, integrazione SHINE (hypernetwork + adapter registry MinIO/Redis) e compressione LLM/tassonomica, con logica non banale per la gestione dei tier e del budget.

La parte “multi‑agent” è implementata principalmente come nodi e funzioni specializzate in un unico processo, non come processi separati o servizi indipendenti, il che è coerente con la maggior parte delle architetture multi‑agent LLM di produzione che puntano a orchestrazioni in‑process per contenere latenza e complessità di orchestrazione. Tuttavia, la dipendenza da un singolo grafo grande significa che qualsiasi modifica strutturale (es. introdurre un nuovo path di revisione) richiede editing centralizzato di `build_graph`, invece di comporre sottografi riusabili come fa LangGraph nelle best practice più recenti (workflow modulari riutilizzabili).[^1_6][^1_1]

***

## Analisi dei costi

La parte costi è molto più curata della media dei progetti open‑source. `src/llm/pricing.py` definisce una tabella `MODEL_PRICING` unica, allineata (almeno nominalmente) ai prezzi API 2025–2026: ad esempio `anthropic/claude-sonnet-4` a 3$/M input e 15$/M output, in linea con la documentazione e i tracker di prezzo recenti per Claude 3.7 Sonnet, `openai/o3-mini` a 1.10$/M input e 4.40$/M output, e Qwen/QWQ con prezzi aggressivi (es. `qwen/qwen3-7b` a 0.03/0.05 \$/M). La funzione `cost_usd(model_id, tokens_in, tokens_out)` calcola il costo per chiamata in modo deterministico e viene usata da `LLMClient._build_result` per arricchire ogni risposta con `cost_usd`, `tokens_in`, `tokens_out` e metadati di caching.[^1_7][^1_8][^1_9][^1_10][^1_11][^1_12]

Il client unificato `LLMClient` in `src/llm/client.py` astrae Anthropic, OpenAI, Google e OpenRouter, applicando un rate‑limiter per modello (`rlm_rate_limiter`) basato su stima dei token (`estimate_tokens`) e riportando tutte le metriche a Prometheus via `observe_llm_call`. Questo è un allineamento diretto con le best practice per sistemi agentici cost‑sensibili in letteratura, che raccomandano un contatore centralizzato di costi e meccanismi di rate‑limiting per modello/ruolo, piuttosto che un throttling globale. Inoltre, l’uso di `cache_control` Anthropic nelle system blocks (ephemeral cache ~5 minuti per regole di stile ed exemplar) riduce i token input effettivi per sezioni successive rispetto ai token logici nel prompt, sfruttando il discount “cached tokens” previsto dal pricing Anthropic.[^1_2][^1_9][^1_1]

La stima pre‑run è affidata a `estimate_run_cost` e `budget_estimator_node` in `src/budget/estimator.py`. `estimate_run_cost` prende in input numero di sezioni, parole target, budget massimo e alcuni parametri di pricing “conservativi” hardcoded: `price_writer_out = 75.0` (claude‑opus‑4‑5), `price_jury_t1_out = 1.10` (tier1 medio tipo QWQ/sonar/llama), `price_jury_t2_out = 12.0` (tier2 medio tipo o3‑mini/gemini‑flash/mistral‑l), `price_reflector_out = 40.0` (o3) e `price_researcher_out = 1.0` (sonar). Il modello assume circa 1.5 token/word per l’output writer, ~800 token per researcher e reflector, e 9 giudici tier1 + fino a 3 tier2 in caso di disaccordo, con un fattore 1.4 per Mixture‑of‑Writers. Tutto questo viene moltiplicato per un `avg_iter` di default 2.5 iterazioni per sezione. Il risultato è una stima di costo per sezione e totale che viene confrontata con il budget utente; se la proiezione supera l’80% del cap, il run viene bloccato a monte (`blocked=True`, `status="failed"`).

Le operazioni più costose in termini di token sono chiaramente: (1) il writer (specialmente in modalità premium con Opus‑like e ancora di più in modalità RLM, che apre un REPL ricorsivo), (2) il jury multi‑pannello con fino a 9 chiamate in parallelo per sezione (`JudgeR`, `JudgeF`, `JudgeS`), e (3) i loop di riflessione/panel (`reflector`, `panel_discussion`, `oscillation_check`, `span_editor`) che possono ri‑attivare writer, jury e altri nodi in caso di conflitti o bassa CSS. Il fatto che esista un controller specifico per i sotto‑call RLM (`RLMBudgetController` in `src/budget/controller.py`, con aggregazione di `rlm_tokens_total` e `rlm_cost_total`) è un indizio esplicito che l’RLM path è considerato un moltiplicatore di costo rispetto al path standard, confermato dalle note d’uso che parlano di sub‑call ricorsive invisibili al tracker principale.

Un problema pratico è che i default di prezzo in `estimate_run_cost` sono molto più pessimisti dei prezzi effettivi per alcuni modelli scelti: ad esempio, Sonnet 3.7 costa 15$/M output e non 75$/M come `claude-opus-4-5`, e `o3-mini` costa 4.40$/M output, non 12$/M, mentre Qwen2.5 72B è nell’ordine di 0.39$/M output. Questo vuol dire che la proiezione può sovrastimare il costo di 3–5× rispetto alla realtà se il routing effettivo usa modelli più economici, con il rischio di bloccare run che in pratica sarebbero perfettamente sostenibili. Inversamente, se per errore il routing sale davvero a `openai/gpt-4.5` o `anthropic/claude-opus-4-5` per certi path, la stima potrebbe addirittura essere ottimistica, perché non tiene conto di casi peggiori come gpt‑4.5 a 150$/M output.[^1_8][^1_9][^1_10][^1_13][^1_11][^1_12][^1_14][^1_7]

***

## Strategie concrete di ottimizzazione dei costi

La base di cost control c’è già: `budget_estimator_node` blocca run troppo costosi, `BudgetState` traccia `spent_dollars`, allarmi 70/90% e `hard_stop_fired`, il `budget_controller_node` nel grafo usa un router dedicato (`route_budget`) per deviare verso `publisher` in caso di esaurimento budget, e `check_budget` viene chiamato esplicitamente in `writer_node` (path standard e RLM) per forzare `force_approve` quando l’ultima iterazione non è più sostenibile. Tuttavia, mancano alcune ottimizzazioni chiave:

Una prima leva è ricalibrare `estimate_run_cost` e, più in generale, `MODEL_PRICING`, per riflettere ciò che veramente usi in produzione. Se la writer slot bilanciata/premium è in realtà `anthropic/claude-sonnet-4` o un Sonnet 3.7 equivalante, la `price_writer_out` dovrebbe essere dell’ordine di 15$/M output, non 75$/M, riducendo drasticamente i falsi positivi di blocco e rendendo il regime “Premium” utilizzabile anche con budget moderati (es. 20–30$). Analogamente, per il jury tier2 potresti allineare `price_jury_t2_out` al mix effettivo di modelli (es. o3‑mini + Gemini Flash + Mistral Large), la cui media reale è più vicina ai 4–6$/M output che ai 12\$/M attuali.[^1_9][^1_10][^1_13][^1_7]

Secondo, il router di modelli (`route_model`, `route_jury_slots` in `src/llm/routing.py`, usato da `writer_node` e `jury_node`) già implementa una logica di tiering con fallback laterale: same‑tier ma provider diverso prima di un “tier upgrade”, con guard `RLM_ALLOW_TIER_UPGRADE` che blocca upgrade verticali se non esplicitamente consentiti, proprio per evitare salti di costo silenziosi 10–20×. Questo è ottimo, ma può essere reso ancora più aggressivo: per ruoli di classificazione pura (style lint, CSS scoring, conflict detection) puoi vincolare il routing a modelli low‑cost come `qwen/qwen3-7b` o `meta/llama-3.3-8b-instruct`, lasciando i modelli costosi solo ai ruoli di generazione (writer, panel discussion) e di riflessione ad alta complessità.

Terzo, potresti sfruttare molto di più SHINE per comprimere il contesto lato writer e jury, come già inizi ad abbozzare in `context_compressor.run`: sezioni “verbatim_shine” vengono codificate in LoRA adapter con costo di ~0.3s e zero token, mantenendo nel testo solo le Load‑Bearing Claims (LBC) e riducendo il budget token dedicato alle sezioni precedenti al 15% della context window del writer (200k token per Sonnet/Opus). Al momento però la parte “STRUCTURED_SUMMARY” è implementata come semplice troncone stringa e non come compressione LLM usando il `qwen/qwen3-7b` menzionato nei commenti, quindi non stai realmente ribilanciando il trade‑off qualità/contesto dove il costo LLM sarebbe minimo. Implementare davvero quel path con un modello ultra‑economico (Qwen3‑7B, Llama 8B) ti consentirebbe di ridurre sistematicamente i token che finiscono nel prompt del writer e dei giudici, con un impatto significativo su costi ricorrenti.[^1_15][^1_16]

Quarto, il caching: stai sfruttando il prompt caching Anthropic solo nel writer, tramite blocchi `system` con `cache_control: {type: "ephemeral"}` per regole di stile ed exemplar, ma pattern analoghi potrebbero essere applicati ai nodi di valutazione (JudgeS, Reflector, CoherenceGuard) che spesso riusano le stesse linee guida su più sezioni o iterazioni. Dato che Anthropic fattura i cached tokens con uno sconto marcato rispetto agli input normali, standardizzare l’uso di blocchi cache‑able per tutte le “policy” ripetitive (linee guida di stile, definizioni di dimensioni di valutazione, rubriche NLI) può abbattere il costo effettivo anche del 30–50% per run lunghi.[^1_9]

Infine, l’RLM path va usato con molta parsimonia. Ora `rlm_mode` può essere attivato da config o automaticamente per preset premium con corpus che eccede la context window del writer, e `writer_node` gli assegna un “estimated_cost” fisso di 1.50\$ nella guard `check_budget`, indipendentemente dal numero reale di sub‑call. Considerato che i reasoning model costosi (o3, DeepSeek‑R1) hanno prezzi non trascurabili, ti conviene spostare l’attivazione di `rlm_mode` su una logica data‑driven: solo se le metriche CSS mostrano oscillazioni ripetute (`oscillation_detected`, `oscillation_type`) e se il budget residuo per sezione è sopra una soglia, oppure solo su sezioni esplicitamente “difficili” (identificate dal planner) invece che sull’intero documento.[^1_11][^1_17]

***

## Modelli LLM alternativi per ruolo

La tabella `MODEL_PRICING` mostra che hai già in mente un portafoglio di modelli piuttosto ricco (Anthropic Opus/Sonnet, OpenAI o3/o3‑mini/gpt‑4.5/gpt‑4o, Gemini 2.5 Pro/Flash, Perplexity Sonar, DeepSeek‑R1, QWQ/Qwen3‑7B, Mistral Large, Llama 3.x). Quello che manca oggi non è tanto il “quali modelli” ma il “quale modello per quale ruolo” codificato in modo sistematico nel router, in particolare facendo un mapping esplicito task→modello per minimizzare costo e massimizzare qualità.

Per il writer: oggi il commento in `estimate_run_cost` assume un writer premium basato su `claude-opus-4-5`, ma i prezzi effettivi suggeriscono che Sonnet 3.7 (3$/M input, 15$/M output, 200k context) è il punto ottimale di trade‑off costo/qualità per long‑form reasoning, con performance competitive sui benchmark di reasoning avanzato. Per preset “economy” e “balanced” potresti mappare `route_model("writer", preset)` rispettivamente a `qwen/qwen3-7b` o `meta/llama-3.3-8b-instruct` (quando l’output atteso è relativamente breve o il livello di finezza stilistica è meno critico), sfruttando prezzi nell’ordine di centesimi di dollaro per M token.[^1_7][^1_8][^1_9]

Per il jury: il design a pannelli eterogenei in `jury_node` è molto buono — ogni mini‑jury R/F/S usa modelli diversi per ridurre herd bias, come suggerito da lavori su “diverse committee of models” (es. ChatEval). Dato che il compito del jury è principalmente scoring classificativo (CSS contribution) e detection di errori/fabbricazioni, puoi tranquillamente ancorare la maggior parte dei giudici a modelli mid‑tier low‑cost come `qwen/qwq-32b`, `qwen/qwen3-7b` e `meta/llama-3.3-70b-instruct`, riservando uno slot “premium” solo alla dimensione più critica (es. fact‑checking contenutistico tramite DeepSeek‑R1 o o3‑mini). Questo riduce drasticamente il costo di 9 giudici/iterazione, mantenendo una diversità epistemica sufficiente.[^1_18][^1_13][^1_14]

Per researcher, context compression e QA post‑hoc: `ResearcherNode` per ora usa solo un connettore locale (`MemvidConnector`), con TODO per sonar‑pro/tavily/brave, quindi il grosso del costo di retrieval non arriva ancora da LLM. Quando aggiungerai connettori LLM‑centrici (es. Sonar), conviene usare modelli tipo `perplexity/sonar` o `qwen/qwen3-7b` soprattutto per snippet brevi, dato che i benchmarking su agentic RAG mostrano che modelli mid‑tier sono spesso sufficienti per ranking e snippet extraction, lasciando la responsabilità di reasoning globale al writer principale. Analogamente, per `context_compressor` il commento prevede l’uso di `qwen/qwen3-7b` per la tier “STRUCTURED_SUMMARY”; qui è quasi sempre sprecato usare Opus/Sonnet, perché il compito è puro riassunto strutturato.[^1_19][^1_20]

Per i ruoli di riflessione/coerenza/panel (`reflector_node`, `panel_discussion_node`, `coherence_guard_node`, `post_qa_node`), che non abbiamo ispezionato ma che il grafo usa come loop di raffinamento e come punti di decisione, la letteratura sugli agentic RAG e sistemi multi‑agent mostra che spesso la qualità marginale di un modello premium viene sfruttata male se queste fasi non sono fortemente vincolate e guidate da strutture ben specificate. Una combinazione pragmatica potrebbe essere: riflessione principale su un reasoning model relativamente economico (o3‑mini, DeepSeek‑R1), con fallback sotto condizioni specifiche (CSS molto bassa + budget ampio) a un Opus‑like, invece di usare sempre e solo il modello più costoso.[^1_20][^1_5][^1_2]

***

## Confronto con letteratura recente (2023–2025)

Le scelte progettuali sono, nel complesso, ben allineate alle direzioni emerse nella letteratura su sistemi multi‑agent LLM e agentic RAG. I survey su LLM‑enabled multi‑agent systems e sulle architetture agentiche mettono l’accento su quattro aspetti: architettura modulare, memoria esplicita e persistente, pianificazione+riflessione, e controllo di costo/risorse. Il tuo sistema implementa tutti e quattro: il grafo LangGraph con 32 nodi separa chiaramente i ruoli; `DocumentState` e i suoi sottotipi rappresentano una memoria strutturata e persistere via checkpointer; nodi come `planner`, `reflector`, `panel_discussion` e `coherence_guard` incarnano pattern di planning e reflection; e la pipeline di budget con estimate, enforcement e reportistica centralizzata segue le raccomandazioni per i sistemi cost‑aware.[^1_1][^1_2][^1_6]

La survey su Agentic RAG sottolinea l’importanza di pipeline a più passi con agenti che orchestrano retrieval, filtraggio, compressione del contesto e generazione, con cicli di feedback e adattamento dinamico delle strategie di retrieval. L’integrazione `ResearcherNode` → `citation_manager`/`citation_verifier` → `source_sanitizer` → `source_synthesizer` → `context_compressor`/SHINE → `writer` implementa esattamente questo pattern, con in più l’uso sperimentale di SHINE per spostare conoscenza da contesto a parametri via LoRA adapters, in linea con l’idea di hypernetwork per adapter generation proposta nel paper SHINE. Questo è probabilmente uno degli aspetti più avanzati dell’intero sistema rispetto allo stato dell’arte open‑source.[^1_16][^1_19][^1_15][^1_20]

D’altro lato, lavori critici sui sistemi multi‑agent LLM hanno mostrato che spesso il guadagno reale rispetto a un singolo modello forte e ben progettato è limitato, mentre costi e complessità crescono rapidamente; in molti benchmark, aumentare il numero di agenti/step peggiora la robustezza o causa “alignment collapse” nelle conversazioni troppo lunghe. Il fatto che il tuo grafo includa loop multipli (post‑draft gap → targeted researcher → nuovo writer, style loop, panel self‑loop, oscillation loop, await_human, section checkpoint, post‑QA) implica un rischio concreto di over‑engineering rispetto ai guadagni marginali di qualità, soprattutto finché non hai misure solide di ablation per ogni path. Qui la letteratura suggerisce esplicitamente di introdurre metriche di efficacia per ogni componente agentico, e disattivare pattern che non offrono miglioramenti misurabili rispetto al costo extra.[^1_21][^1_5][^1_2]

Infine, la survey “Deep Research: A Survey of Autonomous Research Agents” propone una tassonomia di quattro fasi (planning, question decomposition, web exploration, report generation) e sottolinea la necessità di benchmark specifici per valutare agenti di deep research, non solo metriche generiche tipo BLEU/ROUGE. Il tuo sistema mappa quasi uno‑a‑uno queste fasi, ma non è chiaro (a livello di codice in questo branch) se tu abbia già integrato benchmark o harness di valutazione automatica per comparare configurazioni di modelli e di grafo. Senza questo, rischi di non sfruttare l’architettura ricca che hai costruito per prendere decisioni data‑driven.[^1_5]

***

## Punti di forza principali

Un primo punto di forza è la completezza architetturale: `build_graph` registra tutti i nodi e i router necessari per coprire l’intero ciclo di deep research, dalla pre‑run budget estimation fino alla raccolta di feedback post‑pubblicazione, senza stubs residui nel branch (tutti i 32 nodi elencati in `NODES` hanno una reale implementazione associata in `_REAL_NODES`). Questo rende il sistema realmente eseguibile come pipeline di produzione, non solo come prototipo parziale.

Un secondo punto forte è la gestione del budget e dei costi: `estimate_run_cost`, `budget_estimator_node`, `BudgetState`, `RLMBudgetController`, `LLMClient` con `cost_usd` e metriche Prometheus creano una catena end‑to‑end dalla previsione al tracking runtime, fino alla reportistica, in linea con i migliori esempi accademici e industriali di sistemi multi‑agent cost‑aware. Pochi progetti open‑source hanno una modellazione così esplicita di `budget_per_word`, regimi Economy/Balanced/Premium, allarmi 70/90% e hard stop.[^1_2][^1_1]

Terzo, l’integrazione di SHINE nel context compressor e nel writer è tecnicamente ambiziosa e varia: usi SHINE per encodare le ultime sezioni approvate in LoRA adapter, conservando nel testo solo le LBC, e propaghi la presenza di adapter verso il writer tramite stato (`active_lora_section_idxs` e `shine_lora`), con un budget token dedicato pari al 15% della MECW (max effective context window). Questo è coerente con il paper SHINE, che mostra come mappare contesti lunghi in LoRA per ridurre drasticamente la latenza e il costo di generazione senza perdere capacità di ragionamento sul contesto stesso.[^1_15][^1_16]

Quarto, il design del jury con pannelli eterogenei e thread pool modulare è robusto: `jury_node` usa un `ThreadPoolExecutor` modulare di livello modulo per evitare overhead di creazione pool per sezione, e delega a `route_jury_slots` la scelta di modelli diversi per ogni slot R/F/S, seguendo evidenze empiriche (p.es. ChatEval) che panels eterogenei migliorano robustness e riducono herd bias. Inoltre, la storia dei verdict è esplicitamente bounded a `_MAX_HISTORY_ROUNDS = 10`, prevenendo overflow nel contesto e in memoria.[^1_18]

Quinto, l’entrypoint `run_pipeline` in `src/main.py` è relativamente pulito e integra prometheus metrics, checkpointer Postgres, CLI, e logging strutturato JSON, il che facilita il deployment in ambienti reali (K8s, orchestratori) rispetto a prototipi puramente notebook‑based. L’allineamento con LangGraph come orchestratore e Postgres come store per i checkpoint è anche coerente con quello che appare nei lavori più recenti sulle architetture multi‑agent LLM di produzione.[^1_6][^1_1]

***

## Criticità principali (con priorità)

Una criticità ad **alta priorità** è la complessità eccessiva del `DocumentState` e la discrepanza tra il contratto dei commenti e l’inizializzazione reale. `DocumentState` dichiara decine di campi obbligatori con commenti molto rigidi sul fatto che “campi non dichiarati non vengono serializzati dal checkpointer e sono sempre None al resume”, ma `_build_initial_state` non li fornisce affatto; ci si affida quindi a una serie di nodi intermedi per popolare lo stato prima che venga usato da altri nodi. Questo pattern è fragile: un refactoring di un nodo può facilmente introdurre bug “silenziosi” al resume (es. `rlm_mode` che torna False dopo un interrupt), esattamente il tipo di problema che i commenti dicono di voler evitare.

Una seconda criticità ad **alta priorità** è il rischio di mismatch tra il routing effettivo dei modelli e la configurazione di `MODEL_PRICING`/`estimate_run_cost`. Usare come default di stima `claude-opus-4-5` a 75$/M output e `openai/gpt-4.5` a 150$/M output mentre in pratica userai modelli come Sonnet 3.7, o3‑mini e Qwen 2.5 rende le proiezioni inutilmente pessimistiche, e soprattutto ti nasconde il vero costo dei rami “premium”: se in futuro qualcuno abilita davvero i tier più alti (es. `RLM_ALLOW_TIER_UPGRADE=true` o mapping writer→gpt‑4.5), il salto di costo sarà di ordini di grandezza rispetto alle aspettative, nonostante le guardie di fallback laterale. In pratica oggi hai un “catalogo prezzi” molto potente, ma non ancora integrato in modo sicuro e trasparente con la policy di routing.[^1_10][^1_13][^1_14][^1_8][^1_7][^1_9]

Una terza criticità a **priorità medio‑alta** è l’eccessiva concentrazione di responsabilità in nodi chiave come `writer_node` e `context_compressor.run`, che combinano controlli di budget, selezione path (SHINE vs RLM vs standard), costruzione prompt, integrazione di memoria (`writer_memory`), gestione delle citazioni, caricamento di configurazioni YAML e interazione diretta con LLM client. Questo non solo rende difficile testare le singole componenti, ma crea anche colli di bottiglia architetturali: qualsiasi cambiamento nel modo di gestire RLM o SHINE richiede di toccare file critici, aumentando il rischio di regressioni. Dato quanto è complesso il sistema, la mancanza di una chiara separazione tra “policy” e “execution” in questi nodi è una debolezza reale.

Una quarta criticità a **priorità media** è il fatto che alcune parti cruciali della pipeline sono ancora TODO o stub mascherati. In `context_compressor._handle_llm_compression` il commento esplicito dice “TODO: Replace stub with qwen/qwen3-7b call via src/llm/client.py”, ma il codice attuale fa solo slicing/testo. `ResearcherNode` usa un solo connettore locale e lascia come TODO connettori web/accademici moderni (sonar/tavily/brave). Questo significa che, nonostante l’architettura agentica sia completa sulla carta, la pipeline di deep research effettiva è ancora lontana da ciò che la letteratura su Agentic RAG descrive come “autonomous research pipeline” realmente connessa al web e a fonti eterogenee.[^1_20][^1_5]

Una quinta criticità a **priorità media** è la mancanza, in questo branch, di un layer esplicito di valutazione/ablation per i pattern multi‑agent introdotti (panel, oscillation, targeted research). Alla luce di studi che mostrano come molti sistemi multi‑agent falliscano nel fornire benefici significativi rispetto a single‑agent forti, pur aumentando moltissimo costo e complessità, introdurre ogni ulteriore loop senza avere un harness di valutazione automatica per misurare il miglioramento di qualità per dollaro è una scelta rischiosa. In termini pratici: stai pagando (in complessità e potenzialmente in token) per molte fasi agentiche di cui non è chiaro, nel codice, se tu abbia numeri a supporto.[^1_21][^1_2]

Infine, una criticità a **priorità medio‑bassa** ma concreta è la manutenibilità complessiva: il livello di commenti “normativi” nelle docstring (riferimenti a paragrafi §x.y, contratti LangGraph, regimi, ecc.) è altissimo e utile ora che il sistema è fresco, ma rende molto facile la divergenza tra documentazione e implementazione man mano che il progetto evolve. Senza test end‑to‑end e unitari solidi per ciascun nodo e router, ogni refactoring rischia di invalidare parti della “specification by comments” senza che nessuno se ne accorga, cosa che la letteratura sulle architetture multi‑agent complesse sconsiglia esplicitamente.[^1_5][^1_1][^1_6]

***

In sintesi: l’implementazione in questo branch è tecnicamente sofisticata e in molti punti avanti rispetto alla media (soprattutto su budget e SHINE), ma allo stato attuale paga un prezzo alto in complessità e rischio di costo non controllato. Il passo successivo dovrebbe essere meno “aggiungere feature” e più consolidare: ridurre la superficie del grafo per i path che non danno guadagni misurabili, rendere il routing realmente data‑driven sul piano dei costi, e normalizzare la separazione tra policy e execution nei nodi critici.
<span style="display:none">[^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_30][^1_31][^1_32][^1_33][^1_34][^1_35][^1_36][^1_37][^1_38][^1_39][^1_40][^1_41][^1_42][^1_43][^1_44][^1_45][^1_46][^1_47][^1_48][^1_49][^1_50][^1_51][^1_52][^1_53]</span>

<div align="center">⁂</div>

[^1_1]: https://arxiv.org/abs/2601.03328

[^1_2]: https://arxiv.org/pdf/2402.03578.pdf

[^1_3]: http://arxiv.org/pdf/2402.14034.pdf

[^1_4]: http://arxiv.org/pdf/2309.17288.pdf

[^1_5]: https://arxiv.org/pdf/2508.12752.pdf

[^1_6]: https://arxiv.org/html/2506.10467v4

[^1_7]: https://pricepertoken.com/pricing-page/model/anthropic-claude-3.7-sonnet

[^1_8]: https://blog.galaxy.ai/model/claude-3-7-sonnet

[^1_9]: https://www.anthropic.com/news/claude-3-7-sonnet

[^1_10]: https://cloudprice.net/models/gradient_ai/openai-o3-mini

[^1_11]: https://simonwillison.net/2025/Jan/31/o3-mini/

[^1_12]: https://designforonline.com/ai-models/openai-o3-mini/

[^1_13]: https://cloudprice.net/models/deepinfra%2FQwen%2FQwen2.5-72B-Instruct

[^1_14]: https://blog.galaxy.ai/model/qwen-2-5-72b-instruct

[^1_15]: https://arxiv.org/abs/2602.06358

[^1_16]: https://arxiv.org/html/2602.06358v1

[^1_17]: https://perunit.ai/models/o3

[^1_18]: https://arxiv.org/abs/2312.09348

[^1_19]: https://arxiv.org/html/2501.09136v3

[^1_20]: https://arxiv.org/abs/2501.09136

[^1_21]: https://arxiv.org/pdf/2503.13657.pdf

[^1_22]: https://www.sciltp.com/journals/ijndi/2024/1/347

[^1_23]: https://www.scitepress.org/DigitalLibrary/Link.aspx?doi=10.5220/0012239100003598

[^1_24]: https://arxiv.org/abs/2410.22932

[^1_25]: https://arxiv.org/abs/2409.08264

[^1_26]: https://arxiv.org/abs/2409.06289

[^1_27]: https://www.osti.gov/servlets/purl/2462994/

[^1_28]: https://arxiv.org/abs/2405.20859

[^1_29]: https://aclanthology.org/2024.wassa-1.30

[^1_30]: https://arxiv.org/abs/2411.01114

[^1_31]: https://arxiv.org/html/2504.00587v1

[^1_32]: https://arxiv.org/abs/2502.19091

[^1_33]: https://arxiv.org/pdf/2411.07464.pdf

[^1_34]: https://arxiv.org/pdf/2311.06622.pdf

[^1_35]: https://arxiv.org/html/2504.01963v1

[^1_36]: https://arxiv.org/pdf/2501.06322.pdf

[^1_37]: https://arxiv.org/abs/2506.01839

[^1_38]: https://arxiv.org/list/cs.MA/2024-02

[^1_39]: https://arxiv.org/list/cs.MA/recent

[^1_40]: https://xue-guang.com/post/llm-marl/

[^1_41]: https://arxiv.org/pdf/2506.10408.pdf

[^1_42]: https://openaccess.thecvf.com/content/ICCV2025/papers/Shenaj_LoRA.rar_Learning_to_Merge_LoRAs_via_Hypernetworks_for_Subject-Style_Conditioned_ICCV_2025_paper.pdf

[^1_43]: http://arxiv.org/pdf/2503.18129.pdf

[^1_44]: https://aclanthology.org/2023.emnlp-main.614.pdf

[^1_45]: https://arxiv.org/pdf/2407.13168.pdf

[^1_46]: https://arxiv.org/pdf/2305.13707.pdf

[^1_47]: http://arxiv.org/pdf/2404.13813.pdf

[^1_48]: https://cloudprice.net/models/openrouter%2Fanthropic%2Fclaude-3.7-sonnet

[^1_49]: https://langcopilot.com/claude-sonnet-3.7-vs-gemini-3-pro-pricing

[^1_50]: https://siliconangle.com/2025/02/24/anthropics-claude-3-7-sonnet-reasoning-model-can-think-long-want/

[^1_51]: https://artificialanalysis.ai/models/qwen2-5-72b-instruct

[^1_52]: https://openrouter.ai/anthropic/claude-3.7-sonnet

[^1_53]: https://simonwillison.net/2025/May/22/updated-anthropic-models/


---

# tieni conto di questo https://m.youtube.com/watch?v=eAqv0EK4XUg https://huggingface.co/collections/Qwen/qwen35

Integro volentieri Qwen 3.5/3.5‑Small nel ragionamento precedente: cambia parecchio il quadro di costo/qualità, soprattutto per i ruoli “economy/balanced”.[^2_1][^2_2][^2_3]

## Implicazioni architetturali di Qwen 3.5

La famiglia Qwen 3.5 introduce modelli da 0.8B fino a ~400B con contesti nativi 262k–1M token, nuova architettura “next” più efficiente in RAM e velocità di decoding, e forti capacità multimodali/agentiche.[^2_1][^2_4][^2_5][^2_3] Questo ha due effetti diretti sul tuo DRS: (1) puoi spostare buona parte delle fasi non‑critiche (researcher, compressione, parte del jury, riflessione) su modelli Qwen 3.5 Small (0.8B–9B, eventualmente serviti via GGUF/Unsloth o Groq), mantenendo latenza bassissima e costo quasi nullo; (2) puoi usare i mid‑tier (es. 35B‑A3B) come writer/judge “premium” open‑source in contesti self‑hosted, riducendo drasticamente la dipendenza da Sonnet/o3 per preset economy/balanced.[^2_2][^2_4][^2_5][^2_6]

In pratica, nella tua `route_model(purpose, preset)` puoi mappare:

- writer economy/balanced → `qwen/Qwen3.5-9B` o `Qwen3.5-35B-A3B` (self‑hosted, long‑context, costo marginale);
- jury_t1 (R/F/S) → combinazione di Qwen 3.5 Small (0.8B/2B/4B) per la maggioranza e un singolo slot “premium” (Sonnet/o3‑mini/DeepSeek‑R1) solo dove serve;[^2_1][^2_2][^2_7]
- context_compressor tier “structured_summary” → Qwen 3.5 Small 2B/4B, che nei test community gestisce bene summarization/analysis con contesti 262k token.[^2_7][^2_6]

Questo ti consente di mantenere l’architettura multi‑fase ricca che hai ora, ma con un “substrato” open‑source molto più economico e scalabile: Sonnet e o3‑mini diventano tool chirurgici, non il backbone di tutto.

## Aggiornamento analisi costi con Qwen 3.5

Rispetto a `MODEL_PRICING` attuale, Qwen 3.5 (soprattutto in hosting proprio o via provider economici) ha un costo per token significativamente inferiore ai modelli closed di fascia alta, con performance su reasoning e coding che nei video e nelle review early user sono competitive con GPT‑4o/Sonnet per molti task pratici.[^2_1][^2_2][^2_7][^2_3] Questo significa che puoi rivedere almeno tre cose:

1. Parametri di default in `estimate_run_cost` (`price_writer_out`, `price_jury_t1_out`, `price_researcher_out`) per preset economy/balanced, assumendo un backbone Qwen 3.5 Small/Medium invece di Opus/Sonnet.[^2_2][^2_4]
2. La scelta di modelli per `route_jury_slots`: la maggioranza dei giudici può essere Qwen 3.5 4B/9B (cheap, veloci), con uno slot “diverso” (es. DeepSeek‑R1, Sonnet) solo per dimensioni critiche, riducendo di molto il costo del pannello 3R+3F+3S.[^2_2][^2_7]
3. Tutte le fasi di supporto (reflector, coherence_guard, post_qa) possono spostarsi su Qwen 3.5 9B/35B‑A3B per preset economy/balanced, riservando i modelli top solo a sezioni flaggate come “difficili” o conflittuali.

Dato che Qwen 3.5 supporta nativamente contesti 262k/1M, questo si integra bene anche con la tua logica SHINE: in molti casi potresti addirittura spegnere SHINE per preset economy e usare direttamente Qwen 3.5 Medium come writer long‑context, risparmiando la complessità (e latenza) dell’hypernetwork, e tenere SHINE come ottimizzazione opzionale per preset premium.[^2_1][^2_4][^2_5]

## Revisione raccomandazioni modello/ruolo alla luce di Qwen 3.5

Ritoccando quanto scritto prima, alla luce del video e della collection HF:

- **Writer**
    - Economy: Qwen 3.5 9B (o 4B se i test interni lo confermano) per sezioni ≤5–7k parole, zero o minima dipendenza da closed;[^2_2][^2_6]
    - Balanced: Qwen 3.5‑35B‑A3B per “core text” + Sonnet/o3‑mini solo per sezioni segnate come “difficili” (oscillazioni, panel escalation);[^2_1][^2_4][^2_5]
    - Premium: Sonnet 3.7 o o3‑mini/gpt‑4.5, ma solo se `budget.regime` e `budget_per_word` lo giustificano, altrimenti Qwen 3.5‑35B può coprire anche molti casi premium.
- **Jury / valutatori**
    - Tier1: Qwen 3.5 Small (0.8B–2B–4B) + Llama 3.3 8B per slot eterogenei a basso costo;[^2_2][^2_7][^2_6]
    - Tier2: DeepSeek‑R1, o3‑mini o Sonnet per minoranza di casi (solo se CSS<0.5, conflitti seri, o panel richiesto).
- **Researcher / RAG / compressori**
    - Qwen 3.5 Small (2B/4B) per ranking, snippet extraction, compressione strutturata, QA sulle fonti, con fallback eventuale a Sonar/DeepSeek solo quando serve reasoning molto pesante.[^2_2][^2_7]

Questo si sposa bene con il messaggio dei video: Qwen 3.5 Small è “incredibly good” per task agentici/coding anche su device mobili, quindi nel tuo contesto può diventare il workhorse dei task non‑critici, abbattendo costi e permettendo runs più lunghi senza ansia di budget.[^2_1][^2_7][^2_3]

Ti andrebbe bene se nel prossimo passo entriamo più nel dettaglio su come vorresti integrare Qwen 3.5 nel tuo stack (self‑hosted su GPU, via OpenRouter, via altri provider) così da proporre una mappatura concreta `route_model` → modelli Qwen 3.5 per ogni preset?
<span style="display:none">[^2_10][^2_11][^2_12][^2_13][^2_14][^2_15][^2_16][^2_17][^2_18][^2_19][^2_20][^2_21][^2_22][^2_8][^2_9]</span>

<div align="center">⁂</div>

[^2_1]: https://www.youtube.com/watch?v=X6mL3cdPiCg

[^2_2]: https://huggingface.co/collections/unsloth/qwen35

[^2_3]: https://huggingface.co/collections/Qwen/qwen35

[^2_4]: https://huggingface.co/Qwen/Qwen3.5-35B-A3B-Base

[^2_5]: https://huggingface.co/Qwen/Qwen3.5-35B-A3B

[^2_6]: https://huggingface.co/Qwen/Qwen3.5-0.8B

[^2_7]: https://www.youtube.com/watch?v=hQoF_dv2UQ4

[^2_8]: https://arxiv.org/pdf/2309.16609.pdf

[^2_9]: https://arxiv.org/html/2503.01307

[^2_10]: https://arxiv.org/html/2501.15570v1

[^2_11]: https://arxiv.org/pdf/2311.07919.pdf

[^2_12]: http://arxiv.org/pdf/2501.06638.pdf

[^2_13]: https://arxiv.org/pdf/2308.12966.pdf

[^2_14]: http://arxiv.org/pdf/2411.05934.pdf

[^2_15]: http://arxiv.org/pdf/2410.05318.pdf

[^2_16]: https://www.youtube.com/shorts/YiHKYmiFQes

[^2_17]: https://www.youtube.com/watch?v=thqELFdBleo

[^2_18]: https://www.youtube.com/playlist?list=PL7MWVbn0t0rx_Ew0Kq7Lij9dmz6jB-tI0

[^2_19]: https://www.youtube.com/watch?v=-eOKvXyP6yg

[^2_20]: https://www.youtube.com/watch?v=HBLjEVTtDjg

[^2_21]: https://www.youtube.com/watch?v=pwrJ4kiqk-Q

[^2_22]: https://www.youtube.com/watch?v=sYl1VdjKTcc


---

# valuta e implementa come usare al meglio i modelli qwen 3.5

Qwen 3.5 rappresenta un’opportunità eccellente per ottimizzare il tuo DRS, grazie a una famiglia di modelli open‑source con dimensioni da 0.8B a 397B (MoE), contesti nativi 262k–1M token, architettura “next” (RNN‑attention hybrid) per efficienza su GPU, e performance competitive su reasoning/coding con Sonnet/o3‑mini a frazioni di costo.[^3_1][^3_2][^3_3][^3_4][^3_5][^3_6] Nei benchmark early (GPQA, AIME, coding), Qwen 3.5 Small/Medium supera spesso Claude 3.5 Sonnet e o3‑mini su task agentici, con guadagni in velocità e costo, rendendolo ideale per il tuo stack multi‑agent.[^3_1][^3_7][^3_5]

## Strategia di utilizzo ottimale

### 1. Mapping per ruolo e preset (priorità: alta)

Usa Qwen 3.5 come **backbone open‑source** per preset economy/balanced, riservando closed models (Sonnet 3.7, o3‑mini) solo a preset premium o task critici (es. panel discussion, writer in loop di oscillazione). Ecco una mappatura concreta da integrare in `src/llm/routing.py` (estendi `route_model` e `route_jury_slots`):


| Ruolo/Nodo | Preset Economy | Preset Balanced | Preset Premium | Motivazione e costo stimato |
| :-- | :-- | :-- | :-- | :-- |
| **Writer** (`writer_node`) | Qwen3.5‑9B‑Instruct (self‑hosted) | Qwen3.5‑35B‑A3B | Claude 3.7 Sonnet / o3‑mini | Qwen 3.5 gestisce long‑form + SHINE/RLM bene; costo ~0.2–0.9$/M token vs 15$/M Sonnet.[^3_8][^3_9] |
| **Jury Tier1** (`jury_node`) | Qwen3.5‑2B/4B/0.8B (eterogenei) | Qwen3.5‑9B + Llama 3.3‑8B | Qwen3.5‑35B + DeepSeek‑R1 | Scoring/classificazione: Small modelli bastano; 9 giudici a ~0.2\$/M token.[^3_2][^3_7][^3_8] |
| **Researcher** (`researcher_node`) | Qwen3.5‑4B | Qwen3.5‑9B | Sonar Pro / DeepSeek‑R1 | Snippet/ranking: low‑cost, long‑context nativo 262k.[^3_2][^3_10] |
| **Context Compressor** | Qwen3.5‑2B | Qwen3.5‑4B | Qwen3.5‑9B | Summarization: Small + efficiente su GPU; integra con SHINE tier.[^3_2][^3_7] |
| **Reflector / Panel / QA** | Qwen3.5‑4B | Qwen3.5‑9B | o3‑mini / Sonnet | Reasoning leggero: Qwen 3.5 Small supera o3‑mini su molti task.[^3_5][^3_9] |

**Implementazione nel router** (snippet per `src/llm/routing.py`):

```python
QWen35_MAPPING = {
    "writer": {
        "economy": "qwen/qwen3.5-9b-instruct",
        "balanced": "qwen/qwen3.5-35b-a3b",
        "premium": "anthropic/claude-3.7-sonnet"  # fallback closed
    },
    "jury_r": {"economy": "qwen/qwen3.5-2b", "balanced": "qwen/qwen3.5-4b", "premium": "deepseek/deepseek-r1"},
    # ... estendi per F/S, researcher, etc.
}

def route_model(purpose: str, preset: str, allow_upgrade: bool = False) -> str:
    model = QWen35_MAPPING.get(purpose, {}).get(preset, "qwen/qwen3.5-4b")  # default safe
    # ... logica fallback laterale/verticale esistente
    return model
```

Aggiorna `MODEL_PRICING` con prezzi reali (es. 0.2$/M per Small via OpenRouter/self‑hosted, 0.9$/M per 35B).[^3_8][^3_9]

### 2. Deployment: Self‑hosted vs API (priorità: alta)

- **Self‑hosted (raccomandato per volume)**: Usa llama.cpp o vLLM su GPU (RTX 4090/5090 o A100/H100).
    - Qwen3.5‑9B/35B: ~10–20GB VRAM in Q4_K_M (Dynamic 4‑bit MoE offload); 24GB VRAM + 64GB RAM per 35B.[^3_11][^3_12][^3_6]
    - Comando esempio (llama.cpp server, OpenAI‑compatibile):

```
./llama-server --model Qwen3.5-35B-A3B-Q4_K_M.gguf --host 0.0.0.0 --port 8080 --ctx-size 262144 --temp 0.3
```

Punta `LLMClient` a `http://localhost:8080/v1` invece di OpenRouter.[^3_12][^3_6]
    - Vantaggi: costo →0 (solo elettricità), privacy totale, no rate limit. Integra con Docker/VPS Hostinger come fai già.
- **API (per burst/scale)**: OpenRouter (0.2$/M Small, 0.9–1$/M Medium, free tier per modelli base),[^3_8][^3_13][^3_14] o Groq (se supportato, ultra‑low latency). Evita per preset premium (usa Sonnet diretto).

**Raccomandazione**: Self‑host Small/Medium su VPS/GPU locale per 80% dei task; fallback API per premium.

### 3. Ottimizzazioni costi/qualità (priorità: media)

- **Quantizzazione**: Q4_K_M o MXFP4_MoE per Qwen3.5 MoE (35B‑A3B); riduce VRAM 50–70% con <2% drop qualità.[^3_12][^3_6]
- **Batching + caching**: Usa vLLM per batch multi‑sezione; estendi Anthropic‑style cache_control a Qwen via prompt engineering (ripeti regole in blocchi fissi).
- **Tiered routing dinamico**: In `budget_controller`, se `spent_dollars > 70%`, forza downgrade a Qwen3.5 Small per ruoli non‑critici.
- **SHINE + Qwen**: Qwen3.5 1M context riduce necessità SHINE; usalo solo per corpus >500k token.

Aggiorna `estimate_run_cost` con prezzi Qwen: `price_writer_out_economy=0.2`, `price_jury_t1_out=0.2`, ecc.[^3_8]

### 4. Test e validazione (priorità: alta)

Prima di deploy:

1. Benchmarka Qwen3.5 vs tuo stack attuale su metriche CSS (content/style/composite) da run campione.
2. Ablation: confronta preset con/senza Qwen (es. writer Qwen vs Sonnet).
3. Integra in `metrics_collector_node`: traccia “model used” per sezione e correlalo con CSS finale.

Questo abbatte costi del 60–80% su preset economy/balanced mantenendo qualità, grazie a Qwen3.5 che “crash” modelli concorrenti su molti benchmark agentici.[^3_1][^3_15][^3_5]

Quale deployment preferisci partire (self‑hosted su VPS/GPU o API OpenRouter) per i primi test con Qwen3.5?
<span style="display:none">[^3_16][^3_17][^3_18][^3_19][^3_20][^3_21][^3_22][^3_23][^3_24][^3_25]</span>

<div align="center">⁂</div>

[^3_1]: https://www.youtube.com/watch?v=X6mL3cdPiCg

[^3_2]: https://huggingface.co/collections/unsloth/qwen35

[^3_3]: https://huggingface.co/Qwen/Qwen3.5-35B-A3B-Base

[^3_4]: https://huggingface.co/Qwen/Qwen3.5-35B-A3B

[^3_5]: https://www.getpassionfruit.com/blog/comparing-claude-3-7-sonnet-claude-3-5-sonnet-openai-o3-mini-deepseek-r1-and-grok-3-beta

[^3_6]: https://www.datacamp.com/tutorial/run-qwen-3-5-locally

[^3_7]: https://www.youtube.com/watch?v=hQoF_dv2UQ4

[^3_8]: https://pricepertoken.com

[^3_9]: https://cloudprice.net/models/openrouter/qwen/qwen3-coder-plus

[^3_10]: https://arxiv.org/pdf/2501.15383.pdf

[^3_11]: https://news.ycombinator.com/item?id=47292522

[^3_12]: https://unsloth.ai/docs/models/qwen3.5

[^3_13]: https://costgoat.com/pricing/openrouter-free-models

[^3_14]: https://openrouter.ai/qwen/qwen-max

[^3_15]: https://www.youtube.com/watch?v=sYl1VdjKTcc

[^3_16]: https://arxiv.org/pdf/2309.16609.pdf

[^3_17]: https://aclanthology.org/2023.emnlp-main.614.pdf

[^3_18]: https://arxiv.org/pdf/2305.05176.pdf

[^3_19]: https://www.atlascloud.ai/it/models/qwen/qwen3-coder-promote

[^3_20]: https://pricepertoken.com/pricing-page/model/qwen-qwen3-vl-32b-instruct

[^3_21]: https://macaron.im/blog/qwen-3-5-vs-gpt-5-vs-claude

[^3_22]: https://anotherwrapper.com/tools/llm-pricing/qwen-3-14b

[^3_23]: https://forum.cursor.com/t/sonnet-3-5-vs-o3-mini/51054

[^3_24]: https://www.reddit.com/r/CLine/comments/1jfi8qc/what_is_the_best_priceperformance_api_provider_in/

[^3_25]: https://apxml.com/posts/qwen-3-5-system-requirement-vram-guide


---

# tenendo conto della conversazione e delle risposte ricevute  scrivi il prompt per continuare la ricerca precedente ma cercando soluzioni nuove e di frontiera ma affidabile per ridurre i costi e migliorare il sistema

Esegui un'analisi critica approfondita del software nel branch `claude/analyze-software-features-5xwWs` del repository [https://github.com/Firmamento-Technologies/deep-research-spec](https://github.com/Firmamento-Technologies/deep-research-spec), focalizzandoti su **soluzioni nuove e di frontiera ma affidabili (2024–2026)** per ridurre i costi e migliorare scalabilità/qualità, tenendo conto della conversazione precedente (Qwen 3.5, SHINE, RLM, LangGraph, budget estimator, jury eterogeneo, DocumentState monolitico).

Non apportare modifiche al codice o ai file. L’analisi deve coprire:

1. **Architettura: ottimizzazioni frontier**
    - Identifica paper/framework recenti (arXiv 2024–2026) su “cost-effective multi-agent LLM orchestration” o “modular LangGraph workflows” che validano o superano il tuo design (es. AgentNet, Nexusflow, BudgetMLAgent, Agentic RAG surveys).
    - Proponi refactoring affidabili: decomposizione DocumentState in sottostati composabili; sottografi LangGraph riutilizzabili per loop (style, panel, oscillation); pattern “single‑agent strong” vs multi‑agent per fasi non‑critiche.
    - Valuta integrazione Qwen 3.5 (self‑hosted/API) con SHINE/RLM per hybrid open/closed.
2. **Costi: tecniche frontier di riduzione**
    - Analizza costi attuali con prezzi aggiornati (Qwen 3.5 Small/Medium, Sonnet 3.7, o3‑mini; verifica OpenRouter/Groq marzo 2026).
    - Identifica le operazioni più costose (writer RLM, jury 9x, loop reflection) e proponi strategie concrete da paper recenti: speculative decoding, MoE routing dinamico, distillation agentica, “FrugalGPT” (multi‑model cascade), KV cache quantization.
    - Stima savings: es. Qwen3.5‑9B self‑hosted per 80% task; batching vLLM; tiered caching (Anthropic + Redis per SHINE adapters).
3. **Modelli alternativi: Qwen 3.5 + frontier**
    - Valuta Qwen 3.5 (0.8B–397B) per task specifici (reasoning, synthesis, extraction, classification) vs Claude/o3; proponi mapping role→modello con self‑hosting (llama.cpp/vLLM) vs API.
    - Aggiungi modelli frontier: DeepSeek R2 (2026), Grok 3.5, Mistral Large 2.5, Gemini 3 Flash; priorita costo/qualità con benchmark GPQA/AIME/coding.
4. **Confronto con stato dell’arte 2024–2026**
    - Confronta con paper recenti su “low‑cost autonomous research agents”, “efficient multi‑agent RAG”, “SHINE variants/hypernetworks 2025–2026”.
    - Segnala validazioni/contraddizioni: es. “Why Multi‑Agent LLM Systems Fail?”; “Deep Research Agents Survey 2025”; nuovi benchmark per agentic workflows.
5. **Punti di forza/criticità aggiornati**
    - Aggiorna lista forza/criticità con focus su Qwen 3.5/SHINE.
    - Priorità (alta/media/bassa) per interventi: es. alta per routing dinamico Qwen.

Fornisci l’analisi in italiano, con riferimenti precisi a file/funzioni/config. Sii diretto e tecnico. Includi snippet codice pronti per `routing.py`, `MODEL_PRICING`, `writer_node` per integrazioni Qwen 3.5. Usa tool per prezzi aggiornati e paper.

---

# Esegui un'analisi critica approfondita del software nel branch claude/analyze-software-features-5xwWs del repository [https://github.com/Firmamento-Technologies/deep-research-spec](https://github.com/Firmamento-Technologies/deep-research-spec), focalizzandoti su soluzioni nuove e di frontiera ma affidabili (2024–2026) per ridurre i costi e migliorare scalabilità/qualità, tenendo conto della conversazione precedente (Qwen 3.5, SHINE, RLM, LangGraph, budget estimator, jury eterogeneo, DocumentState monolitico).

Non apportare modifiche al codice o ai file. L’analisi deve coprire:
Architettura: ottimizzazioni frontier
Identifica paper/framework recenti (arXiv 2024–2026) su “cost-effective multi-agent LLM orchestration” o “modular LangGraph workflows” che validano o superano il tuo design (es. AgentNet, Nexusflow, BudgetMLAgent, Agentic RAG surveys).
Proponi refactoring affidabili: decomposizione DocumentState in sottostati composabili; sottografi LangGraph riutilizzabili per loop (style, panel, oscillation); pattern “single‑agent strong” vs multi‑agent per fasi non‑critiche.
Valuta integrazione Qwen 3.5 (self‑hosted/API) con SHINE/RLM per hybrid open/closed.
Costi: tecniche frontier di riduzione
Analizza costi attuali con prezzi aggiornati (Qwen 3.5 Small/Medium, Sonnet 3.7, o3‑mini; verifica OpenRouter/Groq marzo 2026).
Identifica le operazioni più costose (writer RLM, jury 9x, loop reflection) e proponi strategie concrete da paper recenti: speculative decoding, MoE routing dinamico, distillation agentica, “FrugalGPT” (multi‑model cascade), KV cache quantization.
Stima savings: es. Qwen3.5‑9B self‑hosted per 80% task; batching vLLM; tiered caching (Anthropic + Redis per SHINE adapters).
Modelli alternativi: Qwen 3.5 + frontier
Valuta Qwen 3.5 (0.8B–397B) per task specifici (reasoning, synthesis, extraction, classification) vs Claude/o3; proponi mapping role→modello con self‑hosting (llama.cpp/vLLM) vs API.
Aggiungi modelli frontier: DeepSeek R2 (2026), Grok 3.5, Mistral Large 2.5, Gemini 3 Flash; priorita costo/qualità con benchmark GPQA/AIME/coding.
Confronto con stato dell’arte 2024–2026
Confronta con paper recenti su “low‑cost autonomous research agents”, “efficient multi‑agent RAG”, “SHINE variants/hypernetworks 2025–2026”.
Segnala validazioni/contraddizioni: es. “Why Multi‑Agent LLM Systems Fail?”; “Deep Research Agents Survey 2025”; nuovi benchmark per agentic workflows.
Punti di forza/criticità aggiornati
Aggiorna lista forza/criticità con focus su Qwen 3.5/SHINE.
Priorità (alta/media/bassa) per interventi: es. alta per routing dinamico Qwen.
Fornisci l’analisi in italiano, con riferimenti precisi a file/funzioni/config. Sii diretto e tecnico. Includi snippet codice pronti per routing.py, MODEL_PRICING, writer_node per integrazioni Qwen 3.5. Usa tool per prezzi aggiornati e paper.

Il sistema nel branch `claude/analyze-software-features-5xwWs` è già molto avanzato, ma alla luce della letteratura 2024–2026 si possono introdurre **pattern di orchestrazione più frugali e modulari** (alla BudgetMLAgent/AgentNet/Agentic RAG) e **modelli Qwen 3.5** per ridurre drasticamente i costi senza sacrificare qualità, soprattutto nei preset economy/balanced.[^5_1][^5_2][^5_3][^5_4]

***

## Architettura: ottimizzazioni frontier

L’attuale architettura è un **StateGraph centralizzato** con 32 nodi reali, orchestrato da `build_graph()` in `src/graph/graph.py`, con `DocumentState` come unico contenitore tipizzato per tutto lo stato (outline, budget, jury, SHINE, RLM, human‑in‑the‑loop, ecc.). Questo è coerente con i pattern “central orchestrator” descritti nei survey su multi‑agent LLM e deep research, ma è esattamente il tipo di design che lavori recenti come AgentNet, SagaLLM e “LLM Multi‑Agent Systems: Challenges and Open Problems” indicano come **bottleneck di scalabilità e flessibilità**. In particolare, AgentNet mostra che passare da un orchestratore centrale fisso a un **DAG di agenti dinamico** riduce single point of failure, migliora adattabilità e consente routing basato su expertise locale, mantenendo comunque una struttura DAG controllabile.[^5_5][^5_3][^5_6][^5_7][^5_8][^5_9]

Per il tuo DRS non serve copiare la decentralizzazione estrema di AgentNet, ma puoi importare due idee chiave: **(1) sottografi riusabili, (2) stati modulari per “cluster” di agenti**. Oggi i loop “style_lint → style_fixer → metrics → budget → jury → aggregator → reflector/panel/oscillation” sono codificati inline in `build_graph`, con router separati ma nessun concetto di “sub‑workflow riusabile” (es. style loop, panel loop, oscillation loop). LangGraph supporta ormai bene la composizione di sottografi; un refactoring frontier e affidabile sarebbe: definire `build_style_loop_subgraph()`, `build_panel_loop_subgraph()`, `build_oscillation_subgraph()` che restituiscono ciascuno un piccolo `StateGraph` su un sotto‑TypedDict (es. `StyleState`, `PanelState`), e montarli nel grafo principale come nodi compositi. Questo riduce accoppiamento e permette di **riusare gli stessi loop** in altri prodotti (es. system di editing puro) senza copiare la logica.[^5_7][^5_9]

Sul fronte stato, la letteratura su sistemi multi‑agent falliti mostra che un singolo “mega‑stato” centrale favorisce **ambiguità di responsabilità, errori di serializzazione, e bug silenziosi al resume** — esattamente ciò che i commenti in `DocumentState` dicono di voler evitare. Un refactoring progressivo, ispirato a SagaLLM (che introduce agenti specializzati di context management e validation), sarebbe:[^5_10][^5_11][^5_8][^5_12]

- estrarre `ResearchState`, `WriterState`, `JuryState`, `BudgetState`, `HumanLoopState` come `TypedDict` separati e far sì che i nodi leggano/scrivano solo la loro “slice”, con funzioni helper di merge verso `DocumentState`.[^5_7]
- ridurre i campi “obbligatori” in `DocumentState` a quelli strettamente necessari per la serializzazione LangGraph (ID, status, outline, budget, approved_sections, shine/rlm flag), spostando tutto il resto in strutture nested opzionali con default solidi in `preflight_node`.

Infine, i survey su Agentic RAG e Deep Research Agents insistono che **molti benefici dei sistemi agentici si ottengono già con un forte single‑agent orchestrato**, usando pattern reflection/planning/tool‑use senza necessariamente moltiplicare agenti e loop. Per alcune fasi del tuo DRS (es. style_fixer + style_linter + part of reflector) è plausibile migrare da un pattern “multi‑nodo + multi‑agent” a un **single strong agent (es. Qwen3.5‑35B o Sonnet)** che esegue editing iterativo in un’unica chiamata controllata, riducendo latenza e complessità, come mostrato da sistemi deep‑research industriali (OpenAI DR, Gemini DR, Kimi‑Researcher) che usano pochi agenti forti con tool‑use invece di decine di ruoli micro‑specializzati.[^5_13][^5_14][^5_15][^5_1]

***

## Costi: tecniche frontier di riduzione

I prezzi 2026 mostrano un **delta enorme** tra modelli high‑end e Qwen 3.5: Qwen3.5‑9B costa ~0.10$/M input e 0.15$/M output, Qwen3.5‑35B‑A3B 0.25/2.00$/M, Qwen3.5 Flash 0.10/0.40$/M, mentre Claude 3.7 “Thinking Sonnet” arriva a 6$/M input e 30$/M output, e GPT‑4.5 resta a 75/150$/M. Questo significa che qualsiasi slot oggi mappato mentalmente a “Opus‑like 75$/M” o “top model” ha un ordine di grandezza di margine di ottimizzazione semplicemente spostandosi su Qwen3.5, soprattutto per preset economy/balanced.[^5_4]

Lavori come FrugalGPT e BudgetMLAgent mostrano strategie efficaci e **misurate**: BudgetMLAgent dimostra una riduzione del costo del 94.2% sostituendo un single‑agent GPT‑4 con una cascata multi‑LLM (Gemini + GPT‑4 solo come “ask‑the‑expert”) e ottiene anche un miglioramento di successo del 32.95% vs 22.72% su MLAgentBench. Il pattern è chiaro e affidabile:[^5_2][^5_16][^5_17]

- **profiling del task** → selezione di un base model low‑cost;
- **LLM cascade** → escalation al modello caro solo se certi controlli falliscono (formato errato, CSS sotto soglia, loop ripetuti);
- **ask‑the‑expert** limitato a poche chiamate controllate per run.

Traslato nel tuo DRS, significa:

- usare Qwen3.5‑9B/Flash come base writer per economy/balanced, con Sonnet/o3‑mini solo se il CSS scende sotto una soglia o se oscillation/panel loop non convergono dopo N iterazioni;[^5_4]
- usare Qwen3.5 Small (0.8B/2B/4B) per la maggioranza dei giudici (R/F/S), con un solo giudice “expert” su DeepSeek‑R1 o Sonnet che si attiva in cascata quando l’aggregator rileva conflitti seri o missing evidence;[^5_2][^5_4]
- usare Qwen3.5‑4B per compressione, reflector, post‑QA, dove il carico cognitivo è più di verifica/riassunto che di heavy reasoning.[^5_18][^5_19]

A queste strategie di “cascata di modelli” puoi sommare altre tecniche frontier ma già consolidate:

- **speculative decoding e batching** tramite vLLM per Qwen3.5 self‑hosted: riduce RTT per chiamata e consente di batchare sezioni in parallelo senza aumentare costo token.[^5_19][^5_20][^5_21]
- **KV cache quantization** su GPU (es. 4‑bit Q4_K_M per Qwen3.5‑35B) riducendo VRAM e permettendo batch più grandi, come mostrato nelle guide Unsloth/llama.cpp.[^5_20][^5_21]
- **tiered caching**: riuso più aggressivo dei blocchi di system prompt (regole di stile, rubriche jury, linee guida di verifica) non solo in `writer_node` ma anche in giudici e reflector, sfruttando cache_control Anthropic e caching custom per Qwen self‑host (YAML→prompt string memoization in Redis).[^5_22]

Con i prezzi Rival/PricePerToken, un writer premium Sonnet a 30$/M output vs Qwen3.5‑35B a 2$/M implica che spostare l’80% delle sezioni su Qwen3.5 e solo il 20% più difficile su Sonnet può dare **savings dell’ordine del 70–85%** sul budget writer, anche senza cambiare nulla nel numero di iterazioni. Se combini questo con un jury a base Qwen Small (0.15–0.40\$/M output) e solo un giudice premium sporadico, l’effetto complessivo può avvicinarsi al 90% di riduzione che BudgetMLAgent riporta rispetto a un single‑agent GPT‑4.[^5_16][^5_2][^5_4]

***

## Modelli alternativi: Qwen 3.5 + frontier

La famiglia Qwen 3.5 (0.8B, 2B, 4B, 9B, 35B‑A3B, 397B‑A17B, vari Flash/Plus/Max) offre un **ventaglio altamente granulare** di compromessi costo/qualità, con contesti fino a 1M token e API/non‑API a prezzi molto inferiori rispetto a Sonnet/o3. Ad esempio, Rival indica: Qwen3.5‑9B a 0.10$/M in e 0.15$/M out, Qwen3.5‑35B‑A3B a 0.25/2.00$/M, Qwen3.5 Flash a 0.10/0.40$/M, Qwen3.5 Plus (1M ctx) a 0.40/2.40$/M, Qwen3.5‑397B a 0.60/3.60$/M — tutti molto sotto Sonnet Thinking 6/30\$/M.[^5_23][^5_24][^5_25][^5_18][^5_4]

Accanto a Qwen, modelli come DeepSeek‑R1/R2 (reasoning a basso costo), Grok 3.5, Mistral Large 2.5 e Gemini 3 Flash offrono altri punti nel design space: high‑end reasoning low‑temperature (DeepSeek‑R1/R2, Grok) e throughput elevato a basso costo (Gemini Flash, Mistral Large) utili per ruoli specifici (panel altamente ragionanti, generazione di codice, verifica fattuale). Una strategia frontier ma affidabile è **combinare Qwen come backbone open‑source con 1–2 modelli chiusi premium** solo per decisioni critiche, in linea con la logica “ask‑the‑expert” di BudgetMLAgent.[^5_26][^5_27][^5_28][^5_29][^5_16][^5_2]

Una mappatura role→modello concreta da codificare in `routing.py` (estendendo `route_model`/`route_jury_slots`), coerente con la tua architettura e con i prezzi 2026, potrebbe essere:

```python
# src/llm/routing.py – mapping frontier (concettuale)
QWEN35_ROUTING = {
    "writer": {
        "economy":  "qwen/qwen3.5-9b-instruct",
        "balanced": "qwen/qwen3.5-35b-a3b",
        "premium":  "anthropic/claude-3.7-sonnet",  # solo se budget_regime lo consente
    },
    "researcher": {
        "economy":  "qwen/qwen3.5-4b",
        "balanced": "qwen/qwen3.5-9b",
        "premium":  "perplexity/sonar-pro",
    },
    "jury_r": {  # Reasoning judges
        "economy":  "qwen/qwen3.5-2b",
        "balanced": "qwen/qwen3.5-4b",
        "premium":  "deepseek/deepseek-r1",
    },
    "jury_f": {  # Factual judges
        "economy":  "qwen/qwen3.5-flash",
        "balanced": "qwen/qwen3.5-9b",
        "premium":  "google/gemini-3-flash",
    },
    "jury_s": {  # Style judges
        "economy":  "qwen/qwen3.5-0.8b",
        "balanced": "qwen/qwen3.5-2b",
        "premium":  "meta/llama-3.3-70b-instruct",
    },
    "reflector": {
        "economy":  "qwen/qwen3.5-4b",
        "balanced": "qwen/qwen3.5-9b",
        "premium":  "openai/o3-mini",
    },
}
```

e poi:

```python
def route_model(purpose: str, preset: str, allow_upgrade: bool = False) -> str:
    table = QWEN35_ROUTING.get(purpose, {})
    model = table.get(preset, table.get("balanced", "qwen/qwen3.5-4b"))
    # qui applichi la tua logica esistente di fallback laterale/verticale e RLM_ALLOW_TIER_UPGRADE
    return model
```

In `MODEL_PRICING` (`src/llm/pricing.py`) dovresti aggiungere voci corrispondenti ai modelli Qwen3.5 che userai effettivamente, allineandole ai prezzi Rival/OpenRouter (es. 0.10/0.15, 0.25/2.00, 0.10/0.40), così che `cost_usd()` rifletta la realtà e il `budget_estimator_node` smetta di sovrastimare i costi di 10× quando in realtà usi Qwen e non Opus.[^5_4]

***

## Integrazione Qwen 3.5 con SHINE e RLM

L’attuale `writer_node` sceglie tra tre path: SHINE LoRA (se `shine_active` e `_SHINE_SERVING_URL` non vuoto), RLM (se `rlm_mode=True`) e path standard, usando `route_model("writer", preset)` per decidere il modello e passando a SHINE un server vLLM/AIBrix locale. La combinazione con Qwen 3.5 apre due nuove strategie frontier:

1. **Preset economy/balanced senza SHINE/RLM**: Qwen3.5‑9B/35B con contesti 262k–1M token permette spesso di tenere l’intero corpus (o quasi) nel contesto standard, soprattutto se combini Agentic RAG + compressione soft, riducendo la necessità di SHINE e RLM per la maggior parte dei documenti. In questi preset puoi forzare `shine_active=False` e `rlm_mode=False` per default e usare SHINE solo se `total_sections` * `target_words` supera una certa soglia (es. >100k parole).[^5_30][^5_31][^5_1][^5_18][^5_19]
2. **Preset premium con SHINE + Qwen3.5‑Max/397B**: per documenti veramente grandi (o clienti di fascia alta), puoi usare SHINE per encodare sezioni in LoRA adapters e caricarle in un server Qwen3.5‑Max/397B (Flash/Plus), sfruttando il contesto gigantesco e l’hypernetwork per ridurre latenza e costo di generazione rispetto a modelli closed, mantenendo comunque qualità top.[^5_31][^5_30][^5_4]

Nel codice, l’unica modifica concettuale è nel routing:

```python
# in writer_node, quando costruisci rlm = get_rlm_client(...)
rlm = get_rlm_client(
    model=route_model("writer_rlm", preset),  # es. qwen3.5 Max Thinking
    child_model=route_model("writer_child", "economy"),  # es. qwen3.5-9b
    state=state,
)
```

e nel modo in cui `context_compressor` decide se bypassarsi (oggi lo fa se `rlm_mode=True`); puoi estendere la condizione a `if rlm_mode or use_qwen_long_context:` basata su preset+doc size.

***

## Confronto con stato dell’arte 2024–2026

I survey “Agentic RAG” e “Deep Research Agents” confermano che la tua pipeline pianificazione → web exploration → synth/compressione → generazione → evaluation/QA è esattamente la struttura di riferimento per sistemi di deep research moderni. La presenza di moduli dedicati per budget, SHINE, RLM, jury eterogeneo e human‑in‑the‑loop ti colloca già sullo stesso piano concettuale dei sistemi DR industriali (OpenAI DR, Gemini DR, Kimi‑Researcher, AutoGLM Rumination) che orchestrano pochi agenti forti con tool‑use avanzato.[^5_14][^5_15][^5_1][^5_13]

Tuttavia, lavori come “Why Do Multi‑Agent LLM Systems Fail?” e “LLM Multi‑Agent Systems: Challenges and Open Problems” mostrano che la maggioranza dei MAS attuali **non supera in modo robusto un single‑agent forte**, mentre introduce molte nuove failure modes (specification ambiguities, organizational breakdowns, inter‑agent misalignment, verification gaps). Il tuo grafo, con numerosi loop (gap analysis, style loop, panel self‑loop, oscillation, await_human, post‑QA) e un DocumentState monolitico, è esattamente il tipo di architettura che questi lavori mettono in guardia: rischia di accumulare failure modes a livello sistemico se non strettamente controllata con metriche e ablation.[^5_11][^5_8][^5_12][^5_10]

BudgetMLAgent fornisce un caso studio quantitativo molto chiaro: **una cascata multi‑LLM ben progettata con ask‑the‑expert può ridurre costi del 94,2% e aumentare la success rate rispetto a un single‑agent GPT‑4**, ma solo perché la struttura di cascata, profiling e retrieval di esperienze passate è curata maniacalmente. Il tuo design ha gli ingredienti (budget estimator, regime/preset, routing multi‑modello, RLM/SHINE, jury eterogeneo), ma manca ancora un layer di **profiling dinamico + cascata esplicita** che colleghi questi strumenti in una policy data‑driven. Implementare una “BudgetDRSAgent” interna, ispirata a BudgetMLAgent, che usi `BudgetState`, CSS e oscillation metrics per decidere quando escalare a modelli costosi renderebbe il tuo sistema molto più allineato allo stato dell’arte.[^5_16][^5_2]

***

## Punti di forza e criticità aggiornati (focus Qwen 3.5/SHINE)

**Punti di forza aggiornati**

1. **Infrastruttura di costo e budget di livello industriale**: `MODEL_PRICING`, `cost_usd`, `BudgetState`, `budget_estimator_node`, `RLMBudgetController` e metriche Prometheus ti danno già una telemetria di costo che lavori come BudgetMLAgent e FrugalGPT auspicano ma non sempre implementano in modo così unificato.[^5_17][^5_2]
2. **Integrazione SHINE avanzata**: `context_compressor` che encode sezioni in LoRA adapters con SHINE, mantenendo solo LBC nel contesto, è perfettamente in linea con i lavori più recenti sulla compressione param‑centric (SHINE 2026). Con Qwen 3.5 a 1M ctx, puoi combinare efficacemente LoRA+long context per minimizzare latenza e costo.[^5_30][^5_31]
3. **Architettura LangGraph già modulare a livello di nodi**: anche se non ancora a sottografi riusabili, la chiara separazione di nodi funzionali (researcher, citation pipeline, writer, jury, aggregator, reflector, panel, coherence, post‑QA) è esattamente la modularità che i survey su Deep Research e Agentic RAG raccomandano.[^5_1][^5_13][^5_14]
4. **Potenziale di integrazione Qwen 3.5**: con i prezzi 0.10–0.40\$/M token e performance dimostrate su reasoning/coding, Qwen 3.5 è un “fit naturale” come backbone open‑source per i preset economy/balanced, riducendo enormemente il rischio di lock‑in e il TCO.[^5_24][^5_25][^5_18][^5_23][^5_4]

**Criticità (aggiornate, con priorità)**

- **Alta priorità – Mancanza di cascata esplicita alla BudgetMLAgent**: oggi la scelta del modello è principalmente una funzione statica di `purpose`+`preset`, con alcuni guardrail (no tier upgrade senza env flag) ma senza una policy di cascata dinamica “low‑cost → high‑cost on failure” come in BudgetMLAgent/FrugalGPT. Questo significa che anche con Qwen 3.5 integrato rischi di usare modelli troppo forti (o troppo deboli) in modo uniforme, perdendo gran parte dei potenziali savings.[^5_17][^5_2][^5_16]
- **Alta priorità – DocumentState monolitico vs failure taxonomy dei MAS**: il singolo TypedDict gigante è in tensione diretta con le raccomandazioni di “Why Do Multi‑Agent LLM Systems Fail?”, che indica organizational breakdowns e specification ambiguities come ~40%+ delle failure modes. Ogni nuovo campo o nodo aumenta il rischio di stati incoerenti e bug silenziosi, soprattutto al resume da checkpoint.[^5_12][^5_10][^5_11]
- **Media priorità – SHINE/RLM attivati troppo grossolanamente**: al momento, `rlm_mode` e `shine_active` sono flag globali attivati in preflight secondo semplici condizioni (preset e dimensione corpus), non da metriche dinamiche (es. oscillation, CSS persistenti, budget residuo). La letteratura su DR Agents e Agentic RAG suggerisce di attivare pattern di reasoning costosi solo quando i pattern più economici (single‑pass, cascata low‑cost) falliscono ripetutamente secondo metriche chiare.[^5_15][^5_13][^5_14]
- **Media priorità – Nessun harness di ablation per path multi‑agent complessi**: dati i risultati misti dei multi‑agent frameworks (spesso nessun vantaggio robusto vs single‑agent forte), mantenere panel, oscillation, targeted research e style loop senza misurarne il contributo marginale in termini di “quality per dollar” è rischioso. Ti serve una suite di benchmark interni alla DeepResearch Agents Survey per quantificare cosa tenere e cosa spegnere.[^5_32][^5_8][^5_11]
- **Bassa‑media priorità – Assenza di protocolli di comunicazione standardizzati tra nodi/“agenti”**: lavori come Agora e i blog tecnici su failure dei MAS sottolineano che la mancanza di schemi di messaggio standard porta a mis‑allineamento e bug silenziosi. Nel tuo caso, i passaggi tra nodi usano solo `DocumentState` condiviso; introdurre mini‑schemi (es. `WriterRequest`, `JuryInput`, `ReflectorInput`) e validatori semplici potrebbe ridurre errori di interpretazione tra fasi.[^5_33][^5_34][^5_35]

***

In conclusione, le tue fondamenta architetturali sono in linea con i migliori lavori 2024–2026 su deep research e Agentic RAG, ma per sfruttare davvero Qwen 3.5, SHINE e RLM in chiave “frontier ma affidabile” devi: (1) introdurre una politica di **cascata multi‑modello alla BudgetMLAgent** codificata nel routing e nel budget controller, (2) **modularizzare lo stato e i loop del grafo** per ridurre failure modes sistemiche, e (3) pilotare SHINE/RLM/Qwen3.5 in modo data‑driven sulla base di CSS, oscillazioni e budget, non solo di preset statici.
<span style="display:none">[^5_36][^5_37][^5_38][^5_39][^5_40][^5_41][^5_42][^5_43][^5_44][^5_45][^5_46][^5_47][^5_48][^5_49][^5_50][^5_51][^5_52][^5_53][^5_54][^5_55][^5_56][^5_57][^5_58][^5_59][^5_60][^5_61][^5_62][^5_63][^5_64][^5_65][^5_66][^5_67][^5_68][^5_69]</span>

<div align="center">⁂</div>

[^5_1]: https://arxiv.org/html/2501.09136v1

[^5_2]: https://www.arxiv.org/abs/2411.07464

[^5_3]: https://arxiv.org/abs/2504.00587v1

[^5_4]: https://www.rival.tips/prices

[^5_5]: https://arxiv.org/abs/2504.00587

[^5_6]: https://papers.cool/venue/tXqLxHlb8Z@OpenReview

[^5_7]: http://arxiv.org/pdf/2503.11951.pdf

[^5_8]: https://arxiv.org/pdf/2402.03578.pdf

[^5_9]: https://arxiv.org/abs/2601.03328

[^5_10]: https://arxiv.org/abs/2503.13657

[^5_11]: https://arxiv.org/pdf/2503.13657.pdf

[^5_12]: https://huggingface.co/papers/2503.13657

[^5_13]: https://arxiv.org/abs/2501.09136

[^5_14]: https://arxiv.org/pdf/2508.12752.pdf

[^5_15]: https://arxiv.org/html/2506.18096v2

[^5_16]: https://paperswithcode.com/paper/budgetmlagent-a-cost-effective-llm-multi

[^5_17]: https://arxiv.org/pdf/2305.05176.pdf

[^5_18]: https://huggingface.co/collections/unsloth/qwen35

[^5_19]: https://arxiv.org/pdf/2501.15383.pdf

[^5_20]: https://unsloth.ai/docs/models/qwen3.5

[^5_21]: https://www.datacamp.com/tutorial/run-qwen-3-5-locally

[^5_22]: https://www.anthropic.com/news/claude-3-7-sonnet

[^5_23]: https://huggingface.co/Qwen/Qwen3.5-35B-A3B-Base

[^5_24]: https://huggingface.co/Qwen/Qwen3.5-35B-A3B

[^5_25]: https://huggingface.co/Qwen/Qwen3.5-0.8B

[^5_26]: https://pricepertoken.com/pricing-page/model/qwen-qwen3-vl-32b-instruct

[^5_27]: https://pricepertoken.com

[^5_28]: https://www.getpassionfruit.com/blog/comparing-claude-3-7-sonnet-claude-3-5-sonnet-openai-o3-mini-deepseek-r1-and-grok-3-beta

[^5_29]: https://cloudprice.net/models/openrouter/qwen/qwen3-coder-plus

[^5_30]: https://arxiv.org/abs/2602.06358

[^5_31]: https://arxiv.org/html/2602.06358v1

[^5_32]: https://arxiv.org/html/2410.22932

[^5_33]: http://arxiv.org/pdf/2410.11905.pdf

[^5_34]: https://arxiv.org/pdf/2402.01108.pdf

[^5_35]: https://orq.ai/blog/why-do-multi-agent-llm-systems-fail

[^5_36]: https://arxiv.org/abs/2512.00614

[^5_37]: https://s-rsa.com/index.php/agi/article/view/15417

[^5_38]: https://arxiv.org/html/2504.00587v1

[^5_39]: http://arxiv.org/pdf/2410.15048.pdf

[^5_40]: https://arxiv.org/pdf/2308.10721.pdf

[^5_41]: http://arxiv.org/pdf/2312.17025.pdf

[^5_42]: http://arxiv.org/pdf/2406.14228.pdf

[^5_43]: https://arxiv.org/pdf/2309.15943.pdf

[^5_44]: https://arxiv.org/html/2502.05453

[^5_45]: https://openreview.net/forum?id=tXqLxHlb8Z

[^5_46]: https://neurips.cc/virtual/2025/poster/115584

[^5_47]: https://github.com/zoe-yyx/AgentNet

[^5_48]: https://www.themoonlight.io/en/review/budgetmlagent-a-cost-effective-llm-multi-agent-system-for-automating-machine-learning-tasks

[^5_49]: https://openreview.net/pdf?id=tXqLxHlb8Z

[^5_50]: https://arxiv.deeppaper.ai/papers/2501.09136v3

[^5_51]: https://arxiv.org/abs/2411.07464

[^5_52]: https://arxiv.org/abs/2511.07784

[^5_53]: https://arxiv.org/abs/2506.06175

[^5_54]: https://arxiv.org/abs/2506.20737

[^5_55]: https://arxiv.org/abs/2512.02682

[^5_56]: https://aclanthology.org/2025.emnlp-industry.83

[^5_57]: https://arxiv.org/abs/2512.07785

[^5_58]: https://arxiv.org/abs/2511.11012

[^5_59]: https://arxiv.org/abs/2506.02739

[^5_60]: https://arxiv.org/abs/2502.20748

[^5_61]: https://arxiv.org/pdf/2404.16698.pdf

[^5_62]: https://arxiv.org/pdf/2408.09955.pdf

[^5_63]: https://openreview.net/forum?id=fAjbYBmonr

[^5_64]: https://neurips.cc/virtual/2025/poster/121528

[^5_65]: https://arxiv.org/html/2508.12752v1

[^5_66]: https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them

[^5_67]: https://iclr.cc/virtual/2025/33314

[^5_68]: https://www.infodocket.com/2025/08/19/research-paper-preprint-deep-research-a-survey-of-autonomous-research-agents/

[^5_69]: https://openrouter.ai/qwen/qwen3.5-plus-02-15

