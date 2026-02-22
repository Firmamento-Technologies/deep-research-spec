"""Budget Estimator — §19.0, §19.1 canonical.

Pre-run cost estimation and regime derivation. Blocks the run before
any LLM call if projected cost exceeds 80% of the budget cap.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from src.budget.regime import (
    REGIME_PARAMS,
    derive_quality_preset,
    populate_budget_thresholds,
)

logger = logging.getLogger(__name__)

Regime = Literal["Economy", "Balanced", "Premium"]


# ── §19.0 BudgetEstimate dataclass ──────────────────────────────────────────

@dataclass(frozen=True)
class BudgetEstimate:
    """Result of pre-run cost estimation. §19.0."""
    estimated_total_usd: float
    cost_per_section: float
    regime: Regime
    budget_per_word: float
    blocked: bool           # True if estimated_total > max_budget * 0.80
    block_reason: str | None


# ── §19.0 estimate_run_cost ─────────────────────────────────────────────────

def estimate_run_cost(
    n_sections: int,
    target_words: int,
    max_budget_usd: float,
    avg_iter: float = 2.5,
    # $/M tokens (output) — conservative defaults from §19.0
    price_writer_out: float = 75.0,       # claude-opus-4-5
    price_jury_t1_out: float = 1.10,      # tier1 avg (qwq-32b/sonar/llama)
    price_jury_t2_out: float = 12.0,      # tier2 avg (o3-mini/gemini-flash/mistral-l)
    price_reflector_out: float = 40.0,    # o3
    price_researcher_out: float = 1.0,    # sonar
    mow_enabled: bool = True,
) -> BudgetEstimate:
    """Estimate total run cost before first LLM call. §19.0.

    Args:
        n_sections: Number of outline sections.
        target_words: Total target word count (≥ 500).
        max_budget_usd: Hard budget cap in USD.
        avg_iter: Average iterations per section.
        price_*_out: Output token prices per million tokens.
        mow_enabled: Whether Mixture-of-Writers is enabled.

    Returns:
        BudgetEstimate with estimated cost, regime, and block status.

    Raises:
        ValueError: If n_sections == 0 (outline empty).
    """
    if n_sections == 0:
        raise ValueError("outline empty: n_sections == 0")

    words_per_sec = target_words / n_sections
    tok_writer_out = words_per_sec * 1.5
    tok_researcher = 800.0
    tok_reflector = 800.0

    # Jury cascading: tier1 always (9 calls); tier2 only on ~40% disagreement
    jury_t1_cost = tok_writer_out * 0.4 * price_jury_t1_out / 1_000_000 * 9
    jury_t2_cost = tok_writer_out * 0.4 * price_jury_t2_out / 1_000_000 * 3 * 0.40

    writer_cost = tok_writer_out * price_writer_out / 1_000_000
    reflector_cost = tok_reflector * price_reflector_out / 1_000_000
    researcher_cost = tok_researcher * price_researcher_out / 1_000_000

    iter_cost = writer_cost + jury_t1_cost + jury_t2_cost + reflector_cost + researcher_cost
    if mow_enabled:
        iter_cost *= 1.4  # MoW adds ~3 Writer calls in iter 1; amortised over avg_iter

    cost_per_section = iter_cost * avg_iter
    estimated_total = cost_per_section * n_sections
    budget_per_word = max_budget_usd / target_words
    regime = _derive_regime(budget_per_word)
    blocked = estimated_total > max_budget_usd * 0.80

    return BudgetEstimate(
        estimated_total_usd=round(estimated_total, 4),
        cost_per_section=round(cost_per_section, 4),
        regime=regime,
        budget_per_word=round(budget_per_word, 6),
        blocked=blocked,
        block_reason=(
            f"Estimated ${estimated_total:.2f} > 80% cap "
            f"${max_budget_usd * 0.80:.2f}"
            if blocked
            else None
        ),
    )


def _derive_regime(budget_per_word: float) -> Regime:
    """Derive regime from budget_per_word ratio. §19.0 / §19.2."""
    return derive_quality_preset(budget_per_word)


# ── §19.1 BudgetEstimator node ──────────────────────────────────────────────

def budget_estimator_node(state: dict) -> dict:
    """Pre-run BudgetEstimator graph node. §19.1.

    Deterministic node (no LLM call). Computes budget estimate, derives
    regime, populates thresholds, and initializes BudgetState.

    MUST be called before any researcher/writer node.
    MUST block the run if BudgetEstimate.blocked is True.

    Args:
        state: DocumentState dict.

    Returns:
        Dict with ``budget`` and optionally ``status`` keys for state merge.
    """
    config = state.get("config", {})
    user_cfg = config.get("user", config)  # support both nested and flat config

    outline = state.get("outline", [])
    n_sections = len(outline)
    target_words: int = user_cfg.get("target_words", 5000)
    max_budget_usd: float = user_cfg.get("max_budget_dollars", 10.0)
    quality_preset: str = user_cfg.get("quality_preset", "balanced")

    if n_sections == 0:
        raise ValueError("outline empty: cannot estimate budget with 0 sections")
    if max_budget_usd <= 0:
        raise ValueError(f"max_budget_dollars must be > 0, got {max_budget_usd}")

    # Derive regime from budget
    budget_per_word = max_budget_usd / target_words
    regime = _derive_regime(budget_per_word)
    regime_params = REGIME_PARAMS[regime]

    mow_enabled = regime_params["mow_enabled"]

    # Estimate cost
    estimate = estimate_run_cost(
        n_sections=n_sections,
        target_words=target_words,
        max_budget_usd=max_budget_usd,
        mow_enabled=mow_enabled,
    )

    # Initialize BudgetState §19.3
    budget: dict = {
        "max_dollars": max_budget_usd,
        "spent_dollars": 0.0,
        "projected_final": estimate.estimated_total_usd,
        "regime": regime,
        "css_content_threshold": 0.0,   # populated below
        "css_style_threshold": 0.0,     # populated below
        "css_panel_threshold": 0.0,     # populated below
        "max_iterations": regime_params["max_iterations"],
        "jury_size": regime_params["jury_size"],
        "mow_enabled": mow_enabled,
        "alarm_70_fired": False,
        "alarm_90_fired": False,
        "hard_stop_fired": False,
    }

    # Populate thresholds from THRESHOLD_TABLE §9.3
    # Override regime in config so populate_budget_thresholds reads the derived regime
    threshold_config = dict(config)
    threshold_config["_budget_regime_override"] = regime
    budget = populate_budget_thresholds(budget, threshold_config)

    # Structured log §19.1
    logger.info(
        "budget_estimator: estimated_usd=%.4f regime=%s blocked=%s "
        "budget_per_word=%.6f cost_per_section=%.4f",
        estimate.estimated_total_usd,
        estimate.regime,
        estimate.blocked,
        estimate.budget_per_word,
        estimate.cost_per_section,
    )

    result: dict = {"budget": budget}

    if estimate.blocked:
        logger.warning(
            "BUDGET_BLOCKED: %s — run will NOT proceed.",
            estimate.block_reason,
        )
        result["status"] = "failed"
        result["budget"] = {**budget, "blocked": True}

    return result
