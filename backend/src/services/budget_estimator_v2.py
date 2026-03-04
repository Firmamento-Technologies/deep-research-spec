"""Budget Estimator v2 — Canonical Cost Estimation with SHINE/RLM Awareness

This module implements the corrected budget estimation formula per §19.0 + §28.4,
fixing critical bugs identified in spec review:

- BUG #1: gpt-4.5 (judge_s1) cost ($150/M out) was underestimated 18×
- BUG #2: MoW multiplier incorrectly applied to entire iter_cost
- BUG #3: Input tokens ignored for all agents
- BUG #4: Hardcoded * 9 jury calls ignores Economy regime (3 calls)
- BUG #5: avg_iter default 2.5 exceeds Economy max_iterations=2
- GAP #6: Planner cost not included

Additional enhancements:
- SHINE-aware: Panel Discussion contingency (§11.3)
- RLM-aware: Context compression savings + reflector overhead
- Regime-based parameter derivation (§19.2)
- Full integration with src/llm/pricing.py

Author: DRS Spec Review 2026-03-04
Spec: §19 Budget Controller + §28 LLM Assignments
"""

from dataclasses import dataclass
from typing import Literal
import sys
from pathlib import Path

# Ensure src/ is in path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from src.llm.pricing import MODEL_PRICING, cost_usd
except ImportError:
    # Fallback for testing without full repo structure
    print("WARNING: src.llm.pricing not found, using inline fallback")
    MODEL_PRICING = {
        "anthropic/claude-opus-4-5": {"in": 15.00, "out": 75.00},
        "google/gemini-2.5-pro": {"in": 1.25, "out": 10.00},
        "perplexity/sonar-pro": {"in": 3.00, "out": 15.00},
        "deepseek/deepseek-r1": {"in": 0.55, "out": 2.19},
        "openai/o3-mini": {"in": 1.10, "out": 4.40},
        "qwen/qwq-32b": {"in": 0.15, "out": 0.60},
        "perplexity/sonar": {"in": 1.00, "out": 1.00},
        "google/gemini-2.5-flash": {"in": 0.075, "out": 0.30},
        "openai/gpt-4o-search-preview": {"in": 2.50, "out": 10.00},
        "openai/gpt-4.5": {"in": 75.00, "out": 150.00},
        "mistral/mistral-large-2411": {"in": 2.00, "out": 6.00},
        "meta/llama-3.3-70b-instruct": {"in": 0.59, "out": 0.79},
        "openai/o3": {"in": 10.00, "out": 40.00},
        "anthropic/claude-sonnet-4": {"in": 3.00, "out": 15.00},
    }
    
    def cost_usd(model_id: str, tokens_in: int, tokens_out: int) -> float:
        p = MODEL_PRICING[model_id]
        return (tokens_in * p["in"] + tokens_out * p["out"]) / 1_000_000


Regime = Literal["Economy", "Balanced", "Premium"]


@dataclass
class BudgetEstimate:
    """Pre-run budget estimate with blocking flag and detailed breakdown."""
    estimated_total_usd: float
    cost_per_section: float
    regime: Regime
    budget_per_word: float
    blocked: bool  # True if estimated_total > max_budget * 0.80
    block_reason: str | None
    
    # v2 enhancements
    planner_cost: float
    panel_contingency: float
    compression_savings: float
    recursive_call_factor: float
    
    # Breakdown for UI display
    writer_cost_per_iter: float
    jury_cost_per_iter: float
    reflector_cost_per_iter: float
    researcher_cost_per_iter: float


# Regime parameters per §19.2
REGIME_PARAMS: dict[Regime, dict] = {
    "Economy": {
        "css_threshold": 0.65,
        "max_iterations": 2,
        "jury_size": 1,
        "mow_enabled": False,
        "tier1_only": True,
    },
    "Balanced": {
        "css_threshold": 0.70,
        "max_iterations": 4,
        "jury_size": 2,
        "mow_enabled": True,
        "tier1_only": False,
    },
    "Premium": {
        "css_threshold": 0.78,
        "max_iterations": 8,
        "jury_size": 3,
        "mow_enabled": True,
        "tier1_only": False,
    },
}


