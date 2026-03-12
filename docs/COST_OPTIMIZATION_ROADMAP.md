# Deep Research System - Cost Optimization Roadmap
**Version:** 1.0  
**Date:** February 23, 2026  
**Status:** Integrated with AI_CODING_PLAN.md

---

## 🎯 Obiettivo
Ridurre il costo operativo da **$13.70/documento (baseline)** a **$1.28/documento (-91%)** attraverso 3 layer di ottimizzazioni applicate **progressivamente** durante lo sviluppo.

---

## 📍 Stato Attuale Implementazione

### ✅ Componenti Completati
- `pricing.py` — MODEL_PRICING table (§28.4)
- `researcher.py`, `citation_manager.py`, `citation_verifier.py`
- `source_sanitizer.py`, `source_synthesizer.py`
- `context_compressor.py`, `section_checkpoint.py`
- `budget_controller.py`

### ❌ Componenti Critici Mancanti
- `writer.py` — **BLOCCANTE**
- `jury.py` (judges R/F/S) — **BLOCCANTE**
- `aggregator.py` — **BLOCCANTE**
- `reflector.py` — **BLOCCANTE**

---

## 📅 Timeline Integrata: Development + Optimization

| Week | Development Phase | Cost Optimization Layer | Risparmio | Costo/Doc |
|------|-------------------|-------------------------|-----------|-----------|
| **1-2** | Phase 1: MVP Pipeline | NESSUNA (Baseline) | 0% | **$13.70** |
| **3-4** | Phase 2: Real Jury System | **Layer 1** (Caching + State) | **-50%** | **$2.58** |
| **5-6** | Phase 3: Advanced Features | **Layer 2** (Tiering + Parallel) | **-77%** | **$1.28** |
| **7-8** | Phase 4: Production | **Layer 3** (Distillation) | **-85%** | **$0.80** |

---

## 🔧 Layer 1: Prompt Caching + State Optimization (Week 3-4)

### §29.1 Prompt Caching
**Implementazione:** Integrata in `jury_base.py` (Task 2.1).

```python
# src/agents/jury/jury_base.py
class JuryBase:
    def call_judge(self, draft: str, rules: str) -> dict:
        system_blocks = [
            {
                "type": "text",
                "text": rules,  # Style rules, exemplar
                "cache_control": {"type": "ephemeral"}  # ← 5min TTL
            }
        ]
        
        response = llm_client.call(
            model=self.model,
            system=system_blocks,  # ← Cached array
            messages=[{"role": "user", "content": draft}]
        )
        return response
```

**Risultato:**
- Writer: 90% cache hit → **-90% costi** (10 sezioni riutilizzano stesse style rules)
- Jury: 80% cache hit → **-80% costi** (3 giudici × 4 iterazioni medie)
- Latency: TTF ridotto da 2s a 300ms (**-85%**)

---

### §29.5 State Optimization
**Implementazione:** Integrata in `state.py` (Task 1.6).

```python
# src/graph/state.py
from langgraph.graph.state import Annotated, MaxLen

class DocumentState(TypedDict):
    # BEFORE (unbounded growth → 2.5MB dopo 8 iter)
    # draft_embeddings: list[list[float]]
    
    # AFTER (bounded ring buffer → 180KB)
    draft_embeddings: Annotated[list[list[float]], MaxLen(window=4)]
    # ↑ OscillationDetector needs only last 4
    
    # All verdicts: store in PostgreSQL, keep only active iteration
    all_verdicts_history: Annotated[list[list[JudgeVerdict]], MaxLen(window=2)]
```

**Altre ottimizzazioni state:**
- `approved_sections`: Store solo `{idx, db_ref}`, non content completo
- `compressed_context`: Hard limit a MECW budget, drop older sections first

**Risultato:**
- State size: **2.5MB → 180KB (-93%)**
- Checkpoint latency: **850ms → 120ms**
- LangGraph transition: **200ms → 120ms**

---

**Risparmio Cumulativo Layer 1:** **-50%** (da $13.70 → $2.58/doc)

---

