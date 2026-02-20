<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Analisi Critica — Deep Research System v1.0

Il documento è architetturalmente solido nella struttura macro e nei principi di design, ma presenta **lacune critiche non negoziabili**, lacune di design significative e intere aree funzionali completamente assenti. L'analisi segue in ordine di gravità.[^1]

***

## Lacune Critiche (bloccanti)

### Il CSS non è mai definito

Il documento usa il CSS (Consensus Strength Score) come criterio di routing centrale — `CSS < 0.50` attiva il Panel Discussion, l'oscillazione è definita come mancanza di variazione del CSS — ma **non ne viene mai fornita la formula matematica**.  È un numero aggregato? Media pesata dei voti dei 9 giudici? Entropia sui verdetti? Coefficiente di variazione? Senza questa definizione, l'Aggregatore non può essere implementato. La soglia `0.50` è arbitraria o empiricamente motivata? Proposta di integrazione:[^1]

> Definire CSS come $\text{CSS} = 1 - \frac{\sigma(\mathbf{v})}{\sigma_{\max}}$ dove $\mathbf{v}$ è il vettore dei voti binari dei 9 giudici e $\sigma_{\max} = 0.5$. Aggiungere una sezione dedicata con formula, range $[0,1]$, significato semantico dei valori estremi e derivazione empirica della soglia.

### Nessuna stima economica

Il sistema invoca potenzialmente, per ogni iterazione di ogni sezione: 1 Writer (`claude-opus-4-5`, il più costoso), 9 giudici paralleli (inclusi `o3`, `gemini-2.5-pro`, `sonar-pro`), 1 Reflector (`o3`).  Per un documento da 10.000 parole con 8 sezioni e una media conservativa di 3 iterazioni per sezione, si parla di **decine di milioni di token** e costi potenzialmente nell'ordine delle centinaia di dollari per singolo documento. Il documento non stima né il costo medio né il worst case, non prevede un budget cap configurabile, non analizza il trade-off costo/qualità. Senza questa analisi il sistema è indefinito per uso enterprise.[^1]

### Resilienza agli errori di rete: assente

Il documento non menziona mai cosa succede se: un endpoint OpenRouter restituisce 500, una chiamata a CrossRef va in timeout, il DOI resolver è temporaneamente down, o un modello viene deprecato durante un'esecuzione lunga.  Non c'è retry logic, nessun circuit breaker, nessun fallback modello a livello di singola chiamata. Per un sistema che può girare ore su documenti lunghi, l'assenza di fault tolerance è un blocco alla produzione.[^1]

### Persistenza e recovery: non specificate

LangGraph fornisce checkpointing, ma il documento non specifica dove viene persistito lo stato (Redis? PostgreSQL? filesystem?), come si gestisce un crash a metà esecuzione, se una sezione approvata può essere recuperata dopo riavvio.  Un processo multi-ora che non può ripartire dall'ultimo checkpoint è inaccettabile in produzione.[^1]

***

## Lacune di Design Significative

### La compressione del contesto è un agente fantasma

Il principio "Contesto accumulato" descrive una compressione progressiva delle sezioni lontane ma **nessun agente è assegnato a questo task** — non esiste un Compressor nel diagramma, non esiste una specifica del meccanismo, non esiste una scelta del modello.  Una summarization lossy mal implementata è la causa principale di incoerenze narrative nei documenti lunghi. Proposta: aggiungere un agente **Compressor** con ruolo, modello (un modello leggero è sufficiente, es. `qwen3-7b`) e strategia esplicita (es. extractive per le sezioni 3-5 più lontane, abstractive per quelle ancora più distanti).[^1]

### Le sezioni approvate sono immutabili: problema con contraddizioni tardive

Il principio di granularità sezione-per-sezione afferma che "una sezione approvata è immutabile".  Ma cosa succede se la sezione 7 confuta fattualmente un'affermazione della sezione 2, già approvata? Il sistema attuale non ha meccanismo di **backpropagation della contraddizione**. I giudici Reasoning controllano la coerenza con le sezioni precedenti, ma se una nuova fonte (scoperta nella sezione 7) smentisce un dato nella sezione 2, non esiste percorso di correzione. Proposta: introdurre un **Coherence Guard** che, prima dell'approvazione definitiva di ogni sezione, esegue un confronto specifico dei nuovi claim fattuali con quelli delle sezioni già approvate, con flag di contraddizione escalabile all'umano.[^1]

