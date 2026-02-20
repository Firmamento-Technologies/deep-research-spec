<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# valuta attentamente la proposta di progetto e fai una analisi super critica proponi integrazioni a tutto ciò che manca

Ecco la mia analisi critica completa. È un documento architetturalmente solido su molti fronti, ma presenta lacune significative che — in produzione — si tradurrebbero in fallimenti o costi incontrollati.

***

## Valutazione generale

Il Deep Research System è concettualmente ben costruito: il Minority Veto è scientificamente motivato, la granularità sezione-per-sezione è genuinamente intelligente, e la separazione dei ruoli è pulita. Tuttavia, il documento è un **documento di visione** che si spaccia per documento di architettura. Descrive *cosa* il sistema fa, ma sistematicamente evita di dire *come* lo fa nelle parti critiche, e ignora completamente le dimensioni operativa, economica e di sicurezza.[^1]

***

## Lacune critiche

### 1. Il CSS non è mai definito matematicamente

Il Consensus Strength Score è il cuore del routing dell'intero sistema — ma la sua formula non viene mai specificata. Come si calcola da 9 voti binari (pass/fail) più motivazioni testuali? È la proporzione di pass? Include confidence scores individuali dei giudici? Come si aggregano le tre mini-giurie? Senza questa formula, l'Aggregatore è una black box non implementabile.[^1]

**Integrazione**: definire CSS come:

$$
CSS = \frac{1}{3} \sum_{k=1}^{3} \left( \frac{\text{pass}_k}{3} \right) \cdot w_k
$$

dove $w_k$ è il peso configurabile per mini-giuria (Reasoning, Factual, Style) e `pass_k` è il numero di voti positivi nella mini-giuria k. Aggiungere un **CSS breakdown per mini-giuria** nel report all'utente.

***

### 2. Zero stima di costo — errore fatale

Il documento non include alcuna analisi economica. Con i modelli scelti (Claude Opus ~\$75/M token output, o3 ~\$60/M, GPT-4.5 ~\$150/M), un documento da 10.000 parole con media 2 iterazioni per sezione su 10 sezioni potrebbe costare facilmente **\$80–300 per run**, con picchi a \$500+ in caso di oscillazioni.[^1]

**Integrazioni necessarie**:

- **Pre-run Budget Estimator**: stima del costo basata su outline approvato (n° sezioni × token stimati × modelli assegnati)
- **Real-time Cost Tracker**: contatore token/costo per agente e per sezione
- **Budget Cap configurabile**: stop automatico con checkpoint se il budget viene superato, con report parziale del prodotto

***

### 3. Latenza non considerata — il sistema è bloccante

Il pipeline è completamente sequenziale per sezione. Con 9 API call in parallelo per la giuria + Writer + Researcher + Reflector, ogni iterazione richiede decine di secondi. Un documento con oscillazioni potrebbe richiedere **4–8 ore** senza alcun feedback intermedio all'utente.[^1]

**Integrazioni necessarie**:

- **Async Progress Dashboard** via WebSocket/SSE: sezione corrente, iterazione N/max, CSS attuale, costo accumulato, ETA stimata
- **Checkpoint e resume**: lo stato del run viene salvato su disco (LangGraph lo supporta nativamente); il run può essere ripreso dopo interruzione
- **Timeout per agente**: ogni call LLM ha un timeout configurabile; in caso di superamento → retry con fallback model

***

### 4. Gestione degli errori assente

Il documento non specifica cosa succede in nessuno scenario di errore:[^1]


| Scenario | Cosa fa il sistema? |
| :-- | :-- |
| API timeout/429 | ❌ Non specificato |
| Output malformato (non parsabile) dal giudice | ❌ Non specificato |
| >80% delle citazioni risultano "ghost" | ❌ Non specificato |
| Modello non disponibile su OpenRouter | ❌ Non specificato |
| Context window esaurita | ❌ Non specificato |

