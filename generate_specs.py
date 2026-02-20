"""
Deep Research System — Generatore Automatico Specifiche
Chiama Claude via OpenRouter per generare ogni file di specifica.
Supporta resume automatico: salta i file già presenti in /output.

Uso:
    python generate_specs.py

Variabili d'ambiente richieste:
    OPENROUTER_API_KEY  — la tua API key OpenRouter

Dipendenze:
    pip install openai python-dotenv
"""

import os
import time
import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# CONFIGURAZIONE
# ─────────────────────────────────────────

API_KEY        = os.getenv("OPENROUTER_API_KEY")
MODEL          = "anthropic/claude-opus-4-6"   # cambia qui se vuoi altro modello
MAX_TOKENS     = 8000                           # token per file — aumenta se le sezioni vengono troncate
RETRY_ATTEMPTS = 3
RETRY_DELAY    = 10                             # secondi tra retry

SOURCE_DIR = Path("source")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────
# DEFINIZIONE DEI FILE DA GENERARE
# Ogni entry: (nome_file, parti_scheletro, descrizione)
# ─────────────────────────────────────────

FILES = [
    (
        "01_visione_obiettivi.md",
        "PARTE I — VISIONE E CONTESTO / Sezione 1: Visione e Obiettivi (1.1, 1.2, 1.3, 1.4, 1.5)",
        "Scrivi la sezione Visione e Obiettivi. Includi: descrizione sintetica del sistema, casi d'uso target con range lunghezza, tabella tipologie utente, user stories in formato narrativo, vincoli di input con i due parametri obbligatori (max_budget_dollars, target_words)."
    ),
    (
        "02_principi_design.md",
        "PARTE I — Sezione 2: Principi di Design (2.1–2.11)",
        "Scrivi tutti gli 11 principi di design architetturali. Per ognuno: nome, spiegazione dettagliata del principio, motivazione, implicazioni implementative. I principi sono: Budget-First, Granularità Sezione-per-Sezione, Diversità Epistemica, Minority Veto a Due Livelli, Cascading Economico, Contesto Accumulato, Human-in-the-Loop Selettivo, Observability by Design, Resilienza Zero-Downtime, Sicurezza GDPR-Ready, Testability First."
    ),
    (
        "03_input_configurazione.md",
        "PARTE II — INPUT E CONFIGURAZIONE / Sezioni 3.1–3.8",
        "Scrivi la specifica completa di tutti gli input del sistema. Includi: input obbligatori con tipi e vincoli, tutti gli input opzionali per documento/stile/fonti/giuria, input aggiuntivi per profilo software_spec, schema YAML completo con tutti i campi, regole di validazione Pydantic con esempi di errori."
    ),
    (
        "04_architettura_flusso.md",
        "PARTE III — ARCHITETTURA / Sezione 4: Flusso Macro (4.1–4.4)",
        "Scrivi il flusso macro del sistema. Includi: diagramma ASCII completo del flusso Fase A→B→C→D con tutti i branch condizionali, descrizione dettagliata di ogni fase (Setup/Pre-Flight, Loop per Sezione, Post-Flight QA, Publisher), tutti i routing e condizioni di transizione tra fasi."
    ),
    (
        "05_agenti.md",
        "PARTE III — Sezione 5: Agenti del Sistema (5.1–5.18)",
        "Scrivi la specifica completa di ogni agente. Per ognuno: nome, responsabilità singola, input ricevuti, output prodotti, modello LLM assegnato, system prompt di riferimento, casi di errore gestiti. Agenti: Planner, Researcher, Citation Manager, Citation Verifier, Source Sanitizer, Metrics Collector, Writer, Writer Memory, Giurie R/F/S (con cascading tier1→tier2→tier3), Aggregatore CSS, Minority Veto, Panel Discussion, Reflector, Oscillation Detector, Context Compressor, Coherence Guard, Publisher, Feedback Collector."
    ),
    (
        "06_stato_langgraph.md",
        "PARTE III — Sezione 6: Schema di Stato LangGraph (6.1–6.6)",
        "Scrivi la definizione completa del DocumentState TypedDict. Includi: tutti i campi con tipi Python precisi, valori default, descrizione di ogni campo, strutture nested (BudgetState, Outline, ApprovedSection, JuryVerdict, ecc.), esempio di stato popolato in JSON, note su quali campi sono mutabili vs immutabili durante l'esecuzione."
    ),
    (
        "07_grafo_nodi_transizioni.md",
        "PARTE III — Sezione 7: Grafo LangGraph (7.1–7.3)",
        "Scrivi la definizione completa del grafo LangGraph. Includi: lista di tutti i nodi con funzione Python associata, tutti gli edge condizionali con le routing functions (route_outline_approval, route_after_aggregator, route_next_section, route_budget_check), codice Python del grafo completo, configurazione AsyncPostgresSaver per checkpointing, meccanismo di resume via thread_id."
    ),
    (
        "08_valutazione_css.md",
        "PARTE IV — SISTEMA DI VALUTAZIONE / Sezione 8: Formula CSS (8.1–8.3)",
        "Scrivi la specifica completa del Consensus Strength Score. Includi: formula matematica CSS = Σ w_k × (pass_k / n_k) con derivazione, pesi default (R:0.35, F:0.45, S:0.20) e motivazione, range [0,1] con semantica dei valori estremi, tabella routing post-CSS con tutte le condizioni e azioni corrispondenti, adattamento dinamico del threshold in base al regime Budget (Economy/Balanced/Premium)."
    ),
    (
        "09_convergenza.md",
        "PARTE IV — Sezione 9: Meccanismi di Convergenza (9.1–9.4)",
        "Scrivi la specifica completa dei meccanismi di convergenza. Includi: logica cascading economico tier1→tier2→tier3 con condizioni e risparmio atteso 60-70%, protocollo Panel Discussion completo (anonimizzazione, scambio motivazioni, revisione voti, max 2 tornate, archivio log), tre tipologie di oscillazione (CSS, semantica con cosine similarity, whack-a-mole), early warning e interfaccia escalazione umana."
    ),
    (
        "10_budget_controller.md",
        "PARTE V — BUDGET CONTROLLER / Sezione 10 (10.1–10.5)",
        "Scrivi la specifica completa del Budget Controller. Includi: formula Pre-Run Budget Estimator con calcolo per sezione, tabella regimi Economy/Balanced/Premium con soglie CSS/max_iter/jury_size/modelli, Real-Time Cost Tracker con allarmi WARN 70% / ALERT 90% / HARD STOP 100%, strategie di risparmio dinamico (fallback cascade, early stopping economico, Redis cache, batching jury), target costi $20–80/doc con esempio pratico budget $50."
    ),
    (
        "11_fonti.md",
        "PARTE VI — LAYER DI RICERCA FONTI / Sezione 11 (11.1–11.6)",
        "Scrivi la specifica completa del layer di ricerca fonti. Includi: architettura con interfaccia uniforme SourceConnector, specifica di ogni connettore (Accademico: CrossRef/Semantic Scholar/arXiv/DOAJ, Istituzionale: .gov/.eu/.un.org, Web: Tavily/Brave, Social: Reddit/Twitter) con reliability score, Custom Source Connector per fonti proprietarie e upload PDF/DOCX, Source Diversity Analyzer, algoritmo di deduplicazione."
    ),
    (
        "12_citazioni.md",
        "PARTE VI — Sezione 12: Gestione e Verifica Citazioni (12.1–12.4)",
        "Scrivi la specifica completa della pipeline citazioni. Includi: Citation Manager con formattazione per stile (Harvard, APA, Chicago, Vancouver), Citation Verifier con HTTP HEAD check e NLI entailment DeBERTa, classificazione ghost/mismatch/valid, percorso condizionale re-attivazione Researcher su missing_evidence, Hallucination Rate Tracker per modello."
    ),
    (
        "13_profili_stile.md",
        "PARTE VII — PROFILI DI STILE / Sezione 13 (13.1–13.6)",
        "Scrivi la specifica completa dei profili linguistici. Per ogni profilo (academic, business, technical, blog, software_spec): tono, registro, coverage citazioni richiesta, forbidden patterns specifici con esempi buono/cattivo, struttura frasi, pattern positivi. Includi: forbidden patterns universali trasversali a tutti i profili, sistema di internazionalizzazione con selezione modelli per lingua e locale-aware patterns."
    ),
    (
        "14_software_spec.md",
        "PARTE VIII — SOFTWARE SPEC / Sezione 14 (14.1–14.8)",
        "Scrivi la specifica completa della modalità Software Specification. Includi: rationale (DRS genera spec non codice), tre livelli di astrazione (COSA/COME/ESECUZIONE), Step 1 functional_spec con input/output, Step 2 technical_spec con input/output (architecture.md, data_schema, api_spec), Traceability Matrix, Step 3 software_spec con struttura directory output multi-file, Pipeline Orchestrator per step sequenziali, adattamento giuria (Judge F verifica testabilità, Judge S diventa AI-Readability Judge)."
    ),
    (
        "15_error_handling.md",
        "PARTE IX — RESILIENZA / Sezione 15: Error Handling Matrix (15.1–15.5)",
        "Scrivi la matrice completa di error handling. Per ogni scenario (API 429, API 500/Timeout, Output malformato, Citation ghost, Context overflow, Crash processo): prima risposta, seconda risposta, fallback, escalazione. Includi: retry policy con exponential backoff (2s→4s→8s, max 3 tentativi), circuit breaker (disabilita provider 5 min dopo N fallimenti), fallback chain configurata in YAML, graceful degradation con giuria ridotta, tecnologie (tenacity, aiohttp-circuitbreaker)."
    ),
    (
        "16_persistenza.md",
        "PARTE IX — Sezione 16: Persistenza e Checkpointing (16.1–16.3)",
        "Scrivi la specifica completa di persistenza e recovery. Includi: schema PostgreSQL con tutte le tabelle (documents, outlines, sections, jury_rounds, costs, sources) e campi, configurazione LangGraph AsyncPostgresSaver, meccanismo resume automatico via thread_id dopo crash, Redis cache con TTL e struttura chiavi, strategia di backup e retention policy."
    ),
    (
        "17_sicurezza_privacy.md",
        "PARTE X — SICUREZZA E PRIVACY / Sezione 17 (17.1–17.5)",
        "Scrivi la specifica completa del security layer. Includi: Source Sanitizer con wrapping XML anti-injection, PII Detection con presidio-analyzer prima di ogni LLM call, Privacy Mode con sostituzione modelli cloud con Ollama/VLLM locali, GDPR compliance (right-to-deletion, data export, data minimization, retention policy), Audit Log con tracciamento completo, elenco esplicito quali dati vanno a quali provider esterni."
    ),
    (
        "18_observability.md",
        "PARTE XI — OBSERVABILITY / Sezione 18 (18.1–18.5)",
        "Scrivi la specifica completa dell'observability stack. Includi: OpenTelemetry con span per ogni agente (latenza, token I/O, costo, modello), Prometheus con lista completa metriche (counters, gauges, histograms), Grafana dashboard con pannelli specifici (CSS trend, cost accumulator, latency P50/P95/P99, Rogue Judge monitor), Sentry per error tracking strutturato, Progress Dashboard real-time via WebSocket/Redis pub/sub, formato obbligatorio logging JSON strutturato."
    ),
    (
        "19_testing.md",
        "PARTE XII — TESTING / Sezione 19 (19.1–19.7)",
        "Scrivi la specifica completa del testing framework. Includi: Golden Dataset (20 documenti su domini diversi con criteri di selezione), metriche di valutazione (BERTScore, citation validity, style compliance regex, Cohen's kappa), Mock LLM con interfaccia di intercettazione, Regression Testing con soglia rollback CSS cala >0.05, Load Testing target 1000 job/giorno, Dependency Injection Architecture (pattern per ogni agente con wrapper iniettabili), Smoke Suite per fase MVP con comando make test-phaseN."
    ),
    (
        "20_escalazioni_umane.md",
        "PARTE XIII — ESCALAZIONI / Sezione 20 (20.1–20.6)",
        "Scrivi la specifica completa del protocollo Human-in-the-Loop. Per ogni trigger: informazioni presentate all'utente, azioni disponibili, comportamento del sistema dopo la scelta. Trigger: Approvazione Outline, Oscillazione Rilevata (con tipo e CSS history), Reflector Scope FULL, Coherence Guard HARD Conflict (con diff visuale), Budget >90% Speso (con proiezione), Rogue Judge Rilevato (con log voti anomali)."
    ),
    (
        "21_output_publisher.md",
        "PARTE XIV — OUTPUT / Sezione 21: Formati di Output (21.1–21.7)",
        "Scrivi la specifica completa del Publisher e dei formati di output. Per ogni formato (DOCX, PDF, MD, HTML, LaTeX, JSON strutturato, output multi-file software_spec): tecnologia usata, struttura del file, configurazione, casi d'uso. Includi: architettura Publisher con assemblaggio sezioni, template DOCX con stili, sommario automatico, bibliografia, section cache per evitare rigenerazione."
    ),
    (
        "22_post_flight_qa.md",
        "PARTE XIV — Sezione 22: Post-Flight QA (22.1–22.4)",
        "Scrivi la specifica completa della pipeline QA finale. Includi: Consistency Check (terminologia coerente, acronimi, nomi propri), Format Validation (riferimenti formattati, nessuna citazione orfana, heading hierarchy), Completeness Check (tutte le sezioni outline presenti, word count ±10%), Contradiction Final Scan (cross-sezione su documento assemblato), comportamento su fallimento di ogni check."
    ),
    (
        "23_stack_tecnologico.md",
        "PARTE XV — STACK TECNOLOGICO / Sezione 23 (23.1–23.8)",
        "Scrivi la tabella completa dello stack tecnologico. Per ogni layer: tecnologia scelta, versione minima, motivazione della scelta, alternative considerate e scartate. Layer: Orchestrazione (LangGraph), LLM Routing (OpenRouter), Backend (FastAPI+Uvicorn), Frontend (Streamlit→Next.js), Job Queue (Celery+Redis), Persistenza (PostgreSQL+Redis+S3), Containerizzazione (Docker/Kubernetes), CI/CD (GitHub Actions). Includi il file pyproject.toml completo con tutte le dipendenze."
    ),
    (
        "24_modelli_llm.md",
        "PARTE XV — Sezione 24: Modelli LLM (24.1–24.4)",
        "Scrivi la specifica completa dell'assegnazione modelli. Includi: tabella agente→modello primario→fallback1→fallback2 con giustificazione task-fit per ogni slot, principio task-fit vs classifica benchmark, configurazione Privacy Mode con sostituzione modelli cloud con Llama/Mistral/Qwen via Ollama, procedura di aggiornamento modelli (cambio riga YAML, nessun impatto codice), dizionario MODEL_PRICING con costi $/M token."
    ),
    (
        "25_prompt_layer.md",
        "PARTE XVI — PROMPT LAYER / Sezione 25 (25.1–25.3)",
        "Scrivi la specifica completa dell'architettura dei prompt. Includi: struttura a tre livelli (System prompt immutabile per identità agente, Context prompt dinamico per stato corrente, Task prompt specifico per invocazione), template completo per ogni agente con placeholder, istruzione anti-sycophancy per giudici (formulazione esatta da inserire nel system prompt), forbidden patterns completi per ogni profilo di stile con esempi."
    ),
    (
        "26_web_ui.md",
        "PARTE XVII — INTERFACCIA UTENTE / Sezione 26 (26.1–26.5)",
        "Scrivi la specifica completa della Web UI. Includi: Wizard di configurazione step-by-step con tutti i campi e validazioni, Style Profile Presets con live preview, Outline Editor visuale con drag-and-drop e inline editing, Progress Dashboard real-time con tutti i componenti (sezione corrente, CSS trend, cost gauge, iterazioni, ETA), Interfaccia Escalation con diff visuale e azioni disponibili."
    ),
    (
        "27_funzionalita_avanzate.md",
        "PARTE XVIII — FUNZIONALITÀ AVANZATE / Sezioni 27, 28, 29",
        "Scrivi la specifica delle funzionalità avanzate. Includi: Document Versioning (sezioni immutabili ma versionate, rollback, fork), Section Regeneration (sblocco sezione approvata, rigenerazione con istruzioni aggiuntive), Multi-User Mode (permessi owner/editor/reviewer, commenti inline, change tracking), Multi-Document Mode (glossario condiviso, citation reuse, cross-referencing tra documenti della serie), Feedback Loop e Training (rating per sezione, miglioramento prompt nel tempo)."
    ),
    (
        "28_deployment.md",
        "PARTE XIX — DEPLOYMENT / Sezione 30 (30.1–30.5)",
        "Scrivi la specifica completa di deployment e infrastruttura. Includi: configurazione ambiente Dev (Docker Compose locale, Mock LLM, PostgreSQL locale), Staging (Kubernetes, modelli reali a budget ridotto, dati anonimizzati), Produzione (Kubernetes con autoscaling, backup PostgreSQL ogni ora), rate limiting verso ogni provider (OpenRouter 60 req/min, CrossRef 50 req/s, Tavily rispetto Retry-After), strategia di scalabilità orizzontale per agenti come microservizi."
    ),
    (
        "29_kpi_metriche.md",
        "PARTE XX — KPI / Sezione 31 (31.1–31.4)",
        "Scrivi la specifica completa dei KPI e metriche di successo. Per ogni metrica: definizione precisa, valore target, metodo di misurazione, frequenza di misurazione. Categorie: Qualità documento (human acceptance >90%, citation accuracy >98%, style compliance 100%, error density <1/1000 parole), Efficienza economica (cost/doc $20–50, cost/word <$0.004, first-time approval >60%, avg iterations <2.5), Affidabilità (uptime >99.5%, recovery rate 100%), Convergenza (oscillation rate <5%, panel rate <15%, budget overrun 0%)."
    ),
    (
        "30_roadmap_mvp.md",
        "PARTE XXI — ROADMAP MVP / Sezione 32 (32.1–32.4)",
        "Scrivi la roadmap MVP completa a 4 fasi. Per ogni fase: obiettivo, scope esatto di componenti inclusi/esclusi, criteri di completamento (inclusa smoke suite obbligatoria), dipendenze dalla fase precedente, stima temporale. Fase 1 MVP Core (4 settimane), Fase 2 Multi-Judge (4 settimane), Fase 3 Advanced Features (6 settimane), Fase 4 Production (8 settimane). Includi diagramma delle dipendenze tra fasi."
    ),
    (
        "31_regole_operative.md",
        "PARTE XXII — REGOLE OPERATIVE / Sezione 33 (33.1–33.6)",
        "Scrivi le regole operative complete per l'AI Developer. Per ogni regola: descrizione, motivazione, esempio corretto vs scorretto. Regole: Pre-Flight Check obbligatorio prima di ogni run, Parsing sempre via Pydantic mai json.loads diretto, Parallelismo asincrono con asyncio.gather per mini-giurie, WebSocket via Redis pub/sub, Logging JSON strutturato con campi obbligatori, Dependency Injection obbligatoria (mai chiamate API dirette negli agenti)."
    ),
    (
        "00_indice.md",
        "INDICE GENERALE",
        "Scrivi l'indice completo del documento. Includi: titolo del progetto, versione, data, sommario esecutivo del sistema in massimo 300 parole, tabella con tutti i 31 file con numero, titolo, descrizione di una riga e link relativo. Aggiungi una sezione 'Come usare questo documento' che spiega l'ordine di lettura consigliato per diversi profili (developer che inizia da zero, developer che integra un componente specifico, project manager che valuta scope)."
    ),
]


