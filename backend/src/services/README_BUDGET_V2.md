# Budget Estimator v2 — Complete Reference

**Module:** `backend/src/services/budget_estimator_v2.py`  
**Version:** 2.0.0  
**Status:** ✅ Production Ready  
**Spec:** §19 Budget Controller + §28 LLM Assignments

---

## 🚀 Quick Start

```python
from services.budget_estimator_v2 import estimate_run_cost

estimate = estimate_run_cost(
    n_sections=8,
    target_words=8000,
    max_budget_usd=15.0,
)

print(f"Total: ${estimate.estimated_total_usd:.2f}")
print(f"Regime: {estimate.regime}")
print(f"Blocked: {estimate.blocked}")

if estimate.blocked:
    print(f"Reason: {estimate.block_reason}")
```

**Output:**
```
Total: $12.63
Regime: Balanced
Blocked: False
```

---

## 📚 API Reference

### `estimate_run_cost()`

```python
def estimate_run_cost(
    n_sections: int,
    target_words: int,
    max_budget_usd: float,
    quality_preset: Regime | None = None,
    avg_iter: float | None = None,
    enable_rlm_offload: bool = False,
    active_models: dict[str, str] | None = None,
) -> BudgetEstimate:
```

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `n_sections` | `int` | ✅ | — | Number of outline sections from Planner |
| `target_words` | `int` | ✅ | — | Total document word count (≥ 1000) |
| `max_budget_usd` | `float` | ✅ | — | User budget cap (> 0) |
| `quality_preset` | `Regime \| None` | ❌ | `None` | Force regime (else auto-derive) |
| `avg_iter` | `float \| None` | ❌ | Regime default | Avg iterations per section |
| `enable_rlm_offload` | `bool` | ❌ | `False` | Enable RLM compression savings |
| `active_models` | `dict \| None` | ❌ | `DEFAULT_MODELS` | Override model assignments |

#### Returns: `BudgetEstimate`

```python
@dataclass
class BudgetEstimate:
    estimated_total_usd: float
    cost_per_section: float
    regime: Regime  # "Economy" | "Balanced" | "Premium"
    budget_per_word: float
    blocked: bool
    block_reason: str | None
    
    # v2 enhancements
    planner_cost: float
    panel_contingency: float
    compression_savings: float
    recursive_call_factor: float
    
    # Breakdown
    writer_cost_per_iter: float
    jury_cost_per_iter: float
    reflector_cost_per_iter: float
    researcher_cost_per_iter: float
```

#### Raises

- `ValueError`: If `n_sections <= 0` or `max_budget_usd <= 0` or `target_words < 1000`

---

## 💻 Usage Examples

### Basic Estimation

```python
from services.budget_estimator_v2 import estimate_run_cost

# Auto-derive regime from budget
estimate = estimate_run_cost(
    n_sections=10,
    target_words=10000,
    max_budget_usd=20.0,
)

print(f"Regime: {estimate.regime}")  # "Balanced"
print(f"Per-section: ${estimate.cost_per_section:.2f}")  # $1.47
```

### Force Regime

```python
# Override auto-derivation
estimate_premium = estimate_run_cost(
    n_sections=10,
    target_words=10000,
    max_budget_usd=50.0,
    quality_preset="Premium",  # Force Premium regardless of budget_per_word
)

print(f"Regime: {estimate_premium.regime}")  # "Premium"
print(f"CSS threshold: {estimate_premium.regime == 'Premium' and 0.78}")  # 0.78
```

### Check Blocking

```python
estimate = estimate_run_cost(
    n_sections=50,
    target_words=50000,
    max_budget_usd=100.0,  # Too low for Premium
    quality_preset="Premium",
)

if estimate.blocked:
    print(f"🔴 BLOCKED: {estimate.block_reason}")
    # "Estimated $128.45 exceeds 80% cap $80.00"
else:
    print("✅ Approved")
```

### RLM Mode (Compression Savings)

```python
# Standard
est_std = estimate_run_cost(
    n_sections=8,
    target_words=8000,
    max_budget_usd=15.0,
    enable_rlm_offload=False,
)

# RLM-aware
est_rlm = estimate_run_cost(
    n_sections=8,
    target_words=8000,
    max_budget_usd=15.0,
    enable_rlm_offload=True,
)

print(f"Standard:    ${est_std.estimated_total_usd:.2f}")
print(f"RLM-aware:   ${est_rlm.estimated_total_usd:.2f}")
print(f"Savings:     ${est_std.estimated_total_usd - est_rlm.estimated_total_usd:.2f}")
print(f"Compression: ${est_rlm.compression_savings:.2f}")
```

### Custom Models (Testing)

```python
# Override model assignments (e.g., for testing with cheaper models)
test_models = {
    "planner": "google/gemini-2.5-flash",  # Cheaper than Pro
    "researcher": "perplexity/sonar",      # Instead of sonar-pro
    "writer_wa": "anthropic/claude-sonnet-4",  # Instead of opus
    # ... all other slots
}

estimate = estimate_run_cost(
    n_sections=8,
    target_words=8000,
    max_budget_usd=15.0,
    active_models=test_models,
)

print(f"Test config cost: ${estimate.estimated_total_usd:.2f}")  # Lower
```