### Panel Discussion incompleta

La sezione 8 descrive una "seconda tornata" dopo il Panel Discussion, ma non specifica: quante tornate massime sono permesse, cosa succede se dopo la seconda tornata il CSS è ancora `< 0.50`, chi gestisce tecnicamente l'anonimizzazione dei commenti tra i giudici, se il log della discussione viene archiviato.  Il meccanismo è descritto in termini narrativi ma non come specifica implementativa.[^1]

### Outline fisso dopo l'approvazione

La Fase A produce un outline che, una volta approvato, è **irreversibile**.  Non esiste meccanismo per rilevare che una sezione dell'outline, in fase di produzione, si riveli troppo ampia (necessita di splitting), troppo stretta o non allineata con le fonti effettivamente disponibili. Proposta: permettere al sistema di proporre all'umano modifiche strutturali all'outline durante la produzione, con una flag di **outline revision request** attivabile dal Researcher quando la disponibilità di fonti è significativamente divergente dalle aspettative del Planner.[^1]

***

## Aree Funzionali Completamente Assenti

### Sicurezza e privacy

Il documento non contiene una singola riga su sicurezza.  Il topic dell'utente — potenzialmente riservato — viene inviato a 12+ modelli su infrastrutture diverse (OpenAI, Anthropic, Google, Alibaba, Mistral, Meta, Perplexity). Mancano:[^1]

- Politica di data retention sulle API (OpenRouter logs?)
- Gestione sicura delle API key (vault, rotazione)
- Input sanitization contro prompt injection
- GDPR compliance per contesti europei
- Opzione per routing esclusivo su modelli self-hosted/on-premise


### Monitoring e observability

Nessuna menzione di logging strutturato, metriche di sistema, distributed tracing o alerting.  Per un sistema multi-agente con esecuzioni lunghe, servono almeno:[^1]

- **Metriche operative**: latenza per agente, costo cumulativo in real-time, tasso di fail per mini-giuria, distribuzione iterazioni per sezione
- **Tracing**: ogni chiamata LLM deve avere un trace ID per debug
- **Dashboard**: stato corrente dell'esecuzione, progress per sezione
- **Alert**: oscillazione imminente, costo soglia superato, errori ripetuti


### Testing strategy

Il documento è un'architettura senza alcun riferimento a come si testa il sistema.  Mancano completamente: unit test per i moduli deterministici (Citation Manager, Citation Verifier HTTP, Publisher), integration test per il loop sezione-per-sezione con mock LLM, regression test per verificare che la modifica di un prompt non degradi la qualità, benchmark di qualità dell'output finale comparato con e senza giuria.[^1]

### Deployment e infrastruttura

Nessuna specifica su: containerizzazione (Docker/Kubernetes?), scalabilità orizzontale, gestione della coda per esecuzioni multiple concorrenti, rate limiting verso le API dei provider, ambienti (dev/staging/prod).[^1]

### Formato di output limitato

Il Publisher produce esclusivamente DOCX.  Mancano: PDF (il formato di distribuzione più comune per documenti formali), Markdown (per uso programmatico e integrazione con altri tool), LaTeX (per contesti accademici), HTML (per pubblicazione web), e un formato JSON strutturato per uso API. La dipendenza da un singolo formato di output è una limitazione architetturale che non ha giustificazione.[^1]

### Feedback loop post-produzione

Il sistema non ha alcun meccanismo per raccogliere feedback sulla qualità del documento finale da parte dell'utente.  Questo significa che non ci sono dati per migliorare i prompt nel tempo, identificare quali pattern di stile sistematicamente insoddisfano l'utente, o calibrare empiricamente le soglie CSS. Un sistema di produzione deve avere un **feedback loop chiuso**.[^1]