# ─────────────────────────────────────────
# CARICAMENTO FILE SORGENTE
# ─────────────────────────────────────────

def load_sources() -> str:
    """Carica tutti i file sorgente in una stringa unica."""
    sources = []
    for path in sorted(SOURCE_DIR.glob("*.md")):
        print(f"  📄 Carico sorgente: {path.name}")
        content = path.read_text(encoding="utf-8")
        sources.append(f"\n\n{'='*60}\nFILE: {path.name}\n{'='*60}\n{content}")
    
    if not sources:
        raise FileNotFoundError(f"Nessun file .md trovato in {SOURCE_DIR}/")
    
    return "\n".join(sources)


# ─────────────────────────────────────────
# GENERAZIONE SINGOLO FILE
# ─────────────────────────────────────────

def generate_file(
    client: OpenAI,
    filename: str,
    section_ref: str,
    instructions: str,
    source_content: str,
    skeleton_content: str,
) -> str:
    """Chiama Claude per generare il contenuto di un file."""

    system_prompt = """Sei un technical writer senior che sta scrivendo le Specifiche di Progetto 
del Deep Research System (DRS) — un sistema multi-agente per la produzione di documenti di ricerca 
di alta qualità.

REGOLE FONDAMENTALI:
1. Usa SOLO le informazioni presenti nei file sorgente forniti. Non inventare nulla.
2. Se un'informazione non è nei sorgenti, scrivi esplicitamente "Da definire".
3. Scrivi in italiano, prosa fluente — non elenchi puntati eccessivi.
4. Ogni sezione deve essere completa e auto-consistente.
5. Includi tutti i dettagli tecnici: formule, strutture dati, esempi di codice dove rilevante.
6. Il documento sarà usato da un AI developer per implementare il sistema — deve essere preciso."""

    user_prompt = f"""Stai scrivendo il file: **{filename}**
Sezione dello scheletro di riferimento: {section_ref}

ISTRUZIONI SPECIFICHE PER QUESTO FILE:
{instructions}

---

SCHELETRO APPROVATO (usa questo per capire la struttura esatta richiesta):
{skeleton_content}

---

FILE SORGENTE (usa questi per ricavare tutte le informazioni):
{source_content}

---

Ora scrivi il contenuto completo per il file {filename}.
Inizia direttamente con il contenuto — nessuna introduzione meta sul tuo lavoro.
Usa heading Markdown appropriati (## per sezioni principali, ### per sottosezioni).
"""

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            print(f"    🤖 Chiamata API (tentativo {attempt}/{RETRY_ATTEMPTS})...")
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                extra_headers={
                    "HTTP-Referer": "https://github.com/deep-research-spec",
                    "X-Title": "Deep Research System Spec Generator",
                },
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"    ⚠️  Errore tentativo {attempt}: {e}")
            if attempt < RETRY_ATTEMPTS:
                print(f"    ⏳ Attendo {RETRY_DELAY}s prima di riprovare...")
                time.sleep(RETRY_DELAY)
            else:
                raise


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  DEEP RESEARCH SYSTEM — Generatore Specifiche")
    print("="*60)

    # Verifica API key
    if not API_KEY:
        raise ValueError("OPENROUTER_API_KEY non trovata. Crea un file .env con la tua chiave.")

    # Inizializza client OpenRouter
    client = OpenAI(
        api_key=API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )

    # Carica sorgenti
    print("\n📚 Carico file sorgente...")
    source_content  = load_sources()
    skeleton_path   = SOURCE_DIR / "DRS_Indice_Strutturale.md"
    skeleton_content = skeleton_path.read_text(encoding="utf-8") if skeleton_path.exists() else ""
    print(f"  ✅ Sorgenti caricati ({len(source_content):,} caratteri)")

    # Conta file da generare
    total     = len(FILES)
    skipped   = 0
    generated = 0
    failed    = []

    print(f"\n🚀 Inizio generazione — {total} file totali\n")

    for i, (filename, section_ref, instructions) in enumerate(FILES, 1):
        output_path = OUTPUT_DIR / filename
        timestamp   = datetime.datetime.now().strftime("%H:%M:%S")

        print(f"[{timestamp}] ({i}/{total}) {filename}")

        # Resume: salta file già presenti
        if output_path.exists() and output_path.stat().st_size > 100:
            print(f"    ⏭️  Già presente — salto\n")
            skipped += 1
            continue

        try:
            content = generate_file(
                client,
                filename,
                section_ref,
                instructions,
                source_content,
                skeleton_content,
            )

            output_path.write_text(content, encoding="utf-8")
            size = len(content)
            print(f"    ✅ Salvato ({size:,} caratteri)\n")
            generated += 1

            # Pausa breve tra chiamate per rispettare rate limit
            if i < total:
                time.sleep(2)

        except Exception as e:
            print(f"    ❌ FALLITO: {e}\n")
            failed.append(filename)

    # ─── Report finale ───
    print("\n" + "="*60)
    print("  COMPLETATO")
    print("="*60)
    print(f"  ✅ Generati:   {generated}")
    print(f"  ⏭️  Saltati:    {skipped}")
    print(f"  ❌ Falliti:    {len(failed)}")
    if failed:
        print(f"\n  File falliti:")
        for f in failed:
            print(f"    - {f}")
        print("\n  Riesegui lo script per riprovare i file falliti.")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
