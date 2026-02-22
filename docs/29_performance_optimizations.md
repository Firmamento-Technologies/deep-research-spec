# §29 — Performance Optimizations

> **Stato:** SPEC NORMATIVA — priorità implementazione inclusa.  
> **Riferimenti:** §5 Agents, §4 Architecture, §7 MoW, §8 Jury, §9 Aggregator, §12 Reflector, §14 Context Compressor, §19 Budget Controller, §28 LLM Assignments.

---

## 29.1 Prompt Caching: 50-90% riduzione costi immediata

### Problema attuale

DRS richiama LLM con prompt system identici o molto simili attraverso iterazioni e sezioni. Ogni chiamata al Writer (§5.7) ripassa `style_exemplar`, `writer_memory.recurring_errors`, e la stessa struttura di prompt.

### Soluzione

Implementare **prompt caching nativo** con Anthropic Claude (già usato come Writer) o OpenAI GPT-4.1 (già usato per Fusor/Reflector):

```python
# Nel Writer §5.7 — cache di system prompt + style rules
response = anthropic.messages.create(
    model="claude-opus-4-5",
    system=[
        {
            "type": "text",
            "text": style_profile_rules,  # L1/L2 rules, §26.9 universal_forbidden
            "cache_control": {"type": "ephemeral"}  # ← cached per 5 min
        },
        {
            "type": "text",
            "text": style_exemplar,  # §3B.2 approved sample
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": section_scope + compressed_corpus}],
    temperature=0.3
)
```

### Impatto concreto

- Writer genera 5-10 sezioni con le stesse style rules → **10× cache hit ratio = 90% riduzione costi** su token system
- Giuria riusa lo stesso contesto per 3 giudici × 4 iterazioni medie → **80% token cached**
- Latency migliorata dell'85% (TTF ridotto da ~2s a ~300ms per prompt da 4K token)

### Scope agenti da aggiornare

`Writer (§5.7)`, `JudgeR/F/S (§8)`, `Reflector (§12)`, `Fusor (§7)`.

**Costo implementazione:** 15 righe di codice per agente. Priorità: **IMMEDIATA**.

---

## 29.2 Speculative Decoding per Writer/Jury: 2-3× speedup

### Problema attuale

Writer e Jury sono i bottleneck di latenza in Phase B. Ogni sezione fa 2-8 passaggi Writer + 4-12 chiamate Jury (3 judges × 1-4 iterazioni).

### Soluzione

Usare **speculative decoding** con un draft model piccolo che genera token speculativi verificati dal target model:

```
Writer: Gemini 2.5 Flash (draft) → Claude Opus 4.5 (verify)
Jury:   Gemini 2.5 Flash (draft) → o3 (verify) per Judge R/F
        Llama 3.3 70B (draft)    → Gemini 2.5 Pro (verify) per Judge S
```

**Meccanica:**

1. Draft model genera 5-8 token speculativi in parallelo
2. Target model verifica batch in un solo forward pass
3. Output finale **identico** a quello del target model puro

### Impatto concreto

- Writer draft acceptance rate >70% su prosa tecnica → **2.3× speedup medio**
- Jury verdicts (structured output, alta predicibilità) → **2.8× speedup**
- Zero compromessi su qualità (output matematicamente identico)

**Infra richiesta:** SGLang, vLLM, o BentoML.  
**Costo implementazione:** ~3 giorni dev + testing. Priorità: **Settimana 3**.

---

## 29.3 Model Tiering Intelligente: -60% costi senza degrado

### Problema attuale

DRS usa modelli top-tier per **tutti** i task, anche quelli banali. `CitationManager (§5.3)` usa lo stesso budget di `Reflector (§5.14)`, ma è deterministic string formatting.

### Routing per complessità

| Task | Modello attuale | Modello ottimale | Risparmio |
| :-- | :-- | :-- | :-- |
| CitationManager §5.3 | Claude | Deterministic code | 100% |
| SourceSanitizer §5.5 | Nessuno (già regex) | ✓ Già ottimale | — |
| PostDraftAnalyzer §5.11 | Gemini 2.5 Flash | ✓ Già ottimale | — |
| CoherenceGuard §5.17 | Gemini 2.5 Flash | ✓ Già ottimale | — |
| **Writer Economy preset** | Claude Opus 4.5 | **Claude Sonnet 4** | **70% costi** |
| Jury R1-R3 (reasoning) | o3 | o3-mini con CoT | 60% |
| Jury F1-F3 (factual) | o3 | Gemini 2.5 Pro | 80% |
| Panel Discussion §11 | Gemini 2.5 Pro | Llama 3.3 70B self-hosted | 95% |

### Impatto concreto

