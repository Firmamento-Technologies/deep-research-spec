# Audit critico iper-approfondito — Deep Research System

## Contesto e perimetro

Analisi svolta sul repository locale (`/workspace/deep-research-spec`, branch `work`) con focus su:
- consistenza architetturale tra backend, frontend, test, CI/CD e Docker;
- stato reale di build/test rispetto alle promesse documentali;
- rischi tecnici e di delivery.

## Valutazione sintetica dello stato di sviluppo

**Stadio complessivo stimato: "late prototype / pre-beta instabile"**.

Il progetto mostra molti segnali di maturità parziale (docker-compose ricco, test presenti, workflow CI/CD, moduli avanzati), ma non è allineato in modo coerente tra le sue parti:
1. documentazione ad alto livello non aderente al codice attuale;
2. frontend non compilabile out-of-the-box;
3. suite test non avviabile in ambiente pulito senza interventi manuali;
4. duplicazione di codebase/backend che genera conflitti di import e incertezza sul "source of truth".

## Evidenze principali (errori, criticità, incongruenze)

### 1) Disallineamento architetturale forte (due backend concorrenti)

Nel repository coesistono almeno due "linee" applicative:
- stack root-level (`src/`, `tests/`, `requirements.txt`) con server in `src/api/server.py`;
- stack `backend/` con entrypoint separato in `backend/main.py` e package `backend/api`, `backend/services`, `backend/src`.

Questo produce ambiguità operativa su:
- quale app FastAPI sia quella canonica;
- quale set di test e dipendenze debba essere eseguito in CI locale;
- quale path d'import sia corretto (es. `services.*` vs `src.services.*`).

### 2) README principale non aderente allo stato attuale

Il `README.md` dichiara quickstart e struttura centrati su `src/` e `tests/`, ma gran parte dell'operatività reale è spostata in `backend/` e `frontend/` con Docker multi-servizio.

Inoltre alcune dichiarazioni (es. stato test "156+ tests, 0 failures") non sono verificabili nello stato corrente senza setup aggiuntivo e/o fix strutturali.

### 3) Frontend attualmente **non buildabile**

Esecuzione `npm --prefix frontend run build` fallisce con errori bloccanti:
- dipendenze mancanti rispetto agli import (`@tanstack/react-query`, `axios`, `lucide-react`);
- moduli importati ma assenti (`./pages/Dashboard`, `../components/ui/Button`, `../components/ui/Card`);
- errori TypeScript strict (`implicit any`, unused imports).

Questa è una criticità release-blocker per qualsiasi milestone UI.

### 4) Test backend/root non eseguibili in modo pulito

Esecuzione `python3 -m pytest backend/tests/unit -q` fallisce già in collection con `ModuleNotFoundError: No module named 'httpx'` (dipendenza non presente nell'ambiente).

Esecuzione `python3 -m pytest tests/unit -q` (suite root-level) fallisce in collection per conflitto import:
- i test forzano `backend/src` nel `sys.path`;
- il package `services` (in `backend/src/services/__init__.py`) importa `src.services.run_manager`, path non disponibile in quel contesto.

Risultato: anche i test "di sicurezza" non possono funzionare come baseline affidabile senza riallineamento package layout.

### 5) Contraddizioni tra setup docs e repository operativo

`SETUP_GUIDE.md` richiede checkout `fix/ui-issues-and-docker-config` e descrive troubleshooting specifico, ma il workspace corrente è su branch `work` con stato file molto differente.

Questo segnala rischio di deriva tra branch/documentazione e rende fragile il passaggio di consegne (onboarding + debug).

### 6) Rischio manutentivo da artefatti versionati non strategici

Il repository contiene `frontend/node_modules` versionato (o comunque fortemente presente nel tree), con moltissimi file modificati localmente.

Impatto:
- rumore enorme nel versionamento;
- diff poco leggibili;
- rischio elevato di commit accidentali non deterministici;
- peggioramento di CI cache e riproducibilità.

### 7) CI/CD presente ma probabilmente non "truthful"

Esistono workflow completi (lint, test, build immagini, deploy), ma la coerenza con stato reale del codice è dubbia perché:
- il frontend non builda localmente;
- i test falliscono in collection senza setup aggiuntivo;
- nel repo ci sono tracce di strutture e path non uniformi.

Conclusione: pipeline CI formalmente ricca, ma valore operativo ridotto finché non si definisce una singola baseline di progetto.

## Diagnosi tecnica: perché succede

Pattern tipico di sviluppo "merge di roadmap diverse" senza hardening finale:
- evoluzione rapida su più branch tematici (UI, Docker, Knowledge Spaces, pipeline LLM);
- integrazione parziale con duplicazione directory (`src` vs `backend/src`);
- documentazione aggiornata solo per sottosezioni;
- assenza di una fase di "stabilization sprint" dedicata a riduzione debito tecnico.

## Priorità di remediation (ordine consigliato)

1. **Definire un solo runtime canonico** (o `src/` root oppure `backend/`), deprecando l'altro con piano di migrazione.
2. **Ripristinare build frontend**: installare dipendenze mancanti, rimuovere/importare correttamente pagine e componenti UI assenti, risolvere strict TS errors.
3. **Ripulire import path Python**: eliminare conflitti `services.*` / `src.services.*` e fissare una convenzione unica.
4. **Rendere i test eseguibili in clean env** con bootstrap deterministico (Makefile/script unico).
5. **Allineare README e SETUP_GUIDE** allo stato reale (niente claim non verificabili).
6. **Escludere `node_modules` dal versionamento effettivo** (se non strettamente richiesto) e ridurre noise di git.
7. **Gate CI minimi obbligatori**: frontend build + backend unit collection + smoke API prima di merge su branch principali.

## Severità stimata

- **Criticità bloccanti (P0-P1):** frontend build rotto, test collection rotta, architettura duplicata.
- **Criticità alte (P1-P2):** documentazione incoerente, path/import non uniformi.
- **Criticità medie (P2):** hygiene repository (`node_modules`), affidabilità processo release.

## Conclusione critica

Il progetto è **tecnicamente promettente ma non ancora in stato "production-ready"**.

La qualità percepita (feature list e ambizione architetturale) è superiore alla qualità di integrazione corrente. Il rischio principale non è "mancanza di feature", ma **frammentazione della base codice**: senza consolidamento, ogni nuovo fix aumenta il costo marginale di sviluppo e debugging.

In termini pratici: prima di aggiungere nuove capability, conviene investire 1 sprint corto (hardening) per trasformare il sistema da "dimostrabile" a "affidabile".
