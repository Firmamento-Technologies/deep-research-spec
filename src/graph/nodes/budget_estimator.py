"""Budget Estimator node (§5.2) — project total cost from outline.

Takes the generated outline and estimates total pipeline cost based on:
- Number of sections
- Quality preset (economy/balanced/premium)
- Estimated tokens per section
- Jury size and iteration count
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Cost-per-section estimates by preset (§19) ─────────────────────────────
_COST_PER_SECTION: dict[str, float] = {
    "economy": 0.15,     # Fewer judges, fewer iterations
    "balanced": 0.40,    # Standard pipeline
    "premium": 0.80,     # Full jury, more iterations
    "max_quality": 1.20, # All features enabled
}


def budget_estimator_node(state: dict) -> dict:
    """Estimate total pipeline cost from outline.

    Returns:
        Partial state with updated ``budget`` containing
        ``estimated_total``, ``per_section_estimate``,
        and verified ``max_dollars``.
    """
    outline = state.get("outline", [])
    budget = dict(state.get("budget", {}))
    preset = budget.get("quality_preset", "balanced").lower()

    n_sections = len(outline) if outline else 5  # Default estimate

    cost_per_section = _COST_PER_SECTION.get(preset, _COST_PER_SECTION["balanced"])
    estimated_total = n_sections * cost_per_section

    budget["estimated_total"] = estimated_total
    budget["per_section_estimate"] = cost_per_section
    budget["num_sections"] = n_sections

    # Check if budget is sufficient
    max_dollars = budget.get("max_dollars", 10.0)
    if estimated_total > max_dollars:
        logger.warning(
            "BudgetEstimator: estimated $%.2f exceeds max $%.2f — "
            "may trigger budget_hard_stop before completion",
            estimated_total, max_dollars,
        )
        budget["budget_warning"] = (
            f"Estimated ${estimated_total:.2f} exceeds budget ${max_dollars:.2f}"
        )

    logger.info(
        "BudgetEstimator: %d sections × $%.2f = $%.2f estimated (preset=%s)",
        n_sections, cost_per_section, estimated_total, preset,
    )

    return {"budget": budget}
