# Cline Setup Prompt — DRS Project Organization

> **Purpose:** Initial project organization and conflict resolution  
> **Target:** Cline (or similar AI coding assistant)  
> **Phase:** Pre-implementation setup  

---

## 📌 Note: Implementation vs Setup

**This file is for PROJECT SETUP only** (conflict resolution, directory structure).

**For IMPLEMENTATION** (coding DRS components), use:

👉 **[`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)**

---

## Your Task: Project Organization

Leggi tutti i file in `output/*.md` — sono le specifiche del Deep Research System (DRS).

Il tuo compito è organizzare questo progetto per implementazione efficiente seguendo l'architettura descritta in `GEMINI.md`.

### Cosa devi produrre

**1. `output/00_conflict_resolutions.md`**

Leggi tutti i 41 file spec e identifica ogni conflitto (valori diversi per la stessa cosa tra file diversi).

Per ogni conflitto, stabilisci quale file è la fonte canonica e scrivi il valore risolto.

Questo file sarà letto per primo da ogni agente implementatore.

**2. `directives/00_overview.md`**

Overview del progetto: stack, struttura `src/`, vincoli globali, ordine di implementazione.

**3. `directives/01_state.md` attraverso `directives/09_api.md`**

Una direttiva per ogni fase di implementazione. Ogni direttiva deve contenere:
- Obiettivo preciso (cosa implementare)
- Quali file spec leggere (con sezione specifica)
- Struttura esatta dell'output (nomi file, classi, funzioni)
- Script di validazione da eseguire dopo

**4. `execution/validate_state.py`**

Script che verifica che `src/state.py` abbia tutti i campi richiesti da `DocumentState`.

**5. `execution/run_graph_compile.py`**

Script che verifica che `src/graph.py` compili senza errori con LangGraph.

**6. `execution/test_routing.py`**

Test unitari per le routing functions con casi edge espliciti.

---

## Regole

- Le direttive devono essere abbastanza precise che un LLM possa implementarle senza leggere tutta la spec
- Ogni direttiva deve referenziare i file spec specifici e le sezioni specifiche (es. "leggi output/09_css_aggregator.md §9.4")
- In caso di conflitto tra spec files, usa sempre i valori in `output/00_conflict_resolutions.md`
- NON modificare nulla in `output/` eccetto creare `00_conflict_resolutions.md`
- NON iniziare a implementare il codice DRS — solo setup della struttura di progetto

---

## After Setup: Next Steps

Once project organization is complete:

👉 **Start implementation following [`docs/AI_CODING_PLAN.md`](docs/AI_CODING_PLAN.md)**

**Phase 0**: RAG + SHINE infrastructure  
**Phase 1**: MVP pipeline  
**Phase 2**: Jury system  
**Phase 3**: Iteration loop  
**Phase 4**: Production features

---

Inizia leggendo tutti i file in `output/` prima di scrivere qualsiasi file.
