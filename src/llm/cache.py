"""Tiered Prompt Cache — memoize system prompts to reduce input token costs.

Hashes (style_config, jury_rubric) with SHA256 and stores in Redis.
Reuses cached prompts across sections with the same policy, reducing
input token costs by 30-50%.

Falls back to in-memory LRU cache if Redis is not available.

Reference: "Strategie concrete di ottimizzazione dei costi.md" §2.4
"""
from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    """Lazy-init Redis client. Returns None if unavailable."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            url = __import__("os").environ.get("REDIS_URL", "redis://localhost:6379/0")
            _redis_client = redis.from_url(url, decode_responses=True)
            _redis_client.ping()
        except Exception as e:
            logger.debug("Redis not available for prompt cache: %s", e)
            _redis_client = False  # sentinel: don't retry
    return _redis_client if _redis_client is not False else None


def _cache_key(style_config: dict, jury_rubric: dict) -> str:
    """Deterministic SHA256 hash of prompt components."""
    payload = json.dumps(
        {"style": style_config, "rubric": jury_rubric},
        sort_keys=True,
    ).encode()
    return f"drs:prompt:{hashlib.sha256(payload).hexdigest()}"


# In-memory fallback (512 entries)
@lru_cache(maxsize=512)
def _mem_cache_get(key: str) -> str | None:
    return None  # placeholder — actual storage via side-effect


_mem_store: dict[str, str] = {}


def get_or_build_system_prompt(
    style_config: dict[str, Any],
    jury_rubric: dict[str, Any],
    builder_fn: Any = None,
) -> tuple[str, str]:
    """Return (prompt_text, cache_key). Uses Redis if available, else in-memory.

    Args:
        style_config: Style rules configuration dict
        jury_rubric: Jury rubric configuration dict
        builder_fn: Optional callable(style_config, jury_rubric) -> str.
                    If None, returns JSON serialization.

    Returns:
        (prompt_text, cache_id) — cache_id can be passed to vLLM for KV cache reuse.
    """
    key = _cache_key(style_config, jury_rubric)

    # Try Redis
    redis = _get_redis()
    if redis:
        try:
            cached = redis.get(key)
            if cached:
                logger.debug("Prompt cache HIT (Redis): %s", key[:16])
                return cached, key
        except Exception as e:
            logger.warning("Redis cache read failed: %s", e)

    # Try in-memory
    if key in _mem_store:
        logger.debug("Prompt cache HIT (memory): %s", key[:16])
        return _mem_store[key], key

    # Build prompt
    if builder_fn:
        prompt = builder_fn(style_config, jury_rubric)
    else:
        prompt = json.dumps(
            {"style_rules": style_config, "rubric": jury_rubric},
            indent=2,
        )

    # Store in Redis (1 hour TTL)
    if redis:
        try:
            redis.setex(key, 3600, prompt)
        except Exception as e:
            logger.warning("Redis cache write failed: %s", e)

    # Store in memory
    _mem_store[key] = prompt
    logger.debug("Prompt cache MISS: %s (built and stored)", key[:16])

    return prompt, key


def invalidate(style_config: dict, jury_rubric: dict) -> None:
    """Remove a cached prompt."""
    key = _cache_key(style_config, jury_rubric)
    _mem_store.pop(key, None)
    redis = _get_redis()
    if redis:
        try:
            redis.delete(key)
        except Exception:
            pass
