# §0 — Conflict Resolutions (READ THIS FIRST)

> **Purpose:** Ogni agente implementatore DEVE leggere questo file prima di qualsiasi spec.
> Quando un valore in un file spec differisce da quanto riportato qui, **questo file vince**.

---

## 0.1 Single Sources of Truth (Canonical Files)

| Concetto | File canonico | Sezione |
|----------|---------------|---------|
| CSS thresholds per regime | `09_css_aggregator.md` | §9.3 THRESHOLD_TABLE |
| CSS formula (CSS_content, CSS_style) | `09_css_aggregator.md` | §9.1 |
| Jury weights | `09_css_aggregator.md` | §9.2 |
| `route_after_aggregator()` | `09_css_aggregator.md` | §9.4 (unica definizione) |
| `route_after_reflector()` | `05_agents.md` | §12.5 (inline in §05) |
| `route_after_oscillation()` | `04_architecture.md` | §4.5 |
| DocumentState TypedDict | `04_architecture.md` | §4.6 |
| LangGraph graph definition | `04_architecture.md` | §4.5 |
| Model assignments (primary + fallback) | `28_llm_assignments.md` | §28.2 |
| MODEL_PRICING | `28_llm_assignments.md` | §28.4 (`src/llm/pricing.py`) |
| YAML config Pydantic schema | `29_yaml_config.md` | §29.6 |
| API input DRSConfig schema | `03_input_config.md` | §3.3 |
| Regime table (Economy/Balanced/Premium) | `19_budget_controller.md` | §19.2 |
| MoW activation & internal topology | `07_mixture_of_writers.md` | §7.1, §7.6 |
| Veto categories & detection | `10_minority_veto.md` | §10.1, §10.2 |
| Project directory tree | `34_deployment.md` | §34.4 |
| Tech stack + pyproject.toml | `33_tech_stack.md` | §33.10 |
| PostgreSQL schema | `21_persistence.md` | §21.1 |
| Design principles | `02_design_principles.md` | §2.1–§2.11 |

---

## 0.2 Resolved Conflicts — Per Conflitto

### C01 — Source type enum: `"general"` vs `"web"`, `"uploaded"` vs `"upload"`

| File | Valore | 
|------|--------|
| `04_architecture.md` §4.6 Source TypedDict | `"web"`, `"upload"` |
| `05_agents.md` §5 Shared Types | `"general"`, `"uploaded"` |
| `21_persistence.md` §21.1 sources table | `"web"` (CHECK constraint) |

**RISOLUZIONE:** Usare i valori di §4.6 (canonical DocumentState):
```python
source_type: Literal["academic", "institutional", "social", "web", "upload"]
```
- `"general"` → rinominare a `"web"` ovunque
- `"uploaded"` → rinominare a `"upload"` ovunque

---

### C02 — Style profile naming: `"scientific_report"` vs `"academic"`

| File | Valori usati |
|------|-------------|
| `01_vision.md` §1.2 DocType | `"scientific_report"`, `"business_report"`, `"technical_documentation"` |
| `05_agents.md` Shared Types | `"scientific_report"`, `"business_report"`, `"technical_documentation"` |
| `29_yaml_config.md` §29.1 | `"academic"`, `"business"`, `"technical"` |
| `03_input_config.md` §3.1 | `"scientific_report"`, `"business_report"`, `"technical_documentation"` |
| `24_api.md` §24.2 | Aggiunge `"functional_spec"`, `"technical_spec"` (non esistenti altrove) |

**RISOLUZIONE:** Esistono DUE enum distinti con scopi diversi:

1. **StyleProfile** (config utente, YAML, API — §29 canonical):
```python
StyleProfile = Literal[
    "academic", "business", "technical", "journalistic",
    "narrative_essay", "ai_instructions", "blog", "software_spec"
]
```

2. **DocType** (rilevamento automatico dal Planner — §01 canonical):
```python
DocType = Literal[
    "scientific_report", "business_report", "technical_documentation",
    "journalistic", "narrative_essay", "ai_instructions", "blog",
    "software_spec"
]
```

- `StyleProfile` è ciò che l'utente sceglie nel config
- `DocType` è ciò che il Planner rileva automaticamente
- Mapping: `academic↔scientific_report`, `business↔business_report`, `technical↔technical_documentation`
- `"functional_spec"` e `"technical_spec"` di §24.2 NON sono valori validi — sono artefatti del Pipeline Orchestrator (§31) e NON devono apparire come StyleProfile