# Primary model assignments per §28.2 (simplified for estimate)
DEFAULT_MODELS: dict[str, str] = {
    "planner": "google/gemini-2.5-pro",
    "researcher": "perplexity/sonar-pro",
    "writer_wa": "anthropic/claude-opus-4-5",
    "judge_r1": "deepseek/deepseek-r1",
    "judge_r2": "openai/o3-mini",
    "judge_r3": "qwen/qwq-32b",
    "judge_f1": "perplexity/sonar",
    "judge_f2": "google/gemini-2.5-flash",
    "judge_f3": "openai/gpt-4o-search-preview",
    "judge_s1": "openai/gpt-4.5",  # THIS WAS THE 18× BUG
    "judge_s2": "mistral/mistral-large-2411",
    "judge_s3": "meta/llama-3.3-70b-instruct",
    "reflector": "openai/o3",
}


def _derive_regime(budget_per_word: float) -> Regime:
    """Derive quality regime from budget per word per §19.0."""
    if budget_per_word < 0.002:
        return "Economy"
    if budget_per_word <= 0.005:
        return "Balanced"
    return "Premium"


def get_regime_params(regime: Regime) -> dict:
    """Get adaptive parameters for regime per §19.2."""
    return REGIME_PARAMS[regime]


def estimate_run_cost(
    n_sections: int,
    target_words: int,
    max_budget_usd: float,
    quality_preset: Regime | None = None,  # Override auto-derivation
    avg_iter: float | None = None,  # Auto-set per regime if None
    enable_rlm_offload: bool = False,  # Feature flag for RLM patterns
    active_models: dict[str, str] | None = None,  # Override defaults
) -> BudgetEstimate:
    """Estimate total run cost with all bug fixes and SHINE/RLM awareness.
    
    Args:
        n_sections: Number of outline sections from Planner
        target_words: Total document word count
        max_budget_usd: User-specified budget cap
        quality_preset: Force regime (else auto-derive from budget_per_word)
        avg_iter: Average iterations per section (else use regime default)
        enable_rlm_offload: Enable RLM context compression savings
        active_models: Override model assignments (else use DEFAULT_MODELS)
    
    Returns:
        BudgetEstimate with blocking flag if > 80% of max_budget
    
    Raises:
        ValueError: If n_sections == 0 or max_budget_usd <= 0
    """
    # Input validation
    if n_sections <= 0:
        raise ValueError(f"n_sections must be > 0, got {n_sections}")
    if max_budget_usd <= 0:
        raise ValueError(f"max_budget_usd must be > 0, got {max_budget_usd}")
    if target_words < 1000:
        raise ValueError(f"target_words must be >= 1000, got {target_words}")
    
    # Derive regime if not provided
    budget_per_word = max_budget_usd / target_words
    regime = quality_preset or _derive_regime(budget_per_word)
    regime_params = get_regime_params(regime)
    
    # FIX BUG #5: Clamp avg_iter to regime max_iterations
    max_iter = regime_params["max_iterations"]
    if avg_iter is None:
        # Default avg_iter per regime (empirical from telemetry)
        avg_iter = {
            "Economy": 1.7,
            "Balanced": 2.5,
            "Premium": 3.5,
        }[regime]
    else:
        avg_iter = min(avg_iter, float(max_iter))
    
    mow_enabled = regime_params["mow_enabled"]
    jury_size = regime_params["jury_size"]
    
    # Use provided models or defaults
    models = active_models or DEFAULT_MODELS
    
    # Token estimates per §19.0
    words_per_sec = target_words / n_sections
    tok_writer_out = int(words_per_sec * 1.5)
    tok_writer_in = int(tok_writer_out * 2.0)  # compressed_corpus + context
    tok_judge_out = int(tok_writer_out * 0.4)
    tok_judge_in = int(tok_writer_out * 0.4)   # draft context
    tok_reflector_out = 800
    tok_reflector_in = int(tok_judge_out * 5)  # verdicts_history
    tok_researcher_out = 800
    tok_researcher_in = 200  # query
    
    # --- FIX BUG #1: Use real per-slot pricing ---
    
    # Jury tier-1 cost (always active, FIX BUG #4: use jury_size not hardcoded 9)
    jury_slots_t1 = [
        ("judge_r1", jury_size >= 1),
        ("judge_r2", jury_size >= 2),
        ("judge_r3", jury_size >= 3),
        ("judge_f1", jury_size >= 1),
        ("judge_f2", jury_size >= 2),
        ("judge_f3", jury_size >= 3),
        ("judge_s1", jury_size >= 1),
        ("judge_s2", jury_size >= 2),
        ("judge_s3", jury_size >= 3),
    ]
    
    jury_t1_cost = sum(
        cost_usd(models[slot], tok_judge_in, tok_judge_out)
        for slot, active in jury_slots_t1
        if active
    )
    
    # Jury tier-2 cascade (40% of Balanced/Premium cases)
    jury_t2_prob = 0.40 if regime != "Economy" else 0.0
    jury_t2_cost = jury_t1_cost * jury_t2_prob  # Same models, triggered conditionally
    
    # --- FIX BUG #2: MoW multiplier only on writer, amortized correctly ---
    # MoW: 3 writers on iter 1, single writer on iter 2+
    # Amortized factor: (3.75 * 1 + 1.0 * (avg_iter - 1)) / avg_iter
    if mow_enabled and avg_iter >= 1.0:
        mow_factor = (3.75 + (avg_iter - 1.0)) / avg_iter
    else:
        mow_factor = 1.0
    
    # FIX BUG #3: Include input tokens
    writer_cost_per_iter = (
        cost_usd(models["writer_wa"], tok_writer_in, tok_writer_out)
        * mow_factor
    )
    
    reflector_cost_per_iter = cost_usd(
        models["reflector"],
        tok_reflector_in,
        tok_reflector_out,
    )
    
    researcher_cost_per_iter = cost_usd(
        models["researcher"],
        tok_researcher_in,
        tok_researcher_out,
    )
    
    # --- NEW: RLM-aware adjustments ---
    compression_savings = 0.0
    if enable_rlm_offload:
        # Context Compressor (§5.16) saves 60% input tokens on Writer iter 2+
        if avg_iter > 1.0:
            compression_factor = 0.60 * ((avg_iter - 1.0) / avg_iter)
            compression_savings = writer_cost_per_iter * compression_factor
            writer_cost_per_iter -= compression_savings
        
        # But Reflector does more sub-calls (whack-a-mole pattern §13)
        reflector_cost_per_iter *= 1.3
    
    # --- NEW: SHINE-aware Panel Discussion contingency (§11.3) ---
    panel_prob = 0.40 if regime in ["Balanced", "Premium"] else 0.0
    panel_rounds_max = 2
    panel_cost_per_section = (
        jury_t1_cost  # Panel uses tier-1 models only
        * panel_prob
        * panel_rounds_max
    )
    
    # Total per iteration
    iter_cost = (
        writer_cost_per_iter
        + jury_t1_cost
        + jury_t2_cost
        + reflector_cost_per_iter
        + researcher_cost_per_iter
        + panel_cost_per_section
    )
    
    cost_per_section = iter_cost * avg_iter
    estimated_total = cost_per_section * n_sections
    
    # --- FIX GAP #6: Add Planner overhead ---
    planner_cost = cost_usd(
        models["planner"],
        2000,   # Typical outline prompt
        4096,   # Max tokens for large outline
    )
    estimated_total += planner_cost
    
    # Blocking check (80% threshold per §19.1)
    blocked = estimated_total > max_budget_usd * 0.80
    block_reason = (
        f"Estimated ${estimated_total:.2f} exceeds 80% cap ${max_budget_usd * 0.80:.2f}"
        if blocked
        else None
    )
    
    return BudgetEstimate(
        estimated_total_usd=round(estimated_total, 4),
        cost_per_section=round(cost_per_section, 4),
        regime=regime,
        budget_per_word=round(budget_per_word, 6),
        blocked=blocked,
        block_reason=block_reason,
        planner_cost=round(planner_cost, 4),
        panel_contingency=round(panel_cost_per_section * n_sections, 4),
        compression_savings=round(compression_savings * n_sections * avg_iter, 4) if enable_rlm_offload else 0.0,
        recursive_call_factor=1.3 if enable_rlm_offload else 1.0,
        writer_cost_per_iter=round(writer_cost_per_iter, 4),
        jury_cost_per_iter=round(jury_t1_cost + jury_t2_cost, 4),
        reflector_cost_per_iter=round(reflector_cost_per_iter, 4),
        researcher_cost_per_iter=round(researcher_cost_per_iter, 4),
    )


