"""Budget Estimator v2 node (§19) — project total cost from outline.

Replaces flat-rate estimation with real per-model pricing via cost_usd().
Fixes 5 critical bugs from spec review (2026-03-04):

- BUG #1: gpt-4.5 (judge_s1) cost $150/M was underestimated 18x
- BUG #2: MoW multiplier incorrectly applied to all agents (only writer)
- BUG #3: Input tokens ignored for all agents
- BUG #4: Hardcoded * 9 jury calls ignores Economy regime (jury_size=1 → 3 calls)
- BUG #5: avg_iter=2.5 always, exceeds Economy max_iterations=2
- GAP #6: Planner cost not included

Additional: SHINE panel contingency + RLM compression awareness.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from src.graph._presets import normalize_preset, DEFAULT_PRESET
from src.llm.pricing import cost_usd

logger = logging.getLogger(__name__)

Regime = Literal["economy", "balanced", "premium"]


@dataclass
class BudgetEstimate:
    """Pre-run budget estimate with blocking flag and detailed breakdown."""
    estimated_total_usd: float
    cost_per_section: float
    regime: str
    budget_per_word: float
    blocked: bool
    block_reason: str | None
    planner_cost: float
    panel_contingency: float
    compression_savings: float
    recursive_call_factor: float
    writer_cost_per_iter: float
    jury_cost_per_iter: float
    reflector_cost_per_iter: float
    researcher_cost_per_iter: float


# Regime parameters per §19.2
REGIME_PARAMS: dict[str, dict] = {
    "economy": {
        "css_threshold": 0.65,
        "max_iterations": 2,
        "jury_size": 1,
        "mow_enabled": False,
        "default_avg_iter": 1.7,
    },
    "balanced": {
        "css_threshold": 0.70,
        "max_iterations": 4,
        "jury_size": 2,
        "mow_enabled": True,
        "default_avg_iter": 2.5,
    },
    "premium": {
        "css_threshold": 0.78,
        "max_iterations": 8,
        "jury_size": 3,
        "mow_enabled": True,
        "default_avg_iter": 3.5,
    },
}


# Primary model assignments per §28.2 (OpenRouter-compatible)
DEFAULT_MODELS: dict[str, str] = {
    "planner": "openrouter/google/gemini-2.5-pro",
    "researcher": "openrouter/google/gemini-2.5-pro",
    "writer_wa": "anthropic/claude-opus-4-5",
    "judge_r1": "openrouter/openai/o3-mini",
    "judge_f1": "openrouter/google/gemini-2.5-flash",
    "judge_s1": "openrouter/anthropic/claude-sonnet-4",
    "reflector": "openrouter/google/gemini-2.5-pro",
}


def estimate_run_cost(
    n_sections: int,
    target_words: int,
    max_budget_usd: float,
    quality_preset: str | None = None,
    avg_iter: float | None = None,
    enable_rlm_offload: bool = False,
    active_models: dict[str, str] | None = None,
) -> BudgetEstimate:
    """Estimate total run cost with all v2 bug fixes and SHINE/RLM awareness."""
    if n_sections <= 0:
        raise ValueError(f"n_sections must be > 0, got {n_sections}")
    if max_budget_usd <= 0:
        raise ValueError(f"max_budget_usd must be > 0, got {max_budget_usd}")

    budget_per_word = max_budget_usd / max(target_words, 1)
    regime = quality_preset or _derive_regime(budget_per_word)
    params = REGIME_PARAMS.get(regime, REGIME_PARAMS["balanced"])

    # FIX BUG #5: Clamp avg_iter to regime max_iterations
    max_iter = params["max_iterations"]
    if avg_iter is None:
        avg_iter = params["default_avg_iter"]
    avg_iter = min(avg_iter, float(max_iter))

    jury_size = params["jury_size"]
    mow_enabled = params["mow_enabled"]
    models = active_models or DEFAULT_MODELS

    # Token estimates per §19.0
    words_per_sec = target_words / n_sections
    tok_writer_out = int(words_per_sec * 1.5)
    tok_writer_in = int(tok_writer_out * 2.0)
    tok_judge_out = int(tok_writer_out * 0.22)
    tok_judge_in = int(tok_writer_out * 0.22)
    tok_reflector_out = 800
    tok_reflector_in = max(int(tok_judge_out * 5), 3000)
    tok_researcher_out = 800
    tok_researcher_in = 200

    # FIX BUG #1+#3+#4: Real per-slot pricing with input tokens and jury_size
    base_jury_cost = sum(
        cost_usd(models.get(slot, "openrouter/google/gemini-2.5-flash"), tok_judge_in, tok_judge_out)
        for slot in ["judge_r1", "judge_f1", "judge_s1"]
    )
    jury_t1_cost = base_jury_cost * jury_size

    # FIX BUG #2: MoW multiplier only on writer, amortized correctly
    if mow_enabled and avg_iter >= 1.0:
        mow_factor = (3.75 + (avg_iter - 1.0)) / avg_iter
    else:
        mow_factor = 1.0

    writer_cost_per_iter = (
        cost_usd(models.get("writer_wa", "anthropic/claude-opus-4-5"),
                 tok_writer_in, tok_writer_out)
        * mow_factor
    )

    reflector_cost_per_iter = cost_usd(
        models.get("reflector", "openrouter/google/gemini-2.5-pro"),
        tok_reflector_in, tok_reflector_out,
    )

    researcher_cost_per_iter = cost_usd(
        models.get("researcher", "openrouter/google/gemini-2.5-pro"),
        tok_researcher_in, tok_researcher_out,
    )

    # RLM-aware adjustments
    compression_savings = 0.0
    if enable_rlm_offload and avg_iter > 1.0:
        compression_factor = 0.60 * ((avg_iter - 1.0) / avg_iter)
        compression_savings = writer_cost_per_iter * compression_factor
        writer_cost_per_iter -= compression_savings
        reflector_cost_per_iter *= 1.3

    # SHINE panel contingency (§11.3)
    panel_prob = 0.25 if regime in ["balanced", "premium"] else 0.0
    panel_cost_per_section = jury_t1_cost * panel_prob * 2  # max 2 rounds

    # Total per iteration
    iter_cost = (
        writer_cost_per_iter
        + jury_t1_cost
        + reflector_cost_per_iter
        + researcher_cost_per_iter
    )

    cost_per_section = (iter_cost * avg_iter) + panel_cost_per_section
    estimated_total = cost_per_section * n_sections

    # GAP #6: Planner overhead
    planner_cost = cost_usd(
        models.get("planner", "google/gemini-2.5-pro"), 2000, 4096
    )
    estimated_total += planner_cost

    blocked = estimated_total > max_budget_usd * 0.80
    block_reason = (
        f"Estimated ${estimated_total:.2f} exceeds 80% cap "
        f"${max_budget_usd * 0.80:.2f}"
        if blocked else None
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
        compression_savings=round(
            compression_savings * n_sections * avg_iter, 4
        ) if enable_rlm_offload else 0.0,
        recursive_call_factor=1.3 if enable_rlm_offload else 1.0,
        writer_cost_per_iter=round(writer_cost_per_iter, 4),
        jury_cost_per_iter=round(jury_t1_cost, 4),
        reflector_cost_per_iter=round(reflector_cost_per_iter, 4),
        researcher_cost_per_iter=round(researcher_cost_per_iter, 4),
    )


def _derive_regime(budget_per_word: float) -> str:
    """Derive quality regime from budget per word per §19.0."""
    if budget_per_word < 0.002:
        return "economy"
    if budget_per_word <= 0.005:
        return "balanced"
    return "premium"


def budget_estimator_node(state: dict) -> dict:
    """Graph-compatible node function using v2 estimation."""
    outline = state.get("outline") or []
    budget = dict(state.get("budget") or {})
    preset = normalize_preset(state.get("quality_preset"))
    config = state.get("config", {})

    n_sections = len(outline) if outline else 5
    target_words = config.get("target_words", n_sections * 1000)
    max_dollars = budget.get("max_dollars", 10.0)
    enable_rlm = state.get("rlm_mode", False)

    estimate = estimate_run_cost(
        n_sections=n_sections,
        target_words=target_words,
        max_budget_usd=max_dollars,
        quality_preset=preset,
        enable_rlm_offload=enable_rlm,
    )

    budget["estimated_total"] = estimate.estimated_total_usd
    budget["per_section_estimate"] = estimate.cost_per_section
    budget["num_sections"] = n_sections
    budget["planner_cost"] = estimate.planner_cost
    budget["panel_contingency"] = estimate.panel_contingency
    budget["compression_savings"] = estimate.compression_savings

    if not budget.get("regime"):
        budget["regime"] = preset

    if estimate.blocked:
        logger.warning(
            "BudgetEstimator v2: %s — estimated $%.2f exceeds 80%% of $%.2f",
            estimate.block_reason, estimate.estimated_total_usd, max_dollars,
        )
        budget["budget_warning"] = estimate.block_reason

    logger.info(
        "BudgetEstimator v2: %d sections, $%.2f estimated "
        "(writer=$%.4f jury=$%.4f reflector=$%.4f, preset=%s)",
        n_sections, estimate.estimated_total_usd,
        estimate.writer_cost_per_iter, estimate.jury_cost_per_iter,
        estimate.reflector_cost_per_iter, preset,
    )

    return {"budget": budget}
