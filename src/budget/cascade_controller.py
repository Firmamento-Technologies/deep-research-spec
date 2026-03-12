"""ModelCascadeController — BudgetMLAgent-pattern dynamic model selection.

Implements intelligent model cascading based on:
- CSS score history (escalation when quality is low)
- Budget remaining (escalation only if budget permits)
- Oscillation count (triggers RLM mode when stuck)

Based on BudgetMLAgent (2024) which achieves 94.2% cost reduction via
base→QA→expert cascade. Adapted for DRS multi-agent architecture.

Reference: "Strategie concrete di ottimizzazione dei costi.md" §2.2
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Budget thresholds for allowing escalation (USD remaining)
_ESCALATION_BUDGET_MIN = 5.0

# CSS threshold below which escalation is triggered
_CSS_ESCALATION_THRESHOLD = 0.4

# Oscillation count above which RLM mode activates
_OSCILLATION_RLM_THRESHOLD = 2


class ModelCascadeController:
    """Dynamic model selector based on CSS history and budget state.

    Uses a base→escalate→RLM cascade:
    1. Start with preset's base model (cheapest for the tier)
    2. If CSS < 0.4 and budget permits → escalate one tier up
    3. If oscillation > 2 → flag RLM mode for advanced reasoning
    """

    # Base models per role per preset
    BASE_MODELS: dict[str, dict[str, str]] = {
        "writer": {
            "economy":  "qwen/qwen3.5-9b-instruct",
            "balanced": "qwen/qwen3.5-35b-a3b",
            "premium":  "anthropic/claude-3.7-sonnet",
        },
        "reflector": {
            "economy":  "qwen/qwen3.5-4b",
            "balanced": "qwen/qwen3.5-9b-instruct",
            "premium":  "openai/o3-mini",
        },
        "researcher": {
            "economy":  "qwen/qwen3.5-4b",
            "balanced": "qwen/qwen3.5-9b-instruct",
            "premium":  "perplexity/sonar-pro",
        },
    }

    # Escalation targets (one tier up from base)
    ESCALATION_MODELS: dict[str, dict[str, str]] = {
        "writer": {
            "economy":  "qwen/qwen3.5-35b-a3b",
            "balanced": "deepseek/deepseek-r1",
            "premium":  "anthropic/claude-opus-4-5",
        },
        "reflector": {
            "economy":  "qwen/qwen3.5-9b-instruct",
            "balanced": "openai/o3-mini",
            "premium":  "openai/o3",
        },
    }

    def select_model(
        self,
        role: str,
        preset: str,
        section_idx: int = 0,
        prev_css: float | None = None,
        budget_remaining: float = 100.0,
        oscillation_count: int = 0,
    ) -> tuple[str, bool]:
        """Select optimal model for a role based on cascade logic.

        Returns:
            (model_id, rlm_mode) — model to use and whether RLM should activate.
        """
        preset = preset.lower()
        base = self.BASE_MODELS.get(role, {}).get(preset)
        if base is None:
            logger.warning("No cascade config for role=%s preset=%s", role, preset)
            return ("qwen/qwen3.5-9b-instruct", False)

        rlm_mode = False

        # Cascade step: escalate if CSS low and budget permits
        if (
            section_idx > 0
            and prev_css is not None
            and prev_css < _CSS_ESCALATION_THRESHOLD
            and budget_remaining > _ESCALATION_BUDGET_MIN
        ):
            escalated = self.ESCALATION_MODELS.get(role, {}).get(preset)
            if escalated:
                logger.info(
                    "Cascade escalation: %s %s→%s (CSS=%.2f, budget=$%.2f)",
                    role, base, escalated, prev_css, budget_remaining,
                )
                base = escalated

        # RLM activation on repeated oscillation
        if oscillation_count > _OSCILLATION_RLM_THRESHOLD:
            rlm_mode = True
            logger.info(
                "RLM mode activated for %s (oscillation=%d)",
                role, oscillation_count,
            )

        return (base, rlm_mode)


# Singleton instance
cascade_controller = ModelCascadeController()