---

### C03 — Config schema: root-level DRSConfig (§03) vs nested DRSConfig (§29)

| File | Struttura |
|------|-----------|
| `03_input_config.md` | `DRSConfig(topic, target_words, style_profile, max_budget_dollars, models, convergence, ...)` — flat/mixed |
| `29_yaml_config.md` | `DRSConfig(user: UserConfig, models: ModelsConfig, convergence: ConvergenceConfig, ...)` — nested |

**RISOLUZIONE:** Sono **due modelli distinti** per scopi diversi:
- **§03 `DRSConfig`** → Modello API input (REST endpoint `POST /v1/runs`). Ha `topic` al root level. Implementare come `src/models/config.py`
- **§29 `DRSConfig`** → Modello YAML file config. Ha sezioni nested `user/models/convergence`. Implementare come `src/config/schema.py`

Al preflight, entrambi vengono normalizzati nel `DocumentState.config: dict` uniformato. L'implementazione deve supportare entrambi gli input format.

---

### C04 — Jury Factual tier3: `perplexity/sonar-pro` vs `openai/gpt-4o-search-preview`

| File | judge_f3 / tier3 |
|------|-----------------|
| `08_jury_system.md` §8.2 MODEL table | `perplexity/sonar-pro` (tier3) |
| `08_jury_system.md` §8.5 JURY_TIERS | `"tier3": "perplexity/sonar-pro"` |
| `28_llm_assignments.md` §28.2 | `judge_f3 = openai/gpt-4o-search-preview` |
| `29_yaml_config.md` §29.2 | `tier3: "perplexity/sonar-pro"` |

**RISOLUZIONE:** §28.2 è canonical per model assignments.
- **Per-slot primary** (§28.2): `judge_f1=perplexity/sonar`, `judge_f2=google/gemini-2.5-flash`, `judge_f3=openai/gpt-4o-search-preview`
- **Tier fallback** (§08.5): define la sequenza di fallback quando il primary per quello slot fallisce
- I Factual judges NON richiedono decorrelazione per slot (usano la stessa tier cascade). Tuttavia il primary effettivo per f3 è `openai/gpt-4o-search-preview` (Bing grounding, decorrelato da Google).
- §08 e §29 YAML devono aggiornare tier3 a `openai/gpt-4o-search-preview` per coerenza con §28.2

---

### C05 — Style jury: slot assignment (§28.2) vs tier order (§08.5)

| File | Slot primari |
|------|-------------|
| `28_llm_assignments.md` §28.2 | s1=`openai/gpt-4.5`, s2=`mistral/mistral-large-2411`, s3=`meta/llama-3.3-70b-instruct` |
| `08_jury_system.md` §8.3/§8.5 | tier1=`meta/llama-3.3-70b-instruct`, tier2=`mistral/mistral-large-2411`, tier3=`openai/gpt-4.5` |

**RISOLUZIONE:** A differenza dei Reasoning judges, i Factual e Style juries usano una **shared tier cascade** (tutti gli slot F/S usano lo stesso modello). Quindi tier1/tier2/tier3 sono la sequenza di cascading economico:
- **Tier1** (cheapest, chiamato per primo): `meta/llama-3.3-70b-instruct` ← §08.5 canonical per cascading
- **Tier2** (on disagreement): `mistral/mistral-large-2411`
- **Tier3** (only if needed): `openai/gpt-4.5`

§28.2 per-slot S assignments (s1/s2/s3) sono per epistemic decorrelation quando `jury_size=3`. La **tier cascade** di §08.5 governa l'ordine economico di invocazione. Implementazione: tutti e 3 gli slot S iniziano con tier1; cascading a tier2/tier3 solo se non unanimi.

---

### C06 — max_sources_per_section default: 12 vs 15 vs 20

| File | Default |
|------|---------|
| `05_agents.md` §5.2 Researcher | `max_sources: int # default 12` |
| `29_yaml_config.md` §29.4 | `max_sources_per_section: 15` |
| `03_input_config.md` §3.2 | `max_sources_per_section: 20` |

**RISOLUZIONE:** §29 è canonical per YAML defaults → **15**.
- §05.2 Researcher rispetta il parametro dal config, non usa un default hardcoded
- §03 ha un default diverso perché è il modello API (più permissivo)
- Runtime: il valore è sempre letto da `config.sources.max_sources_per_section`

