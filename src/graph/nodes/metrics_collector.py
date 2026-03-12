"""Metrics Collector node (§5.8) — embeddings and token counting.

Collects per-draft metrics:
- Draft embedding (for oscillation detection)
- Token count (for budget tracking)
- Readability scores
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)


def metrics_collector_node(state: dict) -> dict:
    """Collect metrics from the current draft.

    Returns:
        Partial state with ``draft_embeddings`` (appended),
        ``draft_token_count``, and ``draft_metrics``.
    """
    draft = state.get("current_draft", "")
    iteration = state.get("current_iteration", 1)

    # Token count estimate (4 chars ≈ 1 token)
    token_count = len(draft) // 4 if draft else 0

    # Simple readability metrics
    metrics = _compute_readability(draft)
    metrics["token_count"] = token_count
    metrics["iteration"] = iteration
    metrics["char_count"] = len(draft)

    # Generate simple embedding (hash-based fingerprint for oscillation detection)
    # In production, this would use BGE-M3 or similar
    embedding = _compute_fingerprint(draft)

    # Update budget spent (rough estimate)
    budget = dict(state.get("budget", {}))
    # Estimate cost of this iteration (tokens processed by jury + writer)
    iter_cost = token_count * 0.000003  # ~$3/1M tokens average
    budget["spent_dollars"] = budget.get("spent_dollars", 0) + iter_cost

    logger.info(
        "MetricsCollector: %d tokens, readability=%.1f, iteration=%d",
        token_count, metrics.get("readability_score", 0), iteration,
    )

    return {
        "draft_embeddings": [embedding],  # Appended via reducer
        "draft_token_count": token_count,
        "draft_metrics": metrics,
        "budget": budget,
    }


def _compute_readability(text: str) -> dict:
    """Compute simple readability metrics."""
    if not text:
        return {"readability_score": 0, "avg_sentence_length": 0, "word_count": 0}

    words = text.split()
    word_count = len(words)

    # Approximate sentence count
    sentences = max(1, text.count(".") + text.count("!") + text.count("?"))
    avg_sentence_length = word_count / sentences

    # Simple readability score (0-100, higher = more readable)
    # Based loosely on Flesch Reading Ease
    readability = max(0, min(100, 206.835 - 1.015 * avg_sentence_length))

    return {
        "readability_score": round(readability, 1),
        "avg_sentence_length": round(avg_sentence_length, 1),
        "word_count": word_count,
        "sentence_count": sentences,
    }


def _compute_fingerprint(text: str, dim: int = 64) -> list[float]:
    """Compute a simple hash-based fingerprint vector.

    Not a true embedding — sufficient for oscillation detection
    (cosine similarity between consecutive drafts).
    In production, replace with BGE-M3 embeddings.
    """
    if not text:
        return [0.0] * dim

    # Use character n-gram hashing to build a fingerprint
    vector = [0.0] * dim
    for i in range(len(text) - 2):
        trigram = text[i:i + 3]
        h = hash(trigram) % dim
        vector[h] += 1.0

    # Normalize to unit vector
    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]

    return vector