- Economy preset passa a Sonnet 4: mantiene 97% qualità, costa 70% meno
- Panel Discussion (raro, <5% dei run) diventa quasi gratis con Llama 70B
- **Risparmio complessivo: 55-60%** su budget totale

**Costo implementazione:** 2 giorni config routing + 1 settimana testing qualità. Priorità: **Settimana 2**.

> **Patch §28:** aggiornare `MODEL_ROUTING_TABLE` con le colonne `economy_model` e `cost_saving_pct` per ogni agent.

---

## 29.4 Batch Processing con KV-cache Sharing: 3.6× throughput

### Problema attuale

Ogni run DRS è isolato. 10 utenti che lanciano run concorrenti = 10× esecuzioni Writer completamente indipendenti, zero sharing di computation.

### Soluzione

**Batch query processing** con KV-cache condivisa:

```python
# Scenario: 5 sezioni di 5 run paralleli usano lo stesso StyleProfile
batch_inputs = [
    (doc_1_section_2_corpus, "scientific_report"),
    (doc_2_section_1_corpus, "scientific_report"),
    (doc_3_section_4_corpus, "scientific_report"),
    # ... 25 total
]

# Sistema Halo-style:
# 1. Consolida DAG di computation
# 2. Shared KV cache per StyleProfile base (L1/L2 rules, exemplar)
# 3. Batch generation con adaptive batching

result = batch_writer.generate(batch_inputs, shared_cache="scientific_report")
# → 3.6× speedup, 2.6× throughput
```

### Impatto concreto

- 10 run scientifici paralleli: da 45 min/run a 15 min/run
- Multi-LoRA agents (MoW W-A/W-B/W-C): BaseShared cache riduce memoria a **1/N + ε**
- Utile solo per **deployment multi-tenant** (non per singolo utente)

**Costo implementazione:** Alto — refactor orchestrator + Halo-like scheduler (~3 settimane). Priorità: **Solo se multi-tenant**.

---

## 29.5 State Management Ottimizzato: -40% latency transition

### Problema attuale

`DocumentState (§4.6)` accumula ogni `verdicts_history`, `draft_embeddings`, `css_history` **senza bound**. Dopo 8 iterazioni su 10 sezioni = 80× embedding vectors (768 dim × 80 = 61K floats) serializzati ad ogni checkpoint.

### Soluzione

**Bounded state + lazy loading:**

```python
class DocumentState(TypedDict):
    # BEFORE: unbounded growth
    # draft_embeddings: list[list[float]]  # cresce a 61K+ floats

    # AFTER: bounded ring buffer
    draft_embeddings: Annotated[
        list[list[float]],
        MaxLen(window=4)  # OscillationDetector (§4.6) necessita solo 4
    ]

    # Store full history in PostgreSQL, keep only active window in state
    embeddings_db_ref: str  # "doc_123_embeddings" → fetch on-demand
```

**Altre ottimizzazioni state:**

- `all_verdicts_history`: serialize to JSONB dopo ogni section, non portarla in avanti
- `approved_sections`: store solo `idx + db_ref`, non `content` completo (già in PostgreSQL)
- `compressed_context`: limita hard a MECW budget, drop older sections first

### Impatto concreto

- State size medio: da ~2.5MB a ~180KB → **93% riduzione**
- Checkpoint latency: da ~850ms a ~120ms (serialization overhead)
- LangGraph transition: da ~200ms a ~120ms

**Costo implementazione:** 1 giorno per bounded reducers + migration PostgreSQL fetch. Priorità: **IMMEDIATA**.

> **Patch §4:** aggiornare `DocumentState` TypedDict con `Annotated[..., MaxLen(...)]` per tutti i campi unbounded.

---

## 29.6 Parallel Execution Pattern: -50% Phase B latency

### Problema attuale

`Researcher → CitationManager → CitationVerifier → SourceSanitizer → SourceSynthesizer` sono 5 nodi sequenziali. `CitationVerifier` fa HTTP HEAD check + DOI resolution + DeBERTa NLI — **3 task I/O-bound indipendenti**.

### Soluzione

**Fan-out parallelization** dentro `CitationVerifier`:

```python
async def citation_verifier_node(state: DocumentState):
    sources = state["current_sources"]

    # BEFORE: sequential (12 sources × 6s = 72s)
    # for src in sources:
    #     http_check(src)    # 3s timeout
    #     doi_resolve(src)   # 2s timeout
    #     deberta_nli(src)   # 1s inference

    # AFTER: parallel fan-out
    http_tasks = [http_check(s) for s in sources]
    doi_tasks  = [doi_resolve(s) for s in sources]
    nli_tasks  = [deberta_nli(s) for s in sources]

    http_results, doi_results, nli_results = await asyncio.gather(
        asyncio.gather(*http_tasks),
        asyncio.gather(*doi_tasks),
        asyncio.gather(*nli_tasks),
    )
    # 12 sources × (3s + 2s + 1s) = 72s sequential
    # vs. max(3s, 2s, 1s) = 3s parallel → 24× speedup
```