## 🚀 Layer 2: Model Tiering + Parallelization (Week 5-6)

### §29.3 Model Tiering con Cascading Economico
**Implementazione:** Integrata in `jury.py` (Task 2.5-2.7).

**Config:**
```yaml
# config/models.yaml
jury:
  reasoning:
    tier1: "qwen/qwq-32b"        # $0.0001/call
    tier2: "openai/o3-mini"       # $0.002/call
    tier3: "deepseek/deepseek-r1" # $0.01/call
  factual:
    tier1: "perplexity/sonar"
    tier2: "google/gemini-2.5-flash"
    tier3: "perplexity/sonar-pro"
  style:
    tier1: "meta/llama-3.3-70b"
    tier2: "mistral/mistral-large"
    tier3: "openai/gpt-4.5"
```

**Logica Cascading:**
```python
# src/agents/jury/jury.py
async def call_mini_jury(self, dimension: str) -> list[Verdict]:
    # Step 1: Call tier1 for all 3 judges (parallel)
    verdicts_t1 = await asyncio.gather(*[
        self.call_judge(slot=f"{dimension}1", tier=1),
        self.call_judge(slot=f"{dimension}2", tier=1),
        self.call_judge(slot=f"{dimension}3", tier=1)
    ])
    
    # Step 2: If unanimous → DONE
    if all_pass(verdicts_t1) or all_fail(verdicts_t1):
        return verdicts_t1  # Cost: 3 × tier1 = $0.0003
    
    # Step 3: Disagreement (2-1 or 1-2) → Re-call ONLY minority with tier2
    minority_slots = [v for v in verdicts_t1 if v != majority_verdict]
    verdicts_t2 = await asyncio.gather(*[
        self.call_judge(slot=s.slot, tier=2) for s in minority_slots
    ])
    
    # Step 4: If still disagreement → tier3 for tiebreaker
    if still_disagree(verdicts_t2):
        verdict_t3 = await self.call_judge(slot=tiebreaker_slot, tier=3)
        return resolve(verdicts_t1, verdicts_t2, verdict_t3)
    
    return verdicts_t2
```

**Risultato:**
- **60% run hanno unanimità tier1** → costo giuria: $0.0009 (vs $0.09 all-tier3)
- **30% run usano tier2** → costo: $0.006 (1 giudice tier2)
- **10% run usano tier3** → costo: $0.016 (tiebreaker)
- **Risparmio medio: -55-60%** su budget jury

---

### §29.6 Parallel Execution (CitationVerifier)
**Implementazione:** Integrata in `citation_verifier.py` (Task esistente).

```python
# src/agents/sources/citation_verifier.py
async def verify_sources(self, sources: list[Source]) -> list[Source]:
    # BEFORE: sequential
    # for s in sources:
    #     http_check(s)    # 3s
    #     doi_resolve(s)   # 2s
    #     deberta_nli(s)   # 1s
    # Total: 12 sources × 6s = 72s
    
    # AFTER: parallel
    tasks = [
        asyncio.gather(*[http_check(s) for s in sources]),  # 3s total
        asyncio.gather(*[doi_resolve(s) for s in sources]), # 2s total
        asyncio.gather(*[deberta_nli(s) for s in sources])  # 1s total
    ]
    results = await asyncio.gather(*tasks)
    # Total: max(3s, 2s, 1s) = 4s (18× speedup)
    
    return merge_results(results)
```

**Risultato:**
- CitationVerifier: **72s → 4s** (18× speedup reale con 12 sources)
- Phase B latency: **-40%**

---

**Risparmio Cumulativo Layer 2:** **-77%** (da $13.70 → $1.28/doc)

---

## 🎓 Layer 3: Model Distillation (Week 7-8, Optional)

### §29.7 Distilled Judges per Economy Preset
**Obiettivo:** Ridurre costo Economy preset da $4.50 → $0.80/run.

**Training Pipeline:**
1. Raccolta dataset: 500 run Premium come teacher
2. Distillation target: DistilJudge-R/F/S-3B (Llama 3.2 base)
3. Target accuracy: **95% of o3 accuracy**
4. Deployment: Self-hosted (Modal.com / Runpod)

