"""Budget regime tables — §9.3 THRESHOLD_TABLE + §19.2 REGIME_PARAMS."""
from __future__ import annotations
from typing import Any, Literal

# §9.3 — SINGLE SOURCE OF TRUTH for all CSS thresholds
THRESHOLD_TABLE: dict[str, dict[str, float]] = {
    "economy": {
        "css_content_threshold": 0.65,
        "css_style_threshold":   0.75,
        "css_panel_trigger":     0.40,
    },
    "balanced": {
        "css_content_threshold": 0.70,
        "css_style_threshold":   0.80,
        "css_panel_trigger":     0.50,
    },
    "premium": {
        "css_content_threshold": 0.78,
        "css_style_threshold":   0.85,
        "css_panel_trigger":     0.55,
    },
}

# §19.2 — Budget regime parameters
REGIME_PARAMS: dict[str, dict[str, Any]] = {
    "Economy": {
        "budget_per_word_max": 0.002,
        "max_iterations": 2,
        "jury_size": 1,
        "mow_enabled": False,
        "writer_model": "anthropic/claude-sonnet-4",
        "cascading_enabled": False,
    },
    "Balanced": {
        "budget_per_word_range": (0.002, 0.005),
        "max_iterations": 4,
        "jury_size": 2,
        "mow_enabled": True,
        "writer_model": "anthropic/claude-opus-4-5",
        "cascading_enabled": True,
    },
    "Premium": {
        "budget_per_word_min": 0.005,
        "max_iterations": 8,
        "jury_size": 3,
        "mow_enabled": True,
        "writer_model": "anthropic/claude-opus-4-5",
        "cascading_enabled": True,
    },
}

# §9.2 — Jury weights (used for CSS_composite only)
JURY_WEIGHTS: dict[str, float] = {
    "reasoning": 0.35,
    "factual":   0.45,
    "style":     0.20,
}


def derive_quality_preset(budget_per_word: float) -> Literal["Economy", "Balanced", "Premium"]:
    """Derive regime from budget_per_word ratio. §19.2."""
    if budget_per_word < 0.002:
        return "Economy"
    elif budget_per_word <= 0.005:
        return "Balanced"
    else:
        return "Premium"


def populate_budget_thresholds(budget: dict, config: dict) -> dict:
    """
    Write resolved CSS thresholds into BudgetState. §9.3.
    Called by BudgetController at init and after regime change.
    """
    preset: str = config.get("_budget_regime_override") or config.get("user", {}).get("quality_preset", "balanced")
    thresholds = THRESHOLD_TABLE[preset.lower()]
    budget = dict(budget)
    budget["css_content_threshold"] = thresholds["css_content_threshold"]
    budget["css_style_threshold"]   = thresholds["css_style_threshold"]
    budget["css_panel_threshold"]   = thresholds["css_panel_trigger"]
    return budget