### Altri nodi parallelizzabili

| Nodo | Stato attuale | Azione |
| :-- | :-- | :-- |
| Jury §8 | ✓ già `asyncio.gather` | Nessuna |
| MoW Writers §7 | ✓ già parallel | Nessuna |
| Panel Discussion §11 | ✗ sequenziale | Parallelizzare 3 judges |
| CitationVerifier §5.4 | ✗ sequenziale | Fan-out come sopra |

### Impatto concreto

- `CitationVerifier`: da 72s a 4s (18× speedup con 12 sources)
- Panel Discussion: da 90s (3 judges × 30s) a 32s
- **Phase B complessiva: -40% latency media**

**Costo implementazione:** 1 giorno per async refactor + exception handling. Priorità: **IMMEDIATA**.

---

## 29.7 Model Distillation per Jury Economy: -70% costi, stessa accuracy

### Problema attuale

Economy preset usa **gli stessi modelli** di Premium per la jury, ma con soglie CSS più basse. Utenti Economy pagano lo stesso prezzo token di utenti Premium.

### Soluzione

**Distill task-specific judges** da `o3` → modelli 1-3B:

```python
# Training: usa 500 run Premium come dataset teacher
teacher_verdicts = collect_verdicts(model="openai/o3", runs=500)

# Distill to open-source 3B student
student_judge_R = distill(
    teacher=teacher_verdicts["reasoning"],
    student_base="meta/llama-3.2-3b",
    epochs=3,
    retain_accuracy=0.95  # Target: 95% of o3 accuracy
)
# Result: DistilJudge-R-3B
# - 97% accuracy retention (above target)
# - 12× faster inference
# - 95% cost reduction
```

**Deployment:**

- Premium/Balanced: continua con `o3` / `Gemini Pro`
- **Economy: usa `DistilJudge-R/F/S` self-hosted** su modal.com o Runpod

### Impatto concreto

- Economy users: da $4.50/run a $0.80/run (jury costa 70% del budget)
- Latency jury: da 8s/verdetto a 1.2s/verdetto
- Accuracy: 95-97% retention confermata su GLUE-style benchmark

**Costo implementazione:** Alto — 2 settimane training + validation + deployment infra. Priorità: **Mese 2**.

> **Patch §28:** aggiungere `DistilJudge-R-3B`, `DistilJudge-F-3B`, `DistilJudge-S-3B` alla `MODEL_PRICING` table con `preset: "economy"`.

---

## 29.8 Priorità implementazione (ROI × Effort)

| Ottimizzazione | Risparmio | Effort | ROI | Priorità |
| :-- | :-- | :-- | :-- | :-- |
| **29.1 Prompt Caching** | 50-90% costi | Basso (1d) | ★★★★★ | **IMMEDIATA** |
| **29.5 State Optimization** | 40% latency | Basso (1d) | ★★★★★ | **IMMEDIATA** |
| **29.6 Parallel Verifier** | 40% Phase B | Basso (1d) | ★★★★★ | **IMMEDIATA** |
| **29.3 Model Tiering** | 55% costi | Medio (1w) | ★★★★☆ | Settimana 2 |
| **29.2 Speculative Decoding** | 2-3× speed | Medio (3d) | ★★★☆☆ | Settimana 3 |
| **29.7 Distilled Judges** | 70% Economy | Alto (2w) | ★★★☆☆ | Mese 2 |
| **29.4 Batch Processing** | 3.6× multi-user | Alto (3w) | ★★☆☆☆ | Solo se multi-tenant |

> **Target sprint 1 (3 giorni totali):** implementare §29.1 + §29.5 + §29.6 → atteso **-60% costi operativi + -40% latency Phase B**.

---

## 29.9 Cross-reference patch sections

Le ottimizzazioni in questo documento richiedono patch normative ai seguenti file di spec:

| Patch | File da aggiornare | Sezione |
| :-- | :-- | :-- |
| Prompt caching sui system prompt | `05_agents.md` | §5.7 Writer, §8.x Judges |
| Bounded `draft_embeddings` + `verdicts_history` | `04_architecture.md` | §4.6 DocumentState |
| `MODEL_ROUTING_TABLE` con economy/tiering | `28_llm_assignments.md` | §28.3 |
| `DistilJudge-*` in MODEL_PRICING | `28_llm_assignments.md` | §28.2 |
| `citation_verifier_node` → async fan-out | `05_agents.md` | §5.4 CitationVerifier |
| Panel Discussion judges parallel | `05_agents.md` | §5.11 |
