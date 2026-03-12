"""Redis cache helpers, cost accumulator, key schema — §21.4 canonical.

Graceful degradation: If Redis is unreachable, all cache lookups return ``None``
(cache miss); cost accumulation falls back to ``costs`` PostgreSQL table
aggregation. Run continues without interruption. Circuit breaker (§20.3)
tracks Redis failures independently.

Hash function: ``SHA-256(canonical_json(input))[:16]`` for all ``*_hash`` keys.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── Key schema — §21.4 ──────────────────────────────────────────────────────
#
# RedisKeySpace = Literal[
#     "src:{query_hash}",           # Researcher cache: list[Source] JSON
#     "cite:{doi_or_url_hash}",     # Citation metadata cache
#     "verdict:{draft_hash}:{judge_id}",  # Judge verdict cache (session-scoped)
#     "compress:{section_hash}",    # Context Compressor output cache
#     "run:{run_id}:cost",          # Atomic cost accumulator (INCRBYFLOAT)
#     "run:{run_id}:events",        # SSE event stream (Redis List, RPUSH/BLPOP)
#     "rate:{provider}:{window_ts}",# Rate limit counter (INCR + EXPIRE)
#     "session:{user_id}",          # Run Companion conversation (JSON)
#     "lock:{run_id}",              # Distributed lock (SET NX EX)
# ]

TTL_SECONDS: dict[str, int] = {
    "src:*":        86_400,     # 24 h
    "cite:*":       2_592_000,  # 30 d
    "verdict:*":    3_600,      # 1 h (session-scoped)
    "compress:*":   86_400,     # 24 h
    "run:*:cost":   604_800,    # 7 d
    "run:*:events": 3_600,      # 1 h
    "rate:*":       60,         # 1 min window
    "session:*":    86_400,     # 24 h
    "lock:*":       300,        # 5 min max lock hold
}


def _ttl_for(key: str) -> int:
    """Resolve TTL for a concrete key by matching against patterns."""
    for pattern, ttl in TTL_SECONDS.items():
        prefix = pattern.split("*")[0]  # e.g. "src:" from "src:*"
        if key.startswith(prefix):
            return ttl
    return 3_600  # safe default: 1 h


# ── Hash helper ──────────────────────────────────────────────────────────────

def sha256_hex(data: str) -> str:
    """SHA-256 truncated to 16 hex chars — canonical hash for Redis keys."""
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization for cache keying."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


# ── Researcher cache — §21.4 ────────────────────────────────────────────────

async def cached_search(
    query: str,
    provider: str,
    redis,  # redis.asyncio.Redis | None
) -> list[dict] | None:
    """Look up researcher results in Redis cache.

    Args:
        query: The search query string.
        provider: Search provider name (e.g. ``"tavily"``, ``"semantic_scholar"``).
        redis: An ``redis.asyncio.Redis`` client, or ``None`` if unavailable.

    Returns:
        Cached list of source dicts, or ``None`` on cache miss / Redis failure.
    """
    if redis is None:
        return None
    key = f"src:{sha256_hex(query + provider)}"
    try:
        hit = await redis.get(key)
        if hit:
            return json.loads(hit)
    except Exception:
        logger.warning("Redis GET failed for key=%s — treating as cache miss", key, exc_info=True)
    return None


async def cache_search_results(
    query: str,
    provider: str,
    results: list[dict],
    redis,
) -> None:
    """Store researcher results in Redis cache.

    Args:
        query: The search query string.
        provider: Search provider name.
        results: List of source dicts to cache.
        redis: An ``redis.asyncio.Redis`` client, or ``None``.
    """
    if redis is None:
        return
    key = f"src:{sha256_hex(query + provider)}"
    try:
        await redis.setex(key, TTL_SECONDS["src:*"], json.dumps(results))
    except Exception:
        logger.warning("Redis SETEX failed for key=%s — skipping cache write", key, exc_info=True)


# ── Citation cache ───────────────────────────────────────────────────────────

async def cached_citation(doi_or_url: str, redis) -> dict | None:
    """Look up citation metadata in Redis."""
    if redis is None:
        return None
    key = f"cite:{sha256_hex(doi_or_url)}"
    try:
        hit = await redis.get(key)
        if hit:
            return json.loads(hit)
    except Exception:
        logger.warning("Redis GET failed for cite cache key=%s", key, exc_info=True)
    return None


async def cache_citation(doi_or_url: str, metadata: dict, redis) -> None:
    """Store citation metadata in Redis."""
    if redis is None:
        return
    key = f"cite:{sha256_hex(doi_or_url)}"
    try:
        await redis.setex(key, TTL_SECONDS["cite:*"], json.dumps(metadata))
    except Exception:
        logger.warning("Redis SETEX failed for cite cache key=%s", key, exc_info=True)


# ── Verdict cache (session-scoped) ──────────────────────────────────────────

async def cached_verdict(draft_hash: str, judge_id: str, redis) -> dict | None:
    """Look up judge verdict in Redis (session-scoped, 1 h TTL)."""
    if redis is None:
        return None
    key = f"verdict:{draft_hash}:{judge_id}"
    try:
        hit = await redis.get(key)
        if hit:
            return json.loads(hit)
    except Exception:
        logger.warning("Redis GET failed for verdict cache key=%s", key, exc_info=True)
    return None


async def cache_verdict(draft_hash: str, judge_id: str, verdict: dict, redis) -> None:
    """Store judge verdict in Redis."""
    if redis is None:
        return
    key = f"verdict:{draft_hash}:{judge_id}"
    try:
        await redis.setex(key, TTL_SECONDS["verdict:*"], json.dumps(verdict))
    except Exception:
        logger.warning("Redis SETEX failed for verdict cache key=%s", key, exc_info=True)


# ── Context Compressor cache ────────────────────────────────────────────────

async def cached_compressed(section_hash: str, redis) -> str | None:
    """Look up compressor output in Redis."""
    if redis is None:
        return None
    key = f"compress:{section_hash}"
    try:
        hit = await redis.get(key)
        if hit:
            return hit.decode() if isinstance(hit, bytes) else hit
    except Exception:
        logger.warning("Redis GET failed for compress cache key=%s", key, exc_info=True)
    return None


async def cache_compressed(section_hash: str, compressed: str, redis) -> None:
    """Store compressor output in Redis."""
    if redis is None:
        return
    key = f"compress:{section_hash}"
    try:
        await redis.setex(key, TTL_SECONDS["compress:*"], compressed)
    except Exception:
        logger.warning("Redis SETEX failed for compress cache key=%s", key, exc_info=True)


# ── Cost accumulator (atomic) — §21.4 ───────────────────────────────────────

async def record_cost_redis(run_id: str, delta_usd: float, redis) -> float:
    """Atomically increment the run cost counter in Redis.

    Args:
        run_id: The run UUID string.
        delta_usd: Cost delta to add.
        redis: An ``redis.asyncio.Redis`` client, or ``None``.

    Returns:
        New total cost. Returns ``delta_usd`` if Redis is unavailable
        (caller should fall back to PostgreSQL aggregation).
    """
    if redis is None:
        return delta_usd
    key = f"run:{run_id}:cost"
    try:
        total = await redis.incrbyfloat(key, delta_usd)
        await redis.expire(key, TTL_SECONDS["run:*:cost"])
        return float(total)
    except Exception:
        logger.warning("Redis INCRBYFLOAT failed for key=%s — fallback to PG", key, exc_info=True)
        return delta_usd


# ── SSE event stream ────────────────────────────────────────────────────────

async def push_sse_event(run_id: str, event: dict, redis) -> None:
    """Push an SSE event onto the run's event list."""
    if redis is None:
        return
    key = f"run:{run_id}:events"
    try:
        await redis.rpush(key, json.dumps(event))
        await redis.expire(key, TTL_SECONDS["run:*:events"])
    except Exception:
        logger.warning("Redis RPUSH failed for SSE key=%s", key, exc_info=True)


