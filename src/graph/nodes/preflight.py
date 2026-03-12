"""Preflight node (§5.1) — validate configuration and dependencies.

PRIMO NODO DELLA PIPELINE. È L'UNICO punto in cui quality_preset viene
letto dall'input utente e normalizzato al canonical lowercase.
Tutti i nodi downstream leggono state["quality_preset"] già normalizzato.

Qualità preset flow:
  1. Utente passa config["quality_preset"] = "Balanced" (qualsiasi case)
  2. preflight_node() chiama normalize_preset() → "balanced"
  3. Scrive {"quality_preset": "balanced"} nel return top-level
  4. Scrive budget["regime"] = "balanced" (campo BudgetState corretto)
  5. NESSUN altro nodo deve normalizzare quality_preset
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from src.graph._presets import normalize_preset

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

    Normalizzazione quality_preset:
      Legge il preset grezzo con la seguente priorità decrescente:
        1. state["quality_preset"]          (se il grafo viene resume-ato)
        2. config["user"]["quality_preset"] (config utente strutturata)
        3. config["quality_preset"]         (config flat)
        4. DEFAULT_PRESET ("balanced")      (fallback finale)

      Chiama normalize_preset() e scrive il risultato lowercase in:
        - return["quality_preset"]  → DocumentState.quality_preset
        - budget["regime"]          → BudgetState.regime

      NON scrive più budget["quality_preset"] — quel campo non esiste in
      BudgetState e veniva silenziosamente scartato dal checkpointer.

    Returns:
        Partial state update con:
          - ``quality_preset``     — canonical lowercase preset
          - ``budget``             — dict BudgetState inizializzato
          - ``preflight_warnings`` — lista warning non bloccanti
    """
    warnings: list[str] = []
    config = state.get("config", {}) or {}

    # ── API key check ───────────────────────────────────────────────────────────
    available_keys = [
        key for key in _RECOMMENDED_KEYS if os.environ.get(key)
    ]
    for key in _RECOMMENDED_KEYS:
        if not os.environ.get(key):
            warnings.append(f"Missing recommended env var: {key}")
    if not available_keys:
        warnings.append("No LLM API keys found — pipeline will use fallback/stub modes")

    # ── Normalize quality_preset — UNICO PUNTO DI NORMALIZZAZIONE ─────────────
    # Priorità: state > config.user > config > DEFAULT_PRESET
    # normalize_preset() gestisce: None, stringa vuota, TitleCase,
    # UPPERCASE, lowercase, e valori sconosciuti (fallback con warning).
    user_cfg: dict = (config.get("user") or {})
    raw_preset: str | None = (
        state.get("quality_preset")          # già normalizzato (resume)
        or user_cfg.get("quality_preset")    # config utente strutturata
        or config.get("quality_preset")      # config flat
    )
    quality_preset = normalize_preset(raw_preset)

    # ── Budget initialization ──────────────────────────────────────────────────
    budget = dict(state.get("budget") or {})
    if not budget.get("max_dollars"):
        budget.setdefault("max_dollars", 10.0)
        budget.setdefault("spent_dollars", 0.0)
        warnings.append("No budget.max_dollars set — defaulting to $10.00")

    # Scrivi il preset normalizzato in BudgetState.regime (campo CORRETTO).
    # NON usare budget["quality_preset"]: quel campo non è dichiarato in
    # BudgetState TypedDict — il LangGraph checkpointer lo scarta al resume.
    budget["regime"] = quality_preset

    # ── Topic / outline check ────────────────────────────────────────────────
    topic: str = state.get("topic", config.get("topic", ""))
    if not topic and not state.get("outline"):
        warnings.append("No topic or outline provided")

    # ── SHINE activation — data-driven (§1.9 frontier strategy) ───────────────
    # Instead of global flag, activate SHINE based on estimated context size
    # relative to model's native context window.
    # Economy (Qwen3.5-9B, 262k): SHINE only if > 200k tokens
    # Balanced (Qwen3.5-35B, 1M): SHINE only if > 800k tokens
    # Premium (Sonnet, 200k): SHINE almost always active
    shine_context_thresholds = {
        "economy": 200_000,
        "balanced": 800_000,
        "premium": 50_000,   # low threshold → almost always active
    }
    estimated_context = config.get("estimated_context_tokens", 0)
    shine_threshold = shine_context_thresholds.get(quality_preset, 200_000)
    shine_active = estimated_context > shine_threshold or config.get("shine_active", False)

    # ── RLM mode — dynamic activation (§1.9 frontier strategy) ──────────────
    # RLM activates when:
    # 1. Explicitly requested in config, OR
    # 2. Premium preset with large context (data-driven, not global flag)
    # At runtime, cascade_controller may also activate RLM based on
    # CSS < 0.35 AND oscillation > 1 (see src/budget/cascade_controller.py).
    rlm_mode: bool = bool(config.get("rlm_mode", False))
    if quality_preset == "premium" and estimated_context > 100_000:
        rlm_mode = True

    # ── Output directory ─────────────────────────────────────────────────────
    doc_id: str = state.get("doc_id", "default")
    output_dir = Path("output") / doc_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Preflight: %d API keys available, %d warnings, "
        "budget=$%.2f, preset=%s, rlm_mode=%s",
        len(available_keys),
        len(warnings),
        budget.get("max_dollars", 0),
        quality_preset,
        rlm_mode,
    )

    return {
        "quality_preset":      quality_preset,   # DocumentState top-level
        "rlm_mode":            rlm_mode,
        "shine_active":        shine_active,
        "preflight_passed":    len(warnings) < 5,
        "preflight_warnings":  warnings,
        "budget":              budget,
    }