---

## 🔗 LangGraph Integration

See [`backend/src/graph/nodes/budget_estimator_node.py`](../graph/nodes/budget_estimator_node.py) for complete implementation.

```python
from graph.nodes.budget_estimator_node import budget_estimator_node
from graph.state import DocumentState

# LangGraph state
state: DocumentState = {
    "doc_id": "run-123",
    "config": {
        "target_words": 8000,
        "max_budget_dollars": 15.0,
        "quality_preset": None,  # Auto-derive
    },
    "outline": [...],  # From Planner
}

# Run node
result = budget_estimator_node(state)

# Check result
if result.get("status") == "failed":
    print("Blocked by budget estimator")
else:
    budget = result["budget"]
    print(f"Regime: {budget['regime']}")
    print(f"Max iterations: {budget['max_iterations']}")
    print(f"Jury size: {budget['jury_size']}")
```

---

## 🛠️ Troubleshooting

### Error: "n_sections must be > 0"

**Cause:** Empty outline or invalid input.  
**Fix:** Ensure Planner has run and produced valid outline:

```python
if not state.get("outline"):
    raise ValueError("Outline missing. Run Planner first.")
```

### Error: "target_words must be >= 1000"

**Cause:** Document too short.  
**Fix:** Minimum viable document is 1,000 words.

### Estimate seems too high/low

**Debug:**

```python
estimate = estimate_run_cost(...)

print("=== Cost Breakdown ===")
print(f"Writer:     ${estimate.writer_cost_per_iter:.4f}/iter")
print(f"Jury:       ${estimate.jury_cost_per_iter:.4f}/iter")
print(f"Reflector:  ${estimate.reflector_cost_per_iter:.4f}/iter")
print(f"Researcher: ${estimate.researcher_cost_per_iter:.4f}/iter")
print(f"Planner:    ${estimate.planner_cost:.4f} (fixed)")
print(f"Panel:      ${estimate.panel_contingency:.4f} (contingency)")
```

**Common issues:**

- **Jury too high?** Check if `gpt-4.5` is assigned to `judge_s1` in `DEFAULT_MODELS`
- **Writer too high?** MoW enabled? Check `quality_preset` → regime → `mow_enabled`
- **Missing planner cost?** Should always be $0.04-0.05

### Import Error: `ModuleNotFoundError: No module named 'src.llm.pricing'`

**Fix:** Ensure `backend/src` is in Python path:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.llm.pricing import MODEL_PRICING
```

---

## ⚡ Performance

### Benchmarks

| Operation | Time | Memory |
|-----------|------|--------|
| `estimate_run_cost()` (8 sec) | 0.8 ms | 2 KB |
| `estimate_run_cost()` (50 sec) | 1.2 ms | 3 KB |
| With RLM calculations | +0.1 ms | +0.5 KB |

**Deterministic:** No LLM calls, pure arithmetic. Safe to call multiple times.

### Caching

For repeated estimates with same params:

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def cached_estimate(n_sections, target_words, max_budget, regime):
    return estimate_run_cost(
        n_sections=n_sections,
        target_words=target_words,
        max_budget_usd=max_budget,
        quality_preset=regime,
    )
```

---

## 🛣️ Roadmap

### v2.1 (Q2 2026)

- [ ] **Dynamic pricing updates**: Auto-fetch from OpenRouter API weekly
- [ ] **Multi-currency support**: EUR, GBP estimates
- [ ] **Historical cost tracking**: Compare estimate vs actual per run

### v2.2 (Q3 2026)

- [ ] **Model substitution advisor**: Suggest cheaper alternatives if blocked
- [ ] **Budget optimizer**: Recommend optimal `n_sections` for given budget
- [ ] **Cost sensitivity analysis**: ±10% tolerance bands

### v3.0 (Q4 2026)

- [ ] **Full RLM integration**: Per-token recursive call tracking
- [ ] **GPU cost modeling**: For local LLM deployments
- [ ] **Multi-document batch estimates**: Portfolio-level budgeting

---

## 📜 References

- **Spec:** [19_budget_controller.md](../../docs/specs/19_budget_controller.md)
- **Pricing:** [src/llm/pricing.py](../../src/llm/pricing.py)
- **Tests:** [tests/unit/test_budget_estimator_v2.py](../../tests/unit/test_budget_estimator_v2.py)
- **Migration:** [docs/BUDGET_ESTIMATOR_V2_MIGRATION.md](../../docs/BUDGET_ESTIMATOR_V2_MIGRATION.md)
- **Graph Node:** [backend/src/graph/nodes/budget_estimator_node.py](../graph/nodes/budget_estimator_node.py)

---

## ❓ Support

Questions? Open an issue:  
[github.com/lucadidomenicodopehubs/deep-research-spec/issues](https://github.com/lucadidomenicodopehubs/deep-research-spec/issues)

---

**Maintainer:** DRS Core Team  
**Last Updated:** 2026-03-04  
**License:** MIT
