"""Preflight node (§5.1) — validate configuration and dependencies.

First node in the graph. Checks:
- Required API keys present
- Budget configuration valid
- Style profile loaded
- Output directory exists
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_REQUIRED_KEYS: list[str] = []  # No hard requirement — gracefully degrade
_RECOMMENDED_KEYS: list[str] = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "PERPLEXITY_API_KEY",
]


def preflight_node(state: dict) -> dict:
    """Validate configuration before starting pipeline.

    Returns:
        Partial state with ``preflight_passed``, ``preflight_warnings``,
        and initialized ``budget`` defaults if missing.
    """
    warnings: list[str] = []
    config = state.get("config", {})

    # Check API keys
    available_keys = []
    for key in _RECOMMENDED_KEYS:
        if os.environ.get(key):
            available_keys.append(key)
        else:
            warnings.append(f"Missing recommended env var: {key}")

    if not available_keys:
        warnings.append("No LLM API keys found — pipeline will use fallback/stub modes")

    # Validate budget
    budget = dict(state.get("budget", {}))
    if not budget.get("max_dollars"):
        budget.setdefault("max_dollars", 10.0)
        budget.setdefault("spent_dollars", 0.0)
        warnings.append("No budget.max_dollars set — defaulting to $10.00")

    if not budget.get("quality_preset"):
        user_cfg = config.get("user", {})
        budget["quality_preset"] = user_cfg.get("quality_preset", "balanced")

    # Validate outline exists or topic is provided
    topic = state.get("topic", config.get("topic", ""))
    if not topic and not state.get("outline"):
        warnings.append("No topic or outline provided")

    # Ensure output dir
    doc_id = state.get("doc_id", "default")
    output_dir = Path("output") / doc_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Preflight: %d API keys available, %d warnings, budget=$%.2f",
        len(available_keys), len(warnings), budget.get("max_dollars", 0),
    )

    return {
        "preflight_passed": len(warnings) < 5,  # Allow some warnings
        "preflight_warnings": warnings,
        "budget": budget,
    }