---

### C07 — Writer fallback chain: fallback[2] diverge

| File | Fallback sequence |
|------|-------------------|
| `05_agents.md` §5.7 | `anthropic/claude-sonnet-4 → google/gemini-2.5-pro` |
| `03_input_config.md` §3.2 | `["anthropic/claude-sonnet-4", "openai/gpt-4.5"]` |
| `28_llm_assignments.md` §28.2 | `anthropic/claude-sonnet-4 → google/gemini-2.5-pro` |
| `29_yaml_config.md` §29.2 | `["anthropic/claude-sonnet-4", "google/gemini-2.5-pro"]` |

**RISOLUZIONE:** §28.2 è canonical → `["anthropic/claude-sonnet-4", "google/gemini-2.5-pro"]`

---

### C08 — Field name: `synthesized_sources` (§04) vs `compressed_corpus` (§05.6)

| File | Field |
|------|-------|
| `04_architecture.md` §4.6 DocumentState | `synthesized_sources: str` |
| `05_agents.md` §5.6 SourceSynthesizer OUTPUT | `compressed_corpus: str` |

**RISOLUZIONE:** §04.6 è canonical per DocumentState field names → il campo è `synthesized_sources`.
- §05.6 produce `compressed_corpus` come output locale dell'agente
- Il valore viene scritto nel campo `synthesized_sources` del DocumentState
- L'implementazione del nodo SourceSynthesizer mapperà: `return {"synthesized_sources": compressed_corpus}`

---

### C09 — PrivacyMode enum values

| File | Values |
|------|--------|
| `03_input_config.md` §3.1 | `"standard", "enhanced", "strict", "self_hosted"` |
| `02_design_principles.md` §2.10 | `"standard", "enhanced", "strict", "self_hosted"` |
| `33_tech_stack.md` §33 env var | `PRIVACY_MODE=cloud # cloud|self_hosted|hybrid|strict` |

**RISOLUZIONE:** §03 + §02 sono canonical (Pydantic schema livello applicazione):
```python
PrivacyMode = Literal["standard", "enhanced", "strict", "self_hosted"]
```
- Il valore env var `cloud` in §33 è un alias legacy per `standard`
- `hybrid` non è un valore valido — probabilmente intent era `enhanced`
- Mapping env: `cloud→standard`, `hybrid→enhanced`

---

### C10 — CSS panel threshold naming: `css_panel_trigger` vs `css_panel_threshold`

| File | Nome campo |
|------|-----------|
| `09_css_aggregator.md` §9.3 | `css_panel_trigger` (in THRESHOLD_TABLE) |
| `09_css_aggregator.md` §9.4 | `thresholds["css_panel_trigger"]` |
| `04_architecture.md` §4.6 BudgetState | `css_panel_threshold: float` |
| `29_yaml_config.md` §29.3 | `css_panel_threshold: 0.50` |
| `03_input_config.md` §3.2 | `css_panel_trigger: float` |

**RISOLUZIONE:** Due naming conventions coesistono:
- **THRESHOLD_TABLE** (§09, data source): usa `css_panel_trigger`
- **BudgetState** (§04, runtime State): usa `css_panel_threshold`
- **YAML config** (§29): usa `css_panel_threshold`

Regola: `css_panel_trigger` è il nome nella THRESHOLD_TABLE; `css_panel_threshold` è il nome nel BudgetState e config YAML. `populate_budget_thresholds()` copia `THRESHOLD_TABLE["css_panel_trigger"]` → `BudgetState["css_panel_threshold"]`. Entrambi i nomi sono validi nel loro contesto.

---

### C11 — Document status vs Run status vs DocumentState status

| File | Contesto | Valori validi |
|------|----------|---------------|
| `04_architecture.md` §4.6 | `DocumentState.status` | `"initializing","running","paused","awaiting_approval","completed","failed","cancelled"` |
| `21_persistence.md` §21.1 | `documents.status` (DB) | `"draft","partial","complete","failed"` |
| `21_persistence.md` §21.1 | `runs.status` (DB) | `"initializing","running","paused","awaiting_approval","completed","failed","cancelled","orphaned"` |

