# Direttiva 03 — Budget & Thresholds

## Obiettivo

Implementare il Budget Estimator (pre-run), il Real-Time Cost Tracker, il regime system (Economy/Balanced/Premium), e le dynamic savings strategies. Il budget è il vincolo inviolabile del sistema (§2.1).

## Pre-requisiti

- Fase 1 completata (`src/budget/regime.py` con THRESHOLD_TABLE e REGIME_PARAMS)
- Fase 2 completata (PostgreSQL `costs` table, Redis cost accumulator)

## Spec da Leggere

| File | Sezione | Cosa estrarre |
|------|---------|--------------|
| `output/19_budget_controller.md` | §19.0 | `estimate_run_cost()` formula completa, `BudgetEstimate` dataclass |
| `output/19_budget_controller.md` | §19.1 | BudgetEstimator agent spec: INPUT/OUTPUT/CONSTRAINTS |
| `output/19_budget_controller.md` | §19.2 | REGIME_PARAMS table con tutti i levers |
| `output/19_budget_controller.md` | §19.3 | Real-Time Cost Tracker: `CostEntry`, alarm texts, counter schema |
| `output/19_budget_controller.md` | §19.4 | `apply_dynamic_savings()` — trigger actions at 70%/90%/100% |
| `output/19_budget_controller.md` | §19.5 | BudgetController node spec, adaptive levers table, `force_approve` mechanism |
| `output/09_css_aggregator.md` | §9.3 | `THRESHOLD_TABLE` (SINGLE SOURCE OF TRUTH), `populate_budget_thresholds()` |
| `output/28_llm_assignments.md` | §28.4 | `MODEL_PRICING`, `cost_usd()`, budget estimator integration |
| `output/02_design_principles.md` | §2.1 | Budget-First principle constraints |

## Conflitti da Applicare

- **C10**: `css_panel_trigger` (in THRESHOLD_TABLE) → `css_panel_threshold` (in BudgetState)
- **C14**: THRESHOLD_TABLE keys sono lowercase; BudgetState/DocumentState usa capitalized

## Output Atteso

### File da creare

```
src/budget/estimator.py          # estimate_run_cost(), BudgetEstimate
src/budget/tracker.py            # RealTimeCostTracker, record_cost(), alarm logic
src/budget/thresholds.py         # populate_budget_thresholds()
src/graph/nodes/budget_controller.py  # BudgetController graph node
```

### `src/budget/estimator.py` — Funzioni richieste

```python
def estimate_run_cost(n_sections, target_words, max_budget_usd, ...) -> BudgetEstimate: ...
def _derive_regime(budget_per_word: float) -> str: ...
# MUST block if estimated > max_budget * 0.80
# MUST call populate_budget_thresholds() after regime derivation
```

### `src/budget/tracker.py` — Funzioni richieste

```python
async def record_cost_entry(entry: CostEntry, budget: BudgetState, db, redis) -> BudgetState: ...
def apply_dynamic_savings(budget: BudgetState) -> BudgetState: ...
# 70% → downgrade writer model, jury_size -= 1
# 90% → css thresholds to Economy floor, max_iterations=1, jury_size=1, disable MoW
# 100% → hard_stop_fired = True → route to publisher
# Section cost > $15 → BUDGET_SECTION_ANOMALY → await_human
```

### `src/graph/nodes/budget_controller.py` — Funzioni richieste

```python
async def budget_controller_node(state: DocumentState) -> dict: ...
# MUST call apply_dynamic_savings()
# MUST re-project final cost
# MUST re-call populate_budget_thresholds() after regime change
# MUST set force_approve if current_iteration >= max_iterations
```

## Script di Validazione

```bash
python -c "
from src.budget.regime import THRESHOLD_TABLE, REGIME_PARAMS
assert 'economy' in THRESHOLD_TABLE
assert THRESHOLD_TABLE['economy']['css_content_threshold'] == 0.65
assert THRESHOLD_TABLE['premium']['css_style_threshold'] == 0.85
assert REGIME_PARAMS['Economy']['max_iterations'] == 2
print('OK: budget regime tables valid')
"
```
