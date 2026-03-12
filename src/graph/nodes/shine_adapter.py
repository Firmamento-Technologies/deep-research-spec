"""ShineAdapter — Convert compressedCorpus to LoRA adapter (§RAG_SHINE_INTEGRATION §2).

Sits between SourceSynthesizer and Writer in the graph.  When SHINE is
available and conditions are met, generates a LoRA adapter from the
compressed corpus so Writer can use parametric memory instead of
putting 4-8k tokens of context in the prompt.

Fallback conditions (returns ``shine_active=False``):
    - SHINE not installed
    - ``quality_preset == "Economy"``
    - Section < 400 target words (overhead not worth it)
    - ``current_iteration > 1`` (retry — use RAG corpus only)
    - Empty corpus
    - Any SHINE runtime error

Dependencies (optional — graceful fallback if missing):
    - SHINE: ``git clone https://github.com/Yewei-Liu/SHINE.git && pip install -e SHINE/``
    - CUDA GPU with ≥18 GB VRAM (BF16) or ≥10 GB (8-bit)

RLM change (Step 11):
    SHINEAdapterSingleton ensures the ShineHypernet model is loaded ONCE
    per process and reused across all sections and all jury threads.
    Without this, shine_adapter_node() created a new ShineAdapter() on every
    call, resetting self._shine = None each time. With 9 parallel jury threads
    all invoking shine_adapter_node() concurrently, this caused 9 simultaneous
    lazy inits of ShineHypernet — loading ~7B model weights 9x in parallel.
    This is the same race condition fixed in client.py (Step 4) for SDK init.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Lazy import SHINE (fallback gracefully if not installed) ─────────────

_SHINE_AVAILABLE: bool | None = None   # tri-state: None = unchecked
_ShineHypernet:   Any         = None
_shine_check_lock = threading.Lock()   # guards the one-time availability check


def _check_shine() -> bool:
    """One-time thread-safe check for SHINE availability (double-checked locking)."""
    global _SHINE_AVAILABLE, _ShineHypernet
    if _SHINE_AVAILABLE is None:
        with _shine_check_lock:
            if _SHINE_AVAILABLE is None:  # second check inside lock
                try:
                    from shine import ShineHypernet  # type: ignore[import-untyped]
                    _ShineHypernet = ShineHypernet
                    _SHINE_AVAILABLE = True
                    logger.info("SHINE hypernetwork available")
                except ImportError:
                    _SHINE_AVAILABLE = False
                    logger.info("SHINE not installed — fallback to text corpus mode")
    return bool(_SHINE_AVAILABLE)


# ── SHINEAdapterSingleton ──────────────────────────────────────────

class SHINEAdapterSingleton:
    """Thread-safe singleton for ShineHypernet and AdapterRegistry.

    Problem solved:
        The previous pattern instantiated ShineAdapter() inside
        shine_adapter_node() on every invocation, resetting
        ``self._shine = None`` each time. Under the jury's 9-thread
        parallel pool, this triggered 9 concurrent ShineHypernet.__init__()
        calls — loading ~7B weights into GPU memory 9 times simultaneously.

    Solution:
        Module-level singleton with threading.Lock + double-checked locking.
        ShineHypernet is loaded exactly ONCE per process, then reused across
        all sections, all iterations, and all parallel jury threads.

    Usage::

        model    = shine_singleton.get_hypernetwork()
        registry = shine_singleton.get_registry(state)
    """

    def __init__(self) -> None:
        self._hyper_lock    = threading.Lock()
        self._registry_lock = threading.Lock()
        self._hypernetwork: Any = None
        self._registry:     Any = None

    def get_hypernetwork(
        self,
        backbone: str = "Qwen/Qwen2.5-7B",
        device:   str = "cuda",
    ) -> Any:
        """Return (and lazily initialise) the module-level ShineHypernet.

        Thread-safe via double-checked locking.  Exactly one GPU model
        load per process lifetime, regardless of concurrent callers.

        Returns:
            ShineHypernet instance, or None if SHINE is unavailable.
        """
        if self._hypernetwork is None:
            with self._hyper_lock:
                if self._hypernetwork is None and _check_shine():
                    logger.info(
                        "SHINE: initialising ShineHypernet(backbone=%s) — one-time GPU load",
                        backbone,
                    )
                    self._hypernetwork = _ShineHypernet(
                        backbone=backbone,
                        device=device,
                    )
                    logger.info("SHINE: ShineHypernet ready")
        return self._hypernetwork

    def get_registry(self, state: dict) -> Any:
        """Return (and lazily initialise) the module-level AdapterRegistry.

        Uses a separate lock from get_hypernetwork() to allow independent
        initialisation of each singleton resource.

        Args:
            state: DocumentState dict (may carry storage config on first call).

        Returns:
            AdapterRegistry instance, or None if initialisation fails.
        """
        if self._registry is None:
            with self._registry_lock:
                if self._registry is None:
                    try:
                        from src.shine.adapter_registry import AdapterRegistry
                        try:
                            from src.storage.redis_cache import get_redis_client
                            redis = get_redis_client()
                        except Exception:
                            redis = None
                        try:
                            from src.storage.minio import get_minio_client
                            minio = get_minio_client()
                        except Exception:
                            minio = None
                        self._registry = AdapterRegistry(
                            redis_client=redis,
                            minio_client=minio,
                            enable_minio_persistence=True,
                        )
                        logger.info("SHINE: AdapterRegistry initialised")
                    except Exception as exc:
                        logger.warning(
                            "SHINE: AdapterRegistry init failed: %s — will retry", exc
                        )
                        # Leave self._registry = None so next call retries
        return self._registry


# Module-level singletons — ONE instance per process
shine_singleton = SHINEAdapterSingleton()


# ── ShineAdapter Node ─────────────────────────────────────────────

class ShineAdapter:
    """Generate LoRA from compressed corpus using SHINE hypernetwork.

    Delegates to the module-level shine_singleton for GPU model access.
    All ShineAdapter instances share the same underlying ShineHypernet —
    no per-instance GPU memory allocation.
    """

    def __init__(self, backbone: str = "Qwen/Qwen2.5-7B", device: str = "cuda"):
        self._backbone = backbone
        self._device   = device

    def _get_shine(self) -> Any:
        """Return the module-level singleton ShineHypernet (thread-safe)."""
        return shine_singleton.get_hypernetwork(self._backbone, self._device)

    def run(self, state: dict) -> dict:
        """Generate LoRA or fallback to text corpus.

        Args:
            state: DocumentState dict.

        Returns:
            Partial state update with ``shine_active`` and optionally
            ``shine_lora``.
        """
        # ── Skip conditions (§RAG_SHINE_INTEGRATION fallback rules) ────

        if not _check_shine():
            logger.info("SHINE unavailable — using text corpus")
            return {"shine_active": False}

        # Economy preset → never activate SHINE (budget §19)
        quality = (
            state.get("quality_preset")
            or state.get("config", {}).get("quality_preset", "Balanced")
        )
        if quality == "Economy":
            logger.info("Economy preset — skipping SHINE")
            return {"shine_active": False}

        # Section < 400 words → overhead not worth it
        section_idx = state.get("current_section_idx", 0)
        outline     = state.get("outline", [])
        if section_idx < len(outline):
            target_words = outline[section_idx].get("target_words", 0)
            if target_words < 400:
                logger.info(
                    "Section %d target_words=%d (<400) — skipping SHINE",
                    section_idx, target_words,
                )
                return {"shine_active": False}

        # Iteration > 1 → skip (use RAG corpus only on retries)
        if state.get("current_iteration", 1) > 1:
            logger.info("Iteration >1 — skipping SHINE")
            return {"shine_active": False}

        # Empty corpus → nothing to compress
        corpus = state.get("synthesized_sources", "") or state.get("compressed_corpus", "")
        if not corpus:
            logger.warning("Empty corpus — skipping SHINE")
            return {"shine_active": False}

        # ── Generate LoRA ──────────────────────────────────────

        shine = self._get_shine()
        if shine is None:
            return {"shine_active": False}

        try:
            lora = shine.generate_lora(corpus, max_length=1150)  # ~0.3s on GPU
            logger.info(
                "\u2705 SHINE LoRA generated for section %d (%d chars corpus)",
                section_idx, len(corpus),
            )
            return {
                "shine_lora":    lora,
                "shine_active":  True,
            }
        except Exception as exc:
            logger.error("SHINE failed: %s — falling back to text corpus", exc)
            return {"shine_active": False}


# ── Node function for LangGraph ─────────────────────────────────────

# Module-level adapter instance — shared across all graph invocations.
# _default_adapter._get_shine() delegates to shine_singleton, so all calls
# share the same ShineHypernet regardless of concurrency.
_default_adapter = ShineAdapter()


def shine_adapter_node(state: dict) -> dict:
    """Graph-compatible node function.

    Uses module-level _default_adapter which delegates GPU model access
    to shine_singleton (thread-safe lazy init, one load per process).
    """
    return _default_adapter.run(state)
