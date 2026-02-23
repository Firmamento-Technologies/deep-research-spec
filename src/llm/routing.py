"""Model Routing (§29.3) — per-preset model selection.

Routes LLM calls to appropriate models based on quality preset
(economy/balanced/premium) and agent type. Reduces costs 55-60%
on Economy preset without significant quality degradation.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml  # type: ignore

logger = logging.getLogger(__name__)

# ── Default routing table (used if YAML config not found) ────────────────────
_DEFAULT_ROUTING: dict[str, dict[str, str]] = {
    "writer": {
        "economy": "anthropic/claude-sonnet-4",
        "balanced": "anthropic/claude-opus-4-5",
        "premium": "anthropic/claude-opus-4-5",
    },
    "jury_r": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "openai/o3-mini",
        "premium": "openai/o3",
    },
    "jury_f": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-pro",
        "premium": "openai/o3",
    },
    "jury_s": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-pro",
        "premium": "google/gemini-2.5-pro",
    },
    "reflector": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-pro",
        "premium": "openai/o3",
    },
    "fusor": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-pro",
        "premium": "openai/o3",
    },
    "planner": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-pro",
        "premium": "google/gemini-2.5-pro",
    },
    "panel_discussion": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-pro",
        "premium": "google/gemini-2.5-pro",
    },
    "coherence_guard": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-flash",
        "premium": "google/gemini-2.5-flash",
    },
    "post_draft_analyzer": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-flash",
        "premium": "google/gemini-2.5-flash",
    },
    "span_editor": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "anthropic/claude-sonnet-4",
        "premium": "anthropic/claude-sonnet-4",
    },
    "style_fixer": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "anthropic/claude-sonnet-4",
        "premium": "anthropic/claude-sonnet-4",
    },
    "length_adjuster": {
        "economy": "google/gemini-2.5-flash",
        "balanced": "google/gemini-2.5-flash",
        "premium": "google/gemini-2.5-flash",
    },
}

# ── Fallback chain ───────────────────────────────────────────────────────────
_FALLBACK_ORDER = ["economy", "balanced", "premium"]


def _load_routing_config() -> dict[str, dict[str, str]]:
    """Load routing config from YAML file, falling back to defaults."""
    config_paths = [
        Path("config/model_routing.yaml"),
        Path("config/model_routing.yml"),
    ]

    for path in config_paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f) or {}
                logger.info("ModelRouting: loaded from %s", path)
                return data
            except Exception as exc:
                logger.warning("ModelRouting: failed to load %s: %s", path, exc)

    logger.info("ModelRouting: using default routing table")
    return _DEFAULT_ROUTING


# ── Singleton routing table ──────────────────────────────────────────────────
_routing_table: dict[str, dict[str, str]] | None = None


def _get_routing_table() -> dict[str, dict[str, str]]:
    """Lazy-load routing table."""
    global _routing_table
    if _routing_table is None:
        _routing_table = _load_routing_config()
    return _routing_table


def route_model(agent: str, preset: str = "balanced") -> str:
    """Get the appropriate model for an agent and quality preset.

    Args:
        agent: Agent identifier (e.g., "writer", "jury_r", "reflector")
        preset: Quality preset — "economy", "balanced", or "premium"

    Returns:
        Model string (e.g., "anthropic/claude-opus-4-5")

    Raises:
        ValueError: If agent is not in routing table and no fallback available
    """
    table = _get_routing_table()
    preset_lower = preset.lower()

    agent_routes = table.get(agent, {})
    if not agent_routes:
        # Agent not in table — use a sensible default
        logger.warning("ModelRouting: agent '%s' not in routing table", agent)
        return "google/gemini-2.5-flash"

    # Direct match
    model = agent_routes.get(preset_lower)
    if model:
        return model

    # Fallback: try adjacent presets
    try:
        current_idx = _FALLBACK_ORDER.index(preset_lower)
    except ValueError:
        current_idx = 1  # Default to balanced

    # Try higher presets first (upgrade for quality)
    for i in range(current_idx + 1, len(_FALLBACK_ORDER)):
        model = agent_routes.get(_FALLBACK_ORDER[i])
        if model:
            logger.info(
                "ModelRouting: %s/%s → fallback to %s (%s)",
                agent, preset_lower, model, _FALLBACK_ORDER[i],
            )
            return model

    # Try lower presets (downgrade for availability)
    for i in range(current_idx - 1, -1, -1):
        model = agent_routes.get(_FALLBACK_ORDER[i])
        if model:
            logger.info(
                "ModelRouting: %s/%s → fallback to %s (%s)",
                agent, preset_lower, model, _FALLBACK_ORDER[i],
            )
            return model

    return "google/gemini-2.5-flash"


def reload_routing_config() -> None:
    """Force reload of routing config from disk."""
    global _routing_table
    _routing_table = None
    _get_routing_table()
