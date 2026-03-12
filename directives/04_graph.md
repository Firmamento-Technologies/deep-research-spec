# Direttiva 04 — Graph & Routing

## Obiettivo

Implementare `build_graph()` con tutti i nodi registrati, tutti gli edge (condizionali e fissi), e tutte le routing functions. Dopo questa fase, il grafo LangGraph compila con un mock checkpointer e tutti i percorsi di routing sono testati.

## Pre-requisiti

- Fase 1 completata (`src/graph/state.py` con `DocumentState`)
- Fase 2 completata (`src/storage/checkpointer.py`)
- Fase 3 completata (`src/budget/regime.py`)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/04_architecture.md` | §4.1 | Phase A flow: preflight → budget_estimator → planner → await_outline |
| `output/04_architecture.md` | §4.2 | Phase B flow completo: section loop con tutti i branch |
| `output/04_architecture.md` | §4.3 | Phase C: post_qa → length_adjuster → publisher |
| `output/04_architecture.md` | §4.4 | Phase D: publisher → END |
| `output/04_architecture.md` | §4.5 completo | NODES list (30 nodi), TUTTE le routing functions, `build_graph()` completo con `add_edge()` e `add_conditional_edges()` |
| `output/09_css_aggregator.md` | §9.4 completo | `route_after_aggregator()` — CANONICAL, priority order, return literals |
| `output/09_css_aggregator.md` | §9.5 | `route_after_panel_internal()` — panel self-loop |
| `output/05_agents.md` | §12.5 | `route_after_reflector()` e `route_after_oscillation()` — canonical |

## Conflitti da Applicare

- **§7.6 AUTHORITATIVE**: MoW nodi (`writer_a`, `writer_b`, `writer_c`, `jury_multi_draft`, `fusor`) NON esistono come nodi graph
- Edge `writer → post_draft_analyzer` è INCONDIZIONALE
- `route_after_aggregator()` è definita SOLO in §9.4 — non duplicare
- `force_approve` è il PRIMO check in `route_after_aggregator()` (prima di budget_hard_stop)

## Output Atteso

### File da creare

```
src/graph/graph.py                   # build_graph(checkpointer) → CompiledGraph
src/graph/routers/outline_approval.py  # route_outline_approval(state)
src/graph/routers/post_aggregator.py   # route_after_aggregator(state) — §9.4 exact
src/graph/routers/post_reflector.py    # route_after_reflector(state) — §12.5 exact
src/graph/routers/post_oscillation.py  # route_after_oscillation(state)
src/graph/routers/post_coherence.py    # route_after_coherence(state)
src/graph/routers/next_section.py      # route_next_section(state)
src/graph/routers/budget_route.py      # route_budget(state)
src/graph/routers/style_lint.py        # route_style_lint(state)
src/graph/routers/post_draft_gap.py    # route_post_draft_gap(state)
src/graph/routers/post_qa.py          # route_post_qa(state)
src/graph/routers/panel_loop.py        # route_after_panel_internal(state)
```

### `src/graph/graph.py` — Struttura richiesta

```python
from langgraph.graph import StateGraph, END
from src.graph.state import DocumentState

NODES: list[str] = [
    "preflight", "budget_estimator", "planner", "await_outline",
    "researcher", "citation_manager", "citation_verifier",
    "source_sanitizer", "source_synthesizer",
    "writer", "post_draft_analyzer", "researcher_targeted",
    "style_linter", "style_fixer",
    "metrics_collector",
    "jury", "aggregator",
    "reflector", "span_editor", "diff_merger",
    "oscillation_check", "panel_discussion",
    "coherence_guard", "context_compressor", "section_checkpoint",
    "await_human", "budget_controller",
    "post_qa", "length_adjuster",
    "publisher", "feedback_collector",
]

def build_graph(checkpointer) -> "CompiledStateGraph":
    g = StateGraph(DocumentState)
    # Registra tutti i nodi (stub functions per ora)
    # Definisci TUTTI gli edge da §4.5:
    # Phase A: preflight → budget_estimator → planner → await_outline → (approved→researcher / rejected→planner)
    # Phase B: researcher → citation_manager → ... → writer → post_draft_analyzer → ...
    # ... tutte le conditional edges esattamente come in §4.5
    return g.compile(checkpointer=checkpointer)
```

### Routing Functions — Contratto di Return Types

```python
# route_after_aggregator → Literal["approved","force_approve","fail_style","fail_missing_ev","fail_reflector","panel","veto","budget_hard_stop"]
# route_after_reflector → Literal["oscillation_check","await_human"]
# route_after_oscillation → Literal["span_editor","writer","escalate_human"]
# route_outline_approval → Literal["approved","rejected"]
# route_post_draft_gap → Literal["gap","no_gap"]
# route_style_lint → Literal["violation","clean"]
# route_budget → Literal["continue","hard_stop"]
# route_after_coherence → Literal["no_conflict","soft_conflict","hard_conflict"]
# route_next_section → Literal["next_section","all_done"]
# route_post_qa → Literal["length_out_of_range","conflicts","ok"]
# route_after_panel_internal → Literal["panel_discussion","aggregator"]
```

## Script di Validazione

```bash
python execution/run_graph_compile.py   # Compila il grafo con mock checkpointer
python execution/test_routing.py        # Unit test su tutte le routing functions
```
