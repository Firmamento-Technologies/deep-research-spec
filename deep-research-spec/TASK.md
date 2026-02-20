# TASK — Generazione Specifiche di Progetto DRS

## Contesto
Sei un technical writer incaricato di scrivere il documento completo 
delle Specifiche di Progetto del Deep Research System (DRS).

## File sorgente
Tutte le informazioni necessarie sono in `/source`:
- `deep.md` e `deep(2).md` — conversazione di design completa
- `Analisi_Critica_*.md` — analisi critiche con integrazioni v2.0
- `valuta_attentamente_*.md` — ulteriori integrazioni e stress test
- `DRS_Indice_Strutturale.md` — lo scheletro approvato che definisce 
  ESATTAMENTE cosa scrivere in ogni sezione

## Regola fondamentale
Usa SOLO le informazioni nei file sorgente. Non inventare nulla.
Ogni affermazione deve essere ricavabile dai file in /source.

## Istruzioni operative

### Come lavorare
1. Leggi interamente `DRS_Indice_Strutturale.md` — è la tua mappa
2. Per ogni file da generare: cerca nei sorgenti le informazioni 
   relative a quella sezione, poi scrivi il contenuto completo
3. Genera un file alla volta nell'ordine indicato
4. Dopo ogni file: fai commit git con messaggio descrittivo
5. Se un file è già presente in /output, saltalo e passa al successivo
   (meccanismo di resume automatico)

### Standard di scrittura
- Prosa continua, non bullet point eccessivi
- Ogni sezione deve essere COMPLETA e AUTO-CONSISTENTE
- Includi tutti i dettagli tecnici: formule, strutture dati, 
  esempi di codice dove specificato nello scheletro
- Lunghezza adeguata al contenuto — non troncare per brevità

## File da generare in ordine

Genera ogni file in `/output/` rispettando esattamente 
il contenuto descritto nello scheletro per ogni sezione.

### Blocco 1 — Fondamenta
- `01_visione_obiettivi.md` → Parti I (sezioni 1)
- `02_principi_design.md` → Parte I (sezione 2)
- `03_input_configurazione.md` → Parte II (sezione 3)

### Blocco 2 — Architettura Core
- `04_architettura_flusso.md` → Parte III (sezione 4)
- `05_agenti.md` → Parte III (sezione 5)
- `06_stato_langgraph.md` → Parte III (sezione 6)
- `07_grafo_nodi_transizioni.md` → Parte III (sezione 7)

### Blocco 3 — Valutazione e Budget
- `08_valutazione_css.md` → Parte IV (sezione 8)
- `09_convergenza.md` → Parte IV (sezione 9)
- `10_budget_controller.md` → Parte V (sezione 10)

### Blocco 4 — Fonti e Stile
- `11_fonti.md` → Parte VI (sezione 11)
- `12_citazioni.md` → Parte VI (sezione 12)
- `13_profili_stile.md` → Parte VII (sezione 13)
- `14_software_spec.md` → Parte VIII (sezione 14)

### Blocco 5 — Resilienza e Sicurezza
- `15_error_handling.md` → Parte IX (sezione 15)
- `16_persistenza.md` → Parte IX (sezione 16)
- `17_sicurezza_privacy.md` → Parte X (sezione 17)
- `18_observability.md` → Parte XI (sezione 18)

### Blocco 6 — Qualità e Output
- `19_testing.md` → Parte XII (sezione 19)
- `20_escalazioni_umane.md` → Parte XIII (sezione 20)
- `21_output_publisher.md` → Parte XIV (sezione 21)
- `22_post_flight_qa.md` → Parte XIV (sezione 22)

### Blocco 7 — Stack e Operativo
- `23_stack_tecnologico.md` → Parte XV (sezione 23)
- `24_modelli_llm.md` → Parte XV (sezione 24)
- `25_prompt_layer.md` → Parte XVI (sezione 25)
- `26_web_ui.md` → Parte XVII (sezione 26)
- `27_funzionalita_avanzate.md` → Parte XVIII (sezioni 27-29)
- `28_deployment.md` → Parte XIX (sezione 30)
- `29_kpi_metriche.md` → Parte XX (sezione 31)
- `30_roadmap_mvp.md` → Parte XXI (sezione 32)
- `31_regole_operative.md` → Parte XXII (sezione 33)

### File finale
- `00_indice.md` → indice completo con link a tutti i file 
  e sommario di una riga per ciascuno
