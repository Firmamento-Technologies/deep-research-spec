# Direttiva 01 — State & Types

## Obiettivo

Implementare tutti i TypedDict, Pydantic models, e type definitions che costituiscono il contratto di dati dell'intero sistema. Nessun nodo graph può essere implementato senza questi tipi.

## Pre-requisiti

- Leggi `output/00_conflict_resolutions.md` (intero file)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/04_architecture.md` | §4.6 completo | `DocumentState`, `BudgetState`, `OutlineSection`, `Source`, `JudgeVerdict`, `AggregatorVerdict`, `ReflectorOutput`, `StyleLintViolation`, `CoherenceConflict` |
| `output/08_jury_system.md` | §8.0 tipi + §8.6 VerdictJSON | `VerdictJSON`, `DimensionScores`, `ExternalSource`, `JurySlot`, `JuryTier`, `VetoCategory`, `Confidence`, `Outcome` |
| `output/05_agents.md` | §5 Shared Types | `Severity`, `Scope`, `AgentOutcome`, `ReflectorFeedback`, `StyleViolation` |
| `output/10_minority_veto.md` | §10.1 + §10.3 | `L1VetoVerdict`, `RogueJudgeFlag`, `RogueJudgeReport` |
| `output/07_mixture_of_writers.md` | §7.4 + §7.5 | `BestElement`, `FusedDraft`, `PerDraftVerdict`, `MoWState` |
| `output/29_yaml_config.md` | §29.6 completo | `DRSConfig` (YAML), `UserConfig`, `ModelsConfig`, `ConvergenceConfig`, `SourcesConfig`, `StyleConfig` + tutti i leaf models |
| `output/03_input_config.md` | §3.1–§3.3 | `DRSConfig` (API), `ModelsConfig`, `ConvergenceConfig`, `SourcesConfig` |
| `output/19_budget_controller.md` | §19.0 + §19.3 | `BudgetEstimate`, `CostEntry` |
| `output/09_css_aggregator.md` | §9.3 + §9.8 | `THRESHOLD_TABLE`, `SectionCSSReport` |
| `output/24_api.md` | §24.2–§24.3 | `RunCreateRequest/Response`, SSE event types |

## Conflitti da Applicare

- **C01**: `source_type` → usa `"web"`, `"upload"` (non `"general"`, `"uploaded"`)
- **C02**: `StyleProfile` usa nomi corti (`"academic"`, `"business"`, `"technical"`)
- **C08**: Campo DocumentState è `synthesized_sources` (non `compressed_corpus`)
- **C14**: DocumentState usa `Literal["Economy", "Balanced", "Premium"]`; YAML config usa lowercase
- **C16**: `dimension_scores` è `dict[str, float]` nel TypedDict state, `DimensionScores` nel Pydantic model

## Output Atteso

### File da creare

```
src/graph/state.py              # DocumentState + tutti i sub-TypedDict
src/models/verdict.py           # VerdictJSON, DimensionScores (Pydantic)
src/models/source.py            # Source, CitationEntry (Pydantic)
src/models/config.py            # DRSConfig API input model (§03)
src/models/document.py          # RunCreateRequest/Response, SSE events
src/config/schema.py            # DRSConfig YAML model (§29.6)
src/budget/regime.py            # THRESHOLD_TABLE, REGIME_PARAMS
src/llm/pricing.py              # MODEL_PRICING dict (§28.4)
```

### `src/graph/state.py` — Contenuto richiesto

```python
from __future__ import annotations
from typing import TypedDict, Annotated, Any, Literal
from langgraph.graph.message import add_messages

class BudgetState(TypedDict): ...      # 13 campi da §4.6
class OutlineSection(TypedDict): ...   # 5 campi
class Source(TypedDict): ...           # 13 campi — source_type usa "web"/"upload"
class JudgeVerdict(TypedDict): ...     # 12 campi
class AggregatorVerdict(TypedDict): ...# 5 campi
class ReflectorOutput(TypedDict): ...  # 3 campi
class StyleLintViolation(TypedDict): ...# 7 campi
class CoherenceConflict(TypedDict): ...# 6 campi

class DocumentState(TypedDict):
    # 40+ campi — copia ESATTA di §4.6
    doc_id: str
    thread_id: str
    user_id: str
    status: Literal["initializing","running","paused","awaiting_approval","completed","failed","cancelled"]
    # ... tutti i campi da §4.6
    companion_messages: Annotated[list, add_messages]
    # ... etc
```

### `src/llm/pricing.py` — Contenuto richiesto

Copia ESATTA della `MODEL_PRICING` dict da §28.4. Include la funzione `cost_usd()`.

### `src/budget/regime.py` — Contenuto richiesto

```python
THRESHOLD_TABLE: dict[str, dict[str, float]]  # da §9.3
REGIME_PARAMS: dict[str, dict]                 # da §19.2
def derive_quality_preset(budget_per_word: float) -> str: ...
def populate_budget_thresholds(budget: dict, config: dict) -> dict: ...
```

## Script di Validazione

```bash
python execution/validate_state.py
```

Verifica che `src/graph/state.py`:
- Contenga TUTTI i campi di DocumentState elencati in §4.6
- Contenga tutti i sub-TypedDict (BudgetState, Source, etc.)
- Usi i tipi corretti per ogni campo
- Importi `add_messages` per `companion_messages`
