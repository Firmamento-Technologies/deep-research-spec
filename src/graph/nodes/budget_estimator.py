"""Budget Estimator node (§5.2) — project total cost from outline.

Takes the generated outline and estimates total pipeline cost based on:
- Number of sections
- Quality preset (economy/balanced/premium)
- Estimated tokens per section
- Jury size and iteration count
"""
from __future__ import annotations

import logging

from src.graph._presets import normalize_preset, DEFAULT_PRESET

logger = logging.getLogger(__name__)

# ── Cost-per-section estimates by preset (§19) ───────────────────────────────────
# Chiavi lowercase — allineate a QualityPreset e alla routing table.
_COST_PER_SECTION: dict[str, float] = {
    "economy":  0.15,   # Fewer judges, fewer iterations
    "balanced": 0.40,   # Standard pipeline
    "premium":  0.80,   # Full jury, more iterations
}


def budget_estimator_node(state: dict) -> dict:
    """Estimate total pipeline cost from outline.

    Legge quality_preset da state (campo top-level normalizzato da preflight_node),
    NON da budget["quality_preset"] che non è un campo BudgetState dichiarato.

    Returns:
        Partial state con ``budget`` aggiornato: ``estimated_total``,
        ``per_section_estimate``, ``num_sections``.
    """
    outline = state.get("outline") or []
    budget = dict(state.get("budget") or {})

    # Leggi dal campo top-level DocumentState.quality_preset.
    # normalize_preset() è chiamata qui come difesa (es. chiamate dirette
    # in test senza preflight), ma in produzione il valore è già canonical.
    preset = normalize_preset(state.get("quality_preset"))

    n_sections = len(outline) if outline else 5  # Default estimate
    cost_per_section = _COST_PER_SECTION.get(preset, _COST_PER_SECTION[DEFAULT_PRESET])
    estimated_total = n_sections * cost_per_section

    budget["estimated_total"] = estimated_total
    budget["per_section_estimate"] = cost_per_section
    budget["num_sections"] = n_sections

    # Propaga il preset nel regime in caso budget_estimator venga chiamato
    # senza preflight (es. test unitari isolati).
    if not budget.get("regime"):
        budget["regime"] = preset

    max_dollars = budget.get("max_dollars", 10.0)
    if estimated_total > max_dollars:
        logger.warning(
            "BudgetEstimator: estimated $%.2f exceeds max $%.2f — "
            "may trigger budget_hard_stop before completion",
            estimated_total,
            max_dollars,
        )
        budget["budget_warning"] = (
            f"Estimated ${estimated_total:.2f} exceeds budget ${max_dollars:.2f}"
        )

    logger.info(
        "BudgetEstimator: %d sections × $%.2f = $%.2f estimated (preset=%s)",
        n_sections, cost_per_section, estimated_total, preset,
    )

    return {"budget": budget}