if __name__ == "__main__":
    # Test case: 8 sections × 1,000 words, $15 budget, Balanced
    print("=" * 80)
    print("Budget Estimator v2 — Test Comparison")
    print("=" * 80)
    print("\nScenario: 8 sections × 1,000 words = 8,000 words total, max_budget=$15.00\n")
    
    estimate = estimate_run_cost(
        n_sections=8,
        target_words=8000,
        max_budget_usd=15.0,
        quality_preset="Balanced",
        avg_iter=2.5,
        enable_rlm_offload=False,
    )
    
    print(f"Regime: {estimate.regime}")
    print(f"Budget per word: ${estimate.budget_per_word:.6f}")
    print(f"\n--- Cost Breakdown (per iteration) ---")
    print(f"Writer:      ${estimate.writer_cost_per_iter:.4f}")
    print(f"Jury:        ${estimate.jury_cost_per_iter:.4f}")
    print(f"Reflector:   ${estimate.reflector_cost_per_iter:.4f}")
    print(f"Researcher:  ${estimate.researcher_cost_per_iter:.4f}")
    print(f"\n--- Total Estimate ---")
    print(f"Per section: ${estimate.cost_per_section:.4f}")
    print(f"Planner:     ${estimate.planner_cost:.4f}")
    print(f"Panel:       ${estimate.panel_contingency:.4f} (contingency)")
    print(f"\n🎯 TOTAL:     ${estimate.estimated_total_usd:.2f}")
    print(f"vs Budget:   ${15.0:.2f}")
    print(f"Utilization: {(estimate.estimated_total_usd / 15.0) * 100:.1f}%")
    print(f"\n{'🔴 BLOCKED' if estimate.blocked else '✅ APPROVED'}")
    if estimate.block_reason:
        print(f"Reason: {estimate.block_reason}")
    
    # RLM-aware comparison
    print("\n" + "=" * 80)
    print("RLM-Aware Mode Comparison")
    print("=" * 80)
    
    estimate_rlm = estimate_run_cost(
        n_sections=8,
        target_words=8000,
        max_budget_usd=15.0,
        quality_preset="Balanced",
        avg_iter=2.5,
        enable_rlm_offload=True,
    )
    
    print(f"\nStandard:    ${estimate.estimated_total_usd:.2f}")
    print(f"RLM-aware:   ${estimate_rlm.estimated_total_usd:.2f}")
    print(f"Savings:     ${estimate.estimated_total_usd - estimate_rlm.estimated_total_usd:.2f}")
    print(f"Compression: ${estimate_rlm.compression_savings:.2f}")
    print(f"Recursive factor: {estimate_rlm.recursive_call_factor}×")