# ── Rate limiter ─────────────────────────────────────────────────────────────

async def check_rate_limit(
    provider: str,
    window_ts: int,
    max_requests: int,
    redis,
) -> bool:
    """Increment and check rate-limit counter for a provider window.

    Args:
        provider: LLM provider slug (e.g. ``"openai"``, ``"anthropic"``).
        window_ts: Current timestamp truncated to window (e.g. ``int(time.time()) // 60``).
        max_requests: Maximum requests allowed in the window.
        redis: Redis client or ``None``.

    Returns:
        ``True`` if under limit, ``False`` if limit exceeded.
        Always returns ``True`` if Redis is unavailable (fail-open).
    """
    if redis is None:
        return True
    key = f"rate:{provider}:{window_ts}"
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, TTL_SECONDS["rate:*"])
        return current <= max_requests
    except Exception:
        logger.warning("Redis rate-limit check failed for key=%s — fail open", key, exc_info=True)
        return True


# ── Distributed lock ─────────────────────────────────────────────────────────

async def acquire_lock(run_id: str, redis, ttl: int | None = None) -> bool:
    """Acquire a distributed lock for a run (SET NX EX).

    Args:
        run_id: Run UUID string.
        redis: Redis client or ``None``.
        ttl: Lock TTL in seconds (default: ``TTL_SECONDS["lock:*"]`` = 300).

    Returns:
        ``True`` if lock acquired, ``False`` otherwise.
    """
    if redis is None:
        return True  # no Redis → assume single-process
    key = f"lock:{run_id}"
    lock_ttl = ttl or TTL_SECONDS["lock:*"]
    try:
        result = await redis.set(key, "1", nx=True, ex=lock_ttl)
        return result is not None
    except Exception:
        logger.warning("Redis SET NX failed for lock key=%s", key, exc_info=True)
        return True  # fail-open


async def release_lock(run_id: str, redis) -> None:
    """Release a distributed lock for a run."""
    if redis is None:
        return
    key = f"lock:{run_id}"
    try:
        await redis.delete(key)
    except Exception:
        logger.warning("Redis DEL failed for lock key=%s", key, exc_info=True)