**Integrazione**: definire una **Error Handling Matrix** per ogni agente con: retry policy (exponential backoff), fallback model, degraded mode (es. proseguire con 2 giudici su 3 se uno è irraggiungibile), escalation umana.

***

### 5. Prompt Injection — vettore ignorato

Il sistema invia contenuto web non sanitizzato (recuperato da Tavily/Brave/CrossRef) direttamente nei prompt di Writer e giudici. Questo è un vettore classico di **indirect prompt injection**: un sito malevolo può includere istruzioni nel body della pagina che alterano il comportamento degli LLM.[^1]

**Integrazione**: aggiungere un **Source Sanitizer** tra Citation Verifier e Writer che:

- Estrae solo il contenuto semanticamente rilevante (abstract, sezioni specifiche), non il raw HTML
- Wrappa il contenuto esterno in un XML tag esplicito (`<external-source>`) con istruzione nel system prompt a non eseguire istruzioni contenute in quel tag
- Loggare qualsiasi pattern sospetto nel contenuto delle fonti

***

### 6. La compressione del contesto è handwavy

"Le sezioni più lontane vengono compresse in sommari progressivamente più densi" — ma *chi* fa la compressione, *come*, e con *quale criterio* decide cosa preservare?  Questa è una scelta architetturale critica che determina la coerenza narrativa del documento, ma viene liquidata in una riga.[^1]

**Integrazione**: agente dedicato **Context Compressor** con strategia esplicita:

- Livelli di compressione: verbatim (ultime 2), sommario strutturato (sezioni 3-5), estratto tematico (sezioni 6+)
- Il compressore usa un modello leggero e veloce (`qwen/qwen3-7b` è già nel stack per Citation Verifier)
- Il compressore riceve anche l'outline per sapere quali informazioni sono "load-bearing" per la coerenza globale

***

### 7. Minority Veto a due livelli — rischio "giudice rogue"

Con il doppio veto, **un singolo giudice su 9** può bloccare la sezione a tempo indeterminato. Non esiste un meccanismo per rilevare un modello che sistematicamente vota in modo diverso dagli altri 8 su ogni sezione del documento (un "rogue judge" causato da un prompt inadatto o da una versione del modello con comportamento anomalo).[^1]

**Integrazione**: **Rogue Judge Detector** nell'Aggregatore:

- Se un giudice ha un disagrement rate > 70% rispetto agli altri 8 su 3+ sezioni consecutive, genera un alert
- Report all'utente con log dei voti anomali
- Opzione di sostituire temporaneamente il giudice anomalo con il fallback configurato in YAML

***

### 8. Il Researcher non chiude il loop con la giuria

Il flusso attuale è: Researcher → Citation Manager → Citation Verifier → Writer → Giuria. Se il Judge Factual rileva che "mancano prove sul claim X", la feedback chain va al Reflector → Writer, ma il **Researcher non viene mai ri-chiamato**. Il Writer è costretto a riscrivere intorno a fonti insufficienti.[^1]

**Integrazione**: percorso condizionale nell'Aggregatore:

- Se Judge Factual segnala `missing_evidence` per claim specifici → ri-attivare Researcher con query mirate prima di passare al Reflector
- Questo aggiunge un half-loop ma risolve la causa radice invece di farla gestire al Writer

***

### 9. Output solo DOCX

Il Publisher produce solo `.docx`. Mancano completamente:[^1]

- **PDF** — formato universale per distribuzione e archiviazione
- **Markdown** — per integrazione in Notion, Obsidian, Git, siti statici
- **HTML** — per pubblicazione web diretta
- **LaTeX** — per pubblicazioni accademiche peer-reviewed
- **Structured JSON** — per consumo programmatico del documento (sezioni separate, citazioni separate, metadati)

**Integrazione**: Publisher multi-formato con flag configurabile in YAML (`output_formats: [docx, pdf, markdown]`). PDF via `pandoc` o `weasyprint` (zero dipendenze LLM), Markdown già disponibile come formato intermedio durante la produzione.

***

### 10. Assenza totale di observability