**RISOLUZIONE:** Sono tre enum distinti per tre entità diverse:
- `DocumentState.status` = stato corrente del run LangGraph (7 valori)
- `runs.status` = stato del run nel DB, include `"orphaned"` per crash detection (8 valori)
- `documents.status` = lifecycle del documento aggregato (4 valori: draft→partial→complete|failed)

`DocumentState.status` e `runs.status` sono quasi identici; `runs.status` aggiunge `"orphaned"`.

---

### C12 — target_words min validation: `ge=500` + check `< 100`

**File:** `03_input_config.md` §3.3

Il Pydantic field ha `ge=500` (Field constraint) ma il `model_validator` controlla `target_words < 100`. Con `ge=500`, il valore non può mai essere `< 100`, rendendo quel check dead code.

**RISOLUZIONE:** Rimuovere il check `< 100` nel validator. Il vincolo effettivo è `ge=500` (Pydantic field). Se serve abbassare il minimo, modificare il Field a `ge=100` e rimuovere il validator — ma §01 e §29 confermano `ge=500`.

---

### C13 — CoherenceConflict: field names divergenti

| File | Fields |
|------|--------|
| `04_architecture.md` §4.6 CoherenceConflict | `section_a_idx: int, section_b_idx: int, claim_a: str, claim_b: str` |
| `05_agents.md` §5.17 CoherenceGuard output | `claim_new: str, claim_existing: str, existing_section_index: int` |

**RISOLUZIONE:** §04.6 è canonical per il TypedDict. §05.17 descrive il formato interno dell'agente. L'implementazione del nodo CoherenceGuard DEVE mappare:
```python
CoherenceConflict(
    section_a_idx=current_section_idx,   # "new"
    section_b_idx=existing_section_index, # "existing"  
    claim_a=claim_new,
    claim_b=claim_existing,
    ...
)
```

---

### C14 — Quality preset casing: `"economy"` vs `"Economy"`

| File | Casing |
|------|--------|
| `07_mixture_of_writers.md` §7.1 | `quality_preset != "economy"` (lowercase) |
| `04_architecture.md` §4.6 | `quality_preset: Literal["Economy", "Balanced", "Premium"]` (capitalized) |
| `19_budget_controller.md` §19.2 | `Regime = Literal["Economy", "Balanced", "Premium"]` (capitalized) |
| `29_yaml_config.md` §29.1 | `quality_preset: "balanced"` (lowercase) |
| `09_css_aggregator.md` §9.3 | `THRESHOLD_TABLE` keys: `"economy"`, `"balanced"`, `"premium"` (lowercase) |

**RISOLUZIONE:** YAML config usa lowercase (§29 canonical per input utente). Internal State usa capitalized (§04 canonical per DocumentState). Regola implementativa:
- **Input/Config/YAML**: lowercase (`"economy"`, `"balanced"`, `"premium"`)
- **DocumentState/BudgetState**: `Literal["Economy", "Balanced", "Premium"]`
- **THRESHOLD_TABLE keys**: lowercase (perché `.lower()` viene usato nel lookup)
- Tutti i confronti devono usare `.lower()` per sicurezza

---

### C15 — LengthAdjuster assente da §28.2 Model Assignment Table

**File:** `05_agents.md` §5.22 definisce LengthAdjuster con `MODEL: anthropic/claude-opus-4-5`, ma §28.2 non lo elenca.

**RISOLUZIONE:** Aggiungere all'implementazione:
```python
"length_adjuster": {
    "primary": "anthropic/claude-opus-4-5",
    "fallbacks": ["anthropic/claude-sonnet-4", "google/gemini-2.5-pro"]
}
```

---

### C16 — JudgeVerdict dimension_scores: `dict[str,float]` vs typed `DimensionScores`

| File | Tipo |
|------|------|
| `04_architecture.md` §4.6 | `dimension_scores: dict[str, float]` |
| `08_jury_system.md` §8.6 | `dimension_scores: DimensionScores` (Pydantic model con 12 campi Optional) |

**RISOLUZIONE:** §08.6 `DimensionScores` è il modello canonico per la validazione Pydantic. §04.6 `dict[str, float]` è la rappresentazione semplificata nel TypedDict per il transport nello State. Implementazione:
- `src/models/verdict.py` → usa `DimensionScores` (Pydantic, §08.6)
- `src/graph/state.py` → `dimension_scores: dict[str, float]` (TypedDict, §04.6)
- Serializzazione: `verdict.dimension_scores.model_dump(exclude_none=True)` → dict

