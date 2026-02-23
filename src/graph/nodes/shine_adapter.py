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
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Lazy import SHINE (fallback gracefully if not installed) ─────────────────

_SHINE_AVAILABLE: bool | None = None  # tri-state: None = unchecked
_ShineHypernet: Any = None


def _check_shine() -> bool:
    """One-time check for SHINE availability."""
    global _SHINE_AVAILABLE, _ShineHypernet
    if _SHINE_AVAILABLE is None:
        try:
            from shine import ShineHypernet  # type: ignore[import-untyped]
            _ShineHypernet = ShineHypernet
            _SHINE_AVAILABLE = True
            logger.info("SHINE hypernetwork available")
        except ImportError:
            _SHINE_AVAILABLE = False
            logger.info("SHINE not installed — fallback to text corpus mode")
    return _SHINE_AVAILABLE


# ── ShineAdapter Node ────────────────────────────────────────────────────────

class ShineAdapter:
    """Generate LoRA from compressed corpus using SHINE hypernetwork.

    Instantiated per-call by ``shine_adapter_node()`` to avoid holding
    GPU memory across graph steps.
    """

    def __init__(self, backbone: str = "Qwen/Qwen2.5-7B", device: str = "cuda"):
        self._backbone = backbone
        self._device = device
        self._shine: Any = None

    def _get_shine(self) -> Any:
        """Lazy-load SHINE model (expensive — loads weights on first use)."""
        if self._shine is None and _check_shine():
            self._shine = _ShineHypernet(
                backbone=self._backbone,
                device=self._device,
            )
        return self._shine

    def run(self, state: dict) -> dict:
        """Generate LoRA or fallback to text corpus.

        Args:
            state: DocumentState dict.

        Returns:
            Partial state update with ``shine_active`` and optionally
            ``shine_lora``.
        """
        # ── Skip conditions (§RAG_SHINE_INTEGRATION fallback rules) ──────

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
        outline = state.get("outline", [])
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

        # ── Generate LoRA ────────────────────────────────────────────────

        shine = self._get_shine()
        if shine is None:
            return {"shine_active": False}

        try:
            lora = shine.generate_lora(corpus, max_length=1150)  # ~0.3s on GPU
            logger.info(
                "✅ SHINE LoRA generated for section %d (%d chars corpus)",
                section_idx, len(corpus),
            )
            return {
                "shine_lora": lora,
                "shine_active": True,
            }
        except Exception as exc:
            logger.error("SHINE failed: %s — falling back to text corpus", exc)
            return {"shine_active": False}


# ── Node function for LangGraph ──────────────────────────────────────────────

def shine_adapter_node(state: dict) -> dict:
    """Graph-compatible node function."""
    adapter = ShineAdapter()
    return adapter.run(state)