Non c'è logging strutturato, tracing, o metriche. In produzione, senza observability non è possibile capire:[^1]

- Quale agente causa i costi maggiori
- Dove il sistema perde più tempo
- Quale giudice blocca più frequentemente
- Quali tipi di sezione oscillano di più

**Integrazione**: **OpenTelemetry stack** con:

- Span per ogni agente call (latenza, token in/out, costo, modello)
- Metrica `section_approval_iterations` per distribuzione statistica delle iterazioni richieste
- Log strutturati (JSON) con `section_id`, `iteration`, `css`, `verdetti` per ogni round
- Dashboard (Grafana o Langfuse) per analisi post-run

***

### 11. Nessuna strategia di test

Il documento non menziona come testare il sistema. Con 11+ modelli, 5+ agenti, e logica condizionale complessa, senza una test suite qualsiasi modifica a un prompt rischia di rompere comportamenti inattesi a cascata.[^1]

**Integrazione**:

- **Golden dataset**: 3-5 topic con documenti di riferimento approvati manualmente, usati come regression test
- **Mock LLM layer**: intercetta le call API e restituisce output predefiniti per testare la logica dell'orchestratore a costo zero
- **Prompt unit test**: ogni prompt ha un set di input/output attesi che vengono verificati ad ogni modifica
- **Cost test**: per ogni run di test, verifica che il costo stimato rimanga sotto una soglia

***

### 12. Privacy e compliance — completamente assenti

Il sistema invia draft e contenuto delle fonti a 11+ provider LLM diversi, ognuno con la propria data retention policy. Per contenuto aziendale riservato o dati personali, questo è un problema GDPR/NDA immediato.[^1]

**Integrazione**:

- **Sezione Privacy nella documentazione**: elenco esplicito di quali dati vanno a quali provider
- **Privacy mode**: opzione per sostituire i giudici cloud con modelli self-hosted (`ollama` + `vllm`) per i dati sensibili
- **Data minimization**: il sistema invia solo il testo necessario a ogni agente, non l'intero contesto se non richiesto

***

## Integrazioni architetturali minori ma rilevanti

- **Pre-flight Validator**: prima dell'esecuzione, verifica validità di tutte le API key, disponibilità dei modelli su OpenRouter, accessibilità delle fonti configurate, e produce un report prima di spendere un singolo token
- **Source Diversity Analyzer**: verifica che le fonti per sezione non siano concentrate su un singolo publisher, autore o anno — diversità delle fonti è orthogonale alla loro reliability
- **Contradiction Detector** post-assemblaggio: scansione cross-sezione sul documento finale per rilevare affermazioni contraddittorie tra sezioni approvate in momenti diversi (il Judge Reasoning opera solo in-section)
- **Section Cache**: le sezioni approvate vengono hashate e salvate; se si riesegue con outline identico, le sezioni non cambiate vengono riutilizzate senza re-elaborazione
- **Hallucination Rate Tracker**: per ogni modello nella giuria, track del tasso storico di citazioni ghost non rilevate — base per decisioni di sostituzione futura dei giudici

***

## Verdict sintetico

| Dimensione | Voto | Nota |
| :-- | :-- | :-- |
| Design concettuale | ⭐⭐⭐⭐½ | Minority Veto e section-by-section sono genuinamente robusti |
| Completezza architetturale | ⭐⭐½ | CSS non definito, compressione handwavy, error handling assente |
| Readiness operativa | ⭐½ | Nessuna stima costi, latenza, testing, observability |
| Sicurezza | ⭐ | Prompt injection ignorata, privacy non menzionata |
| Output e integrabilità | ⭐⭐ | Solo DOCX, nessuna API strutturata, nessun versioning |

Il sistema è un'architettura di alta qualità **a livello di napkin design**. Per diventare un documento v1.0 deployabile richiede almeno: la formula del CSS, una error handling matrix, un cost model, e una sezione di observability.

<div align="center">⁂</div>

[^1]: Deep-Research-System.md