---

### C17 — API RunCreateRequest style_profile includes invalid values

**File:** `24_api.md` §24.2 include `"functional_spec"` e `"technical_spec"` nel Literal per `style_profile`.

**RISOLUZIONE:** Questi valori NON sono StyleProfile validi. Sono prodotti dal Pipeline Orchestrator (§31) per uso interno. Il Literal nell'API endpoint deve essere:
```python
style_profile: Literal[
    "academic", "business", "technical",
    "journalistic", "narrative_essay", "ai_instructions", 
    "blog", "software_spec"
]
```

---

### C18 — API target_words minimum: 1000 vs 500

| File | Minimo |
|------|--------|
| `24_api.md` §24.2 RunCreateRequest | `target_words: int # 1000–50000` |
| `03_input_config.md` §3.3 | `ge=500` |
| `29_yaml_config.md` §29.6 | `ge=500` |
| `01_vision.md` §1.4 | `ge=500` |

**RISOLUZIONE:** §01 + §29 canonical → minimo è `500`. §24 API docstring errato.

---

## 0.3 Resolved Values — Quick Reference

### CSS Thresholds (from §9.3 THRESHOLD_TABLE — SINGLE SOURCE OF TRUTH)

| Regime | css_content_threshold | css_style_threshold | css_panel_trigger |
|--------|----------------------|--------------------|--------------------|
| Economy | 0.65 | 0.75 | 0.40 |
| Balanced | 0.70 | 0.80 | 0.50 |
| Premium | 0.78 | 0.85 | 0.55 |

### Budget Regime Parameters (from §19.2)

| Regime | budget_per_word | max_iterations | jury_size | mow_enabled |
|--------|----------------|---------------|-----------|-------------|
| Economy | < $0.002 | 2 | 1 | False |
| Balanced | $0.002–$0.005 | 4 | 2 | True |
| Premium | > $0.005 | 8 | 3 | True |

### Jury Weights (from §9.2)

```python
JURY_WEIGHTS = {"reasoning": 0.35, "factual": 0.45, "style": 0.20}
```

### Reasoning Judge Slot Assignments (from §28.2 — per-slot decorrelated)

| Slot | Primary | Fallback 1 | Fallback 2 |
|------|---------|-----------|-----------|
| R1 | `deepseek/deepseek-r1` | `openai/o3-mini` | `qwen/qwq-32b` |
| R2 | `openai/o3-mini` | `deepseek/deepseek-r1` | `qwen/qwq-32b` |
| R3 | `qwen/qwq-32b` | `deepseek/deepseek-r1` | `openai/o3-mini` |

### Aggregator Route Literals (from §9.4)

```python
AggregatorRoute = Literal[
    "approved", "force_approve", "fail_style", "fail_missing_ev",
    "fail_reflector", "panel", "veto", "budget_hard_stop"
]
```
Priority order: `force_approve > budget_hard_stop > veto > panel > missing_ev > content_gate > style_pass > fail_reflector`

### Reflector Route (from §12.5)

```python
# SURGICAL/PARTIAL → oscillation_check → span_editor|writer|escalate_human
# FULL → await_human (bypass oscillation)
```

### MoW Topology (from §7.6 — AUTHORITATIVE)

- MoW è **interamente interno** al nodo `writer`
- I nodi `writer_a`, `writer_b`, `writer_c`, `jury_multi_draft`, `fusor` NON esistono come nodi graph
- Il grafo vede SOLO `writer → post_draft_analyzer` (edge incondizionale)

---

## 0.4 Cross-File Consistency Rules

1. **Qualsiasi pricing** → DEVE importare da `src/llm/pricing.py` (§28.4 canonical). Mai hardcodare prezzi.
2. **Qualsiasi threshold CSS** → DEVE leggere da `THRESHOLD_TABLE` (§09.3) via `populate_budget_thresholds()`. Mai hardcodare soglie.
3. **Qualsiasi routing function** → esiste in UN solo file. Non duplicare.
4. **Qualsiasi model assignment** → §28.2 è canonical. §08/§29 definiscono fallback/tier cascade.
5. **DocumentState fields** → §04.6 è canonical. Agenti producono output che viene mappato ai nomi dei campi di §04.6.

<!-- SPEC_COMPLETE -->