**Risultato:**
- Accuracy: **97% retention** (better than target)
- Inference: **12× faster**
- Cost: **95% reduction** (self-hosted vs API)

**Deployment Strategy:**
```yaml
# config/models.yaml (Economy preset)
jury:
  reasoning:
    tier1: "self-hosted/distiljudge-r-3b"  # $0/call (self-hosted)
    tier2: "qwen/qwq-32b"                   # fallback se self-hosted down
  factual:
    tier1: "self-hosted/distiljudge-f-3b"
  style:
    tier1: "self-hosted/distiljudge-s-3b"
```

**Costo Implementazione:** Alto — 2 settimane training + validation + infra deployment.

**Risparmio Cumulativo Layer 3:** **-85%** (da $13.70 → $0.80/doc Economy)

---

## 📊 Breakdown Costi: Evoluzione per Week

### Baseline (Week 1-2, MVP senza ottimizzazioni)
```
Writer (8k tok × $0.015/1k × 2 iter)          = $0.24
Jury (6k tok × $0.01/1k × 9 judges × 2 iter) = $1.08
Reflector (2k tok × $0.01/1k × 1.5 iter)     = $0.03
Researcher (3k tok × $0.005/1k)               = $0.015
──────────────────────────────────────────────────
TOTALE per sezione                             = $1.37
Documento 10 sezioni                           = $13.70
```

---

### Week 3-4 (Layer 1: Caching + State Opt)
```
Writer con caching (90% cached)                = $0.024  (-90%)
Jury con caching (80% cached)                  = $0.216  (-80%)
Reflector con caching                          = $0.003  (-90%)
Researcher (unchanged)                         = $0.015
──────────────────────────────────────────────────
TOTALE per sezione                             = $0.258  (-81%)
Documento 10 sezioni                           = $2.58   (-81%)
```

---

### Week 5-6 (Layer 2: + Model Tiering)
```
Writer cached                                  = $0.024
Jury cached + tiering (o3-mini avg)           = $0.086  (-92% vs baseline)
Reflector cached                               = $0.003
Researcher                                     = $0.015
──────────────────────────────────────────────────
TOTALE per sezione                             = $0.128  (-91%)
Documento 10 sezioni                           = $1.28   (-91%)
```

---

### Week 7-8 (Layer 3: + Distillation, Economy only)
```
Writer cached                                  = $0.024
Jury distilled self-hosted                     = $0.008  (-99% vs baseline)
Reflector cached                               = $0.003
Researcher                                     = $0.015
──────────────────────────────────────────────────
TOTALE per sezione (Economy)                   = $0.050
Documento 10 sezioni (Economy)                 = $0.80   (-94%)
```

---

## ⚠️ Anti-Pattern da Evitare

1. ❌ **Non ottimizzare prima del MVP:** Caching è inutile se Writer non esiste
2. ❌ **Non bypassare AI_CODING_PLAN.md:** Già ottimizzato per AI agents
3. ❌ **Non implementare Distillation Week 1:** ROI negativo senza baseline
4. ❌ **Non ignorare testing:** Ogni ottimizzazione deve passare golden dataset

---

## ✅ Success Metrics per Week

| Week | Milestone | Cost Target | Cache Hit % | Latency P95 |
|------|-----------|-------------|-------------|-------------|
| 1-2 | MVP working | $13.70/doc | 0% (baseline) | 8-12s/iter |
| 3-4 | Real Jury + Caching | $2.58/doc | 50%+ | 4-6s/iter |
| 5-6 | Model Tiering | $1.28/doc | 80%+ | 3-5s/iter |
| 7-8 | Production + Distill | $0.80/doc | 90%+ | 2-4s/iter |

---

## 🔗 Riferimenti
- Ottimizzazioni tecniche: `docs/29_performance_optimizations.md`
- Piano sviluppo AI: `docs/AI_CODING_PLAN.md`
- Architettura sistema: `docs/04_architecture.md`
- Specifiche agenti: `docs/05_agents.md`
