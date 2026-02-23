"""Oscillation detector (§5.15, §13) — detect revision loops.

Monitors CSS history and draft embeddings to detect three types
of oscillation:

1. **CSS oscillation**: CSS scores bounce up/down without converging
2. **SEMANTIC oscillation**: Draft embeddings show high cosine similarity
   between alternate iterations (i.e., reverting changes)
3. **WHACK_A_MOLE**: Fixing one issue re-introduces another

When oscillation is detected, ``route_after_oscillation`` escalates
to human intervention to break the loop.
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# ── Thresholds ───────────────────────────────────────────────────────────────
_CSS_OSCILLATION_WINDOW = 4      # Look at last N CSS scores
_CSS_OSCILLATION_THRESHOLD = 0.03  # Max variance for "stuck" detection
_CSS_DIRECTION_CHANGES = 3       # N direction changes = oscillation
_SEMANTIC_SIM_THRESHOLD = 0.95   # Cosine sim between iter N and N-2


def oscillation_check_node(state: dict) -> dict:
    """Detect oscillation patterns in CSS history and draft embeddings.

    Args:
        state: DocumentState dict with ``css_history`` and
               ``draft_embeddings``.

    Returns:
        Partial state update with ``oscillation_detected`` and
        ``oscillation_type``.
    """
    css_history = state.get("css_history", [])
    draft_embeddings = state.get("draft_embeddings", [])
    iteration = state.get("current_iteration", 1)

    # Skip on early iterations (need at least 3 data points)
    if iteration < 3 or len(css_history) < 3:
        return {
            "oscillation_detected": False,
            "oscillation_type": None,
        }

    # Check CSS oscillation
    css_osc = _detect_css_oscillation(css_history)
    if css_osc:
        logger.warning(
            "CSS oscillation detected: %s (last %d scores: %s)",
            css_osc, len(css_history), css_history[-_CSS_OSCILLATION_WINDOW:],
        )
        return {
            "oscillation_detected": True,
            "oscillation_type": css_osc,
        }

    # Check semantic oscillation (requires embeddings)
    if len(draft_embeddings) >= 3:
        sem_osc = _detect_semantic_oscillation(draft_embeddings)
        if sem_osc:
            logger.warning("Semantic oscillation detected (draft reverting)")
            return {
                "oscillation_detected": True,
                "oscillation_type": "SEMANTIC",
            }

    return {
        "oscillation_detected": False,
        "oscillation_type": None,
    }


def _detect_css_oscillation(css_history: list[float]) -> str | None:
    """Detect CSS score oscillation patterns.

    Returns oscillation type or None.
    """
    window = css_history[-_CSS_OSCILLATION_WINDOW:]

    if len(window) < 3:
        return None

    # Pattern 1: Direction changes (up-down-up-down)
    directions = []
    for i in range(1, len(window)):
        diff = window[i] - window[i - 1]
        if abs(diff) > 0.01:  # ignore noise
            directions.append(1 if diff > 0 else -1)

    if len(directions) >= _CSS_DIRECTION_CHANGES:
        changes = sum(
            1 for i in range(1, len(directions))
            if directions[i] != directions[i - 1]
        )
        if changes >= _CSS_DIRECTION_CHANGES - 1:
            return "CSS"

    # Pattern 2: Stuck (variance too low — not improving)
    if len(window) >= 4:
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        if variance < _CSS_OSCILLATION_THRESHOLD ** 2:
            # Check if CSS is below threshold (stuck at low quality)
            if mean < 0.75:
                return "WHACK_A_MOLE"

    return None


def _detect_semantic_oscillation(embeddings: list[list[float]]) -> bool:
    """Detect if draft is reverting to a previous version.

    Compares embedding of iteration N with iteration N-2.
    If cosine similarity > threshold, the draft is "reverting".
    """
    if len(embeddings) < 3:
        return False

    current = embeddings[-1]
    two_back = embeddings[-3]  # N-2

    sim = _cosine_similarity(current, two_back)
    return sim > _SEMANTIC_SIM_THRESHOLD


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)
