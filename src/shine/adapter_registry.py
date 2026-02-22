"""
AdapterRegistry — lifecycle management for SHINE-generated LoRA adapters.

Storage backends (in priority order):
  1. Redis   — hot cache, TTL-managed (default TTL: 3h per session)
  2. Memory  — in-process fallback when Redis is unavailable
  3. MinIO   — cold persistence for cross-session reuse (opt-in)

Key schema:
    drs:adapter:{doc_id}:{section_idx}

Thread safety:
    Redis and MinIO operations are individually atomic.
    In-memory fallback is NOT safe for multi-process deployments.
    Use Redis in production (already part of DRS stack).

Integration points:
    - src/graph/nodes/context_compressor.py  → store() after SHINE encoding
    - src/graph/nodes/context_compressor.py  → load() to check cache before re-encoding
    - src/graph/nodes/writer.py              → load_all_for_doc() to inject adapters
    - src/graph/nodes/aggregator.py          → invalidate() on section rejection
"""
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 3 * 3600   # 3 hours — covers typical DRS run duration
MINIO_BUCKET         = "drs-adapters"


class AdapterRegistry:
    """
    Thread-safe registry for SHINE LoRA adapters.

    Example usage::

        registry = AdapterRegistry(
            redis_client=get_redis_client(),
            minio_client=get_minio_client(),
            enable_minio_persistence=True,
        )

        # After SHINE encoding:
        registry.store(doc_id="run_abc", section_idx=3, adapter=lora_adapter)

        # Before Writer call:
        adapters = registry.load_all_for_doc(doc_id="run_abc", up_to_section=5)
        # → {0: LoRAAdapter, 1: LoRAAdapter, 2: LoRAAdapter, 3: LoRAAdapter, 4: LoRAAdapter}
    """

    def __init__(
        self,
        redis_client=None,
        minio_client=None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        enable_minio_persistence: bool = False,
    ):
        self._redis   = redis_client
        self._minio   = minio_client
        self._ttl     = ttl_seconds
        self._minio_enabled = enable_minio_persistence and minio_client is not None
        self._memory: dict[str, dict] = {}   # fallback store

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key(doc_id: str, section_idx: int) -> str:
        return f"drs:adapter:{doc_id}:{section_idx}"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store(
        self,
        doc_id: str,
        section_idx: int,
        adapter,             # LoRAAdapter
    ) -> bool:
        """
        Persist adapter to Redis (primary) with optional MinIO cold backup.

        Non-blocking: failures are logged as warnings, never raise.
        Returns True if stored successfully in at least one backend.
        """
        key        = self._key(doc_id, section_idx)
        data       = adapter.to_dict()
        data["stored_at"] = time.time()
        serialized = json.dumps(data)
        success    = False

        # --- Redis (primary) ---
        if self._redis is not None:
            try:
                self._redis.setex(key, self._ttl, serialized)
                success = True
                logger.debug("[AdapterRegistry] Stored %s in Redis (TTL=%ds)", key, self._ttl)
            except Exception as exc:
                logger.warning("[AdapterRegistry] Redis store failed for %s: %s", key, exc)

        # --- Memory fallback ---
        if not success:
            self._memory[key] = data
            success = True
            logger.debug("[AdapterRegistry] Stored %s in memory (Redis unavailable)", key)

        # --- MinIO cold persistence (async, best-effort) ---
        if self._minio_enabled and self._minio is not None:
            try:
                encoded = serialized.encode()
                self._minio.put_object(
                    bucket_name=MINIO_BUCKET,
                    object_name=f"{key}.json",
                    data=__import__("io").BytesIO(encoded),
                    length=len(encoded),
                    content_type="application/json",
                )
                logger.debug("[AdapterRegistry] Persisted %s to MinIO", key)
            except Exception as exc:
                logger.warning("[AdapterRegistry] MinIO persistence failed for %s: %s", key, exc)

        return success

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def load(self, doc_id: str, section_idx: int):
        """
        Load adapter from registry.

        Lookup order: Redis → Memory → MinIO (cold hit warms Redis).
        Returns LoRAAdapter or None if not found / expired.
        """
        from .hypernetwork import LoRAAdapter

        key = self._key(doc_id, section_idx)

        # --- Redis ---
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                if raw:
                    logger.debug("[AdapterRegistry] HIT %s (Redis)", key)
                    return LoRAAdapter.from_dict(json.loads(raw))
            except Exception as exc:
                logger.warning("[AdapterRegistry] Redis load failed for %s: %s", key, exc)

        # --- Memory ---
        if key in self._memory:
            logger.debug("[AdapterRegistry] HIT %s (memory)", key)
            return LoRAAdapter.from_dict(self._memory[key])

        # --- MinIO cold hit ---
        if self._minio_enabled and self._minio is not None:
            try:
                obj  = self._minio.get_object(MINIO_BUCKET, f"{key}.json")
                data = json.loads(obj.read())
                # Warm Redis on cold hit
                if self._redis is not None:
                    try:
                        self._redis.setex(key, self._ttl, json.dumps(data))
                    except Exception:
                        pass
                logger.debug("[AdapterRegistry] HIT %s (MinIO cold)", key)
                return LoRAAdapter.from_dict(data)
            except Exception:
                pass

        logger.debug("[AdapterRegistry] MISS %s", key)
        return None

    def load_all_for_doc(self, doc_id: str, up_to_section: int) -> dict:
        """
        Load all available adapters for a document up to (exclusive) section index.

        Called by the Writer node to retrieve all prior section knowledge.
        Sections not found in registry are silently skipped (fallback to
        text context for those sections).

        Returns:
            dict {section_idx: LoRAAdapter} for all found adapters.
        """
        result: dict = {}
        for idx in range(up_to_section):
            adapter = self.load(doc_id, idx)
            if adapter is not None:
                result[idx] = adapter
        return result

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def invalidate(self, doc_id: str, section_idx: int) -> None:
        """
        Remove adapter for a specific section.
        Called by aggregator on section rejection to force re-encoding
        after the section is rewritten and re-approved.
        """
        key = self._key(doc_id, section_idx)
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._memory.pop(key, None)
        logger.debug("[AdapterRegistry] Invalidated %s", key)

    def invalidate_doc(self, doc_id: str) -> None:
        """
        Remove all adapters for an entire document run.
        Called on run cancellation or hard error.
        """
        pattern = f"drs:adapter:{doc_id}:*"
        if self._redis:
            try:
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
                    logger.debug(
                        "[AdapterRegistry] Invalidated %d Redis keys for doc %s",
                        len(keys), doc_id,
                    )
            except Exception as exc:
                logger.warning(
                    "[AdapterRegistry] Redis invalidate_doc failed for %s: %s",
                    doc_id, exc,
                )
        stale = [k for k in self._memory if k.startswith(f"drs:adapter:{doc_id}:")]
        for k in stale:
            del self._memory[k]
