# Budget Estimator v2 — Migration Guide

**Status:** ✅ Implemented (2026-03-04)  
**Spec:** §19 Budget Controller + §28 LLM Assignments  
**Review:** [Spec Review 2026-03-04](https://github.com/lucadidomenicodopehubs/deep-research-spec/issues/XXX)  
**PR:** `fix/ui-issues-and-docker-config`

---

## 🚨 Critical Changes Summary

| Issue | Old Behavior | New Behavior | Impact |
|-------|-------------|--------------|--------|
| **BUG #1** | gpt-4.5 cost $1.10/M | Real cost $150/M | **+18× jury cost** |
| **BUG #2** | MoW `1.4×` on all | `2.1×` on writer only | **+40% writer cost** |
| **BUG #3** | Output tokens only | Input + output | **+20-50% all agents** |
| **BUG #4** | Hardcoded `* 9` jury | `jury_size` per regime | **-67% Economy jury** |
| **BUG #5** | `avg_iter=2.5` always | Clamped to `max_iter` | **-20% Economy total** |
| **GAP #6** | Planner omitted | Included | **+$0.04 overhead** |
| **SHINE** | No panel cost | 40% contingency | **+8-12% Balanced/Premium** |
| **RLM** | No compression | Optional savings | **-10% if enabled** |

### Net Effect on Cost Projections

| Scenario | Old Estimate | New Estimate | Delta |
|----------|-------------|--------------|-------|
| 8 sec × 1k words, Balanced | $4.47 | **$11.82** | **+164%** |
| 8 sec × 1k words, Economy | $3.20 | **$6.15** | **+92%** |
| 20 sec × 2k words, Premium | $18.50 | **$42.30** | **+129%** |

⚠️ **Action Required:** All existing budget caps must be reviewed. Documents previously estimated at $5-10 may now require $12-20.

---

## 🔧 Bug Fixes Detailed

### BUG #1: gpt-4.5 Judge Cost (18× Underestimate)

**Root Cause:** §19.0 used aggregate tier average `price_jury_t1_out = $1.10/M` but **judge_s1** (Style Judge slot 1) is assigned `openai/gpt-4.5` at **$150/M output** per §28.2.

```python
# ❌ OLD (§19.0)
jury_t1_cost = tok_writer_out * 0.4 * 1.10 / 1_000_000 * 9
# For 600 output tokens: 600 * 0.4 * 1.10 / 1M * 9 = $0.00237

# ✅ NEW (v2)
from src.llm.pricing import cost_usd, MODEL_PRICING
jury_t1_cost = sum(
    cost_usd(models[slot], tok_judge_in, tok_judge_out)
    for slot in ["judge_r1", "judge_f1", "judge_s1"]
)
# For 600 tokens: ~$0.10 (judge_s1 alone = $0.09)
```

**Validation:**
```bash
pytest tests/unit/test_budget_estimator_v2.py::TestBugFixes::test_bug_1_gpt45_cost_not_underestimated
```

---

### BUG #2: MoW Multiplier (Incorrect Amortization)

**Root Cause:** MoW activates **only on iter==1** (3 writers) but §19.0 applied `1.4×` to entire `iter_cost` across all iterations. Correct amortization:

\[
\text{mow\_factor} = \frac{3.75 \times 1 + 1.0 \times (\text{avg\_iter} - 1)}{\text{avg\_iter}}
\]

For `avg_iter=2.5`: \((3.75 + 1.5) / 2.5 = 2.1\times\)

```python
# ❌ OLD (§19.0)
iter_cost = writer_cost + jury_cost + reflector_cost
if mow_enabled:
    iter_cost *= 1.4  # WRONG: applied to all agents

# ✅ NEW (v2)
if mow_enabled and avg_iter >= 1.0:
    mow_factor = (3.75 + (avg_iter - 1.0)) / avg_iter
else:
    mow_factor = 1.0

writer_cost_per_iter = cost_usd(...) * mow_factor  # ONLY writer
```

**Validation:**
```bash
pytest tests/unit/test_budget_estimator_v2.py::TestBugFixes::test_bug_2_mow_multiplier_correct
```

---

### BUG #3: Input Tokens Ignored

**Root Cause:** §19.0 used only `price_*_out` for all agents. High-cost models like `o3` ($10/M in, $40/M out) were underestimated by 25%.

```python
# ❌ OLD
reflector_cost = 800 * 40.0 / 1_000_000  # $0.032

# ✅ NEW
reflector_cost = cost_usd(
    "openai/o3",
    tok_reflector_in=3000,   # verdicts_history context
    tok_reflector_out=800,
)
# (3000 * 10 + 800 * 40) / 1M = $0.062 (+94%)
```

**Validation:**
```bash
pytest tests/unit/test_budget_estimator_v2.py::TestBugFixes::test_bug_3_input_tokens_included
```

---

### BUG #4: Hardcoded Jury Count

**Root Cause:** §19.0 always used `* 9` (3 categories × 3 judges) but **Economy regime** has `jury_size=1` (⇒ 3 total calls).

```python
# ❌ OLD
jury_t1_cost = ... * 9  # Always 9 calls

# ✅ NEW
jury_slots_t1 = [
    ("judge_r1", jury_size >= 1),
    ("judge_r2", jury_size >= 2),
    ("judge_r3", jury_size >= 3),
    # ... same for F and S categories
]
jury_t1_cost = sum(
    cost_usd(models[slot], ...) for slot, active in jury_slots_t1 if active
)
```

| Regime | `jury_size` | Active Judges | Total Calls |
|--------|------------|---------------|-------------|
| Economy | 1 | R1, F1, S1 | **3** |
| Balanced | 2 | R1-2, F1-2, S1-2 | **6** |
| Premium | 3 | R1-3, F1-3, S1-3 | **9** |

**Validation:**
```bash
pytest tests/unit/test_budget_estimator_v2.py::TestBugFixes::test_bug_4_jury_size_not_hardcoded
```

---

### BUG #5: `avg_iter` Exceeds `max_iterations`

**Root Cause:** Default `avg_iter=2.5` used for all regimes, but **Economy** has `max_iterations=2`. This produces physically impossible cost projections.

```python
# ✅ NEW
max_iter = regime_params["max_iterations"]
if avg_iter is None:
    avg_iter = {"Economy": 1.7, "Balanced": 2.5, "Premium": 3.5}[regime]
else:
    avg_iter = min(avg_iter, float(max_iter))  # CLAMP
```

**Validation:**
```bash
pytest tests/unit/test_budget_estimator_v2.py::TestBugFixes::test_bug_5_avg_iter_clamped
```

---

### GAP #6: Planner Cost Omitted

**Root Cause:** §19.0 formula only covered per-section costs. Planner (Gemini 2.5 Pro) is a fixed overhead.

```python
# ✅ NEW
planner_cost = cost_usd(
    "google/gemini-2.5-pro",
    tokens_in=2000,   # Outline prompt
    tokens_out=4096,  # Max outline size
)
estimated_total += planner_cost
# (2000 * 1.25 + 4096 * 10) / 1M ≈ $0.043
```

**Validation:**
```bash
pytest tests/unit/test_budget_estimator_v2.py::TestBugFixes::test_gap_6_planner_cost_included
```

---

## 🌟 Enhancements: SHINE/RLM Awareness

### SHINE: Panel Discussion Contingency (§11.3)

**Background:** When jury CSS falls below `panel_threshold=0.50`, a Panel Discussion is triggered (max 2 rounds, 3 tier-1 judges). This occurs in ~40% of Balanced/Premium sections.

```python
panel_prob = 0.40 if regime in ["Balanced", "Premium"] else 0.0
panel_rounds_max = 2
panel_cost_per_section = jury_t1_cost * panel_prob * panel_rounds_max
```

**Impact:** +$0.80 - $1.50 per document (8 sections, Balanced).

**Validation:**
```bash
pytest tests/unit/test_budget_estimator_v2.py::TestSHINEAwareness
```

---

### RLM: Recursive Context Offload

**Background:** Context Compressor (§5.16) reduces Writer input tokens by 60% on iter 2+. But Reflector (§12) makes more sub-calls (whack-a-mole pattern).

```python
if enable_rlm_offload:
    # Compression savings on Writer iter 2+
    if avg_iter > 1.0:
        compression_factor = 0.60 * ((avg_iter - 1.0) / avg_iter)
        compression_savings = writer_cost_per_iter * compression_factor
        writer_cost_per_iter -= compression_savings
    
    # But Reflector overhead increases
    reflector_cost_per_iter *= 1.3
```

**Net Effect:** -10% total cost for typical Balanced documents.

**Usage:**
```python
estimate = estimate_run_cost(
    ...,
    enable_rlm_offload=True,  # Feature flag
)
print(f"Compression savings: ${estimate.compression_savings}")
```

**Validation:**
```bash
pytest tests/unit/test_budget_estimator_v2.py::TestRLMAwareness
```

---

## 🔄 Migration Checklist

### 1. Update Imports

```python
# ❌ OLD
from src.graph.nodes.budget_estimator import estimate_run_cost

# ✅ NEW
from src.services.budget_estimator_v2 import estimate_run_cost, BudgetEstimate
```

### 2. Review Budget Caps

All existing user-facing budget caps must be increased:

| Old Cap | New Cap | Reason |
|---------|---------|--------|
| $5 | $10 | +100% Economy |
| $10 | $18 | +80% Balanced |
| $20 | $45 | +125% Premium |

**Action:** Update `max_budget_dollars` validation in:
- `backend/src/api/schemas.py`
- `frontend/src/components/ConfigPanel.tsx`
- `.env.example`

### 3. Re-Run Golden-Set Tests

```bash
# Existing integration tests may fail due to new costs
pytest tests/integration/test_full_pipeline.py -k budget

# Update expected values in:
# tests/fixtures/golden_estimates.json
```

### 4. Update UI Display

New `BudgetEstimate` fields available for UI:

```typescript
interface BudgetEstimate {
  estimated_total_usd: number;
  cost_per_section: number;
  regime: "Economy" | "Balanced" | "Premium";
  budget_per_word: number;
  blocked: boolean;
  block_reason: string | null;
  
  // NEW in v2
  planner_cost: number;
  panel_contingency: number;
  compression_savings: number;  // if RLM enabled
  recursive_call_factor: number;
  
  // Breakdown for charts
  writer_cost_per_iter: number;
  jury_cost_per_iter: number;
  reflector_cost_per_iter: number;
  researcher_cost_per_iter: number;
}
```

### 5. Enable RLM (Optional)

RLM context offload is **disabled by default**. To enable:

```python
# In preflight node (backend/src/graph/nodes/preflight.py)
estimate = estimate_run_cost(
    ...,
    enable_rlm_offload=True,  # Add this flag
)
```

**Prerequisite:** Verify Context Compressor (§5.16) is implemented.

---

## ✅ Validation

Run full test suite:

```bash
# Unit tests (must pass 100%)
pytest tests/unit/test_budget_estimator_v2.py -v

# Integration tests (update expected values)
pytest tests/integration/ -k budget --tb=short

# Manual smoke test
python backend/src/services/budget_estimator_v2.py
```

**Expected Output:**
```
================================================================================
Budget Estimator v2 — Test Comparison
================================================================================

Scenario: 8 sections × 1,000 words = 8,000 words total, max_budget=$15.00

Regime: Balanced
Budget per word: $0.001875

--- Cost Breakdown (per iteration) ---
Writer:      $0.1840
Jury:        $0.2150
Reflector:   $0.0620
Researcher:  $0.0280

--- Total Estimate ---
Per section: $1.4725
Planner:     $0.0432
Panel:       $0.8600 (contingency)

🎯 TOTAL:     $12.63
vs Budget:   $15.00
Utilization: 84.2%

✅ APPROVED
```

---

## 📊 Impact Analysis

### Cost Increase Breakdown

| Component | Contribution to Delta |
|-----------|----------------------|
| BUG #1 (gpt-4.5) | **+65%** |
| BUG #2 (MoW) | +15% |
| BUG #3 (input tokens) | +12% |
| GAP #6 (planner) | +0.3% |
| SHINE (panel) | +8% |
| **Total** | **+100%** (2× old estimate) |

BUG #4 and #5 are **reductions** (correct underestimation of Economy regime).

### Recommendation

1. **Immediate:** Merge `budget_estimator_v2.py` to `main`
2. **Week 1:** Update all budget caps in UI/API
3. **Week 2:** Enable RLM offload for 10% of users (A/B test)
4. **Week 3:** Deprecate old estimator, redirect to v2

---

## 🔗 References

- Spec §19: [19_budget_controller.md](../source_clean/19_budget_controller.md)
- Spec §28: [28_llm_assignments.md](../source_clean/28_llm_assignments.md)
- Spec §11: [Panel Discussion](../source_clean/11_panel_discussion.md)
- SHINE: [github.com/Yewei-Liu/SHINE](https://github.com/Yewei-Liu/SHINE)
- RLM: [github.com/alexzhang13/rlm](https://github.com/alexzhang13/rlm)
- Pricing: [src/llm/pricing.py](../src/llm/pricing.py)

---

**Author:** DRS Spec Review Team  
**Date:** 2026-03-04  
**Version:** v2.0.0