***

## Lacune Minori ma Significative

### Reliability score contestuale vs fisso

I reliability score sono fissi per tipo di fonte (es. Twitter/X: 0.20–0.40) ma nella realtà dipendono dal contesto.  Un thread di un ricercatore verificato su X che presenta risultati preliminari di uno studio può essere più affidabile di un articolo .gov datato. Il sistema dovrebbe permettere override contestuale del reliability score.[^1]

### Multi-linguismo della giuria Style

La mini-giuria Style include `mistral-large-2411` per il "bias europeo" ma non affronta esplicitamente il caso in cui la lingua di output configurata non sia l'inglese.  Per output in italiano, tedesco, cinese o arabo, la composizione ottimale della giuria Style è diversa. I forbidden patterns devono essere definiti in lingua target. Proposta: una configurazione di giuria Style per lingua, con modelli ottimali per ogni lingua.[^1]

### Fonti senza URL (libri, monografie)

Il Citation Verifier verifica `HTTP 200` e DOI, ma libri e monografie (ISBN) non hanno URL verificabile.  Il sistema non menziona come gestire citazioni di libri, capitoli di libro, atti di conferenza senza DOI o materiale d'archivio.[^1]

### Modelli potenzialmente non esistenti

Il documento cita `anthropic/claude-opus-4-5` e `openai/gpt-4.5` che, alla data del documento (Febbraio 2026), hanno nomenclatura non verificabile nelle release note ufficiali.  Dato che il documento stesso riconosce che "il panorama dei modelli evolve rapidamente", una sezione dedicata alla **model verification procedure** (come validare che i modelli dichiarati in YAML esistano effettivamente su OpenRouter prima dell'esecuzione) è necessaria.[^1]

***

## Integrazioni Proposte — Riepilogo Strutturato

| Area | Integrazione | Priorità |
| :-- | :-- | :-- |
| Aggregatore | Definizione matematica completa del CSS con formula, range e derivazione della soglia | 🔴 Critica |
| Economia | Cost estimator pre-esecuzione + budget cap + report costo per sessione | 🔴 Critica |
| Resilienza | Retry logic, circuit breaker, fallback modello per ogni slot | 🔴 Critica |
| Persistenza | Specifica storage (es. PostgreSQL + Redis), recovery da checkpoint | 🔴 Critica |
| Contesto | Agente Compressor dedicato con modello, strategia e specifica | 🟠 Alta |
| Coerenza | Coherence Guard per contraddizioni inter-sezione | 🟠 Alta |
| Outline | Meccanismo di outline revision request durante produzione | 🟠 Alta |
| Panel Discussion | Specifica completa: max tornate, gestione anonimato, archivio log | 🟠 Alta |
| Sicurezza | Data handling policy, API key vault, input sanitization, GDPR | 🟠 Alta |
| Output | Aggiunta PDF, Markdown, LaTeX, HTML, JSON al Publisher | 🟡 Media |
| Monitoring | Logging strutturato, metriche operative, dashboard, alerting | 🟡 Media |
| Testing | Unit, integration, regression test strategy + benchmark qualità | 🟡 Media |
| Deployment | Containerizzazione, queue management, rate limiting | 🟡 Media |
| Feedback | Loop post-produzione per calibrazione prompt e soglie | 🟡 Media |
| Multi-lingua | Composizione giuria Style per lingua configurata | 🟡 Media |
| Citazioni | Gestione ISBN/libri/archivio senza URL | 🟢 Bassa |
| Reliability | Override contestuale reliability score | 🟢 Bassa |
| Modelli | Model verification procedure pre-esecuzione da YAML | 🟢 Bassa |

Il documento stabilisce un'architettura concettualmente valida e differenziante (il Minority Veto e la diversità epistemica della giuria sono scelte solide e ben motivate), ma nella sua forma attuale è un **documento di visione**, non ancora una specifica implementativa. La distanza tra i due livelli è significativa e deve essere colmata prima di poter parlare di v1.0 producibile.

<div align="center">⁂</div>

[^1]: Deep-Research-System.md

