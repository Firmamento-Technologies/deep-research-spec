"""Canonical quality preset definitions — fonte di verità unica.

Convenzione: lowercase ovunque nel codice.
I label visibili all'utente ("Economy", "Balanced", "Premium") esistono
exclusivamente in PRESET_LABELS per display/report.

Regola di importazione:
  from src.graph._presets import QualityPreset, normalize_preset, DEFAULT_PRESET

Flusso di normalizzazione:
  1. L'utente può passare "Economy", "BALANCED", "premium", "Balanced", ecc.
  2. preflight_node chiama normalize_preset() UNA VOLTA.
  3. Il valore scritto in DocumentState.quality_preset è sempre lowercase.
  4. Tutti i nodi downstream leggono il valore già normalizzato—
     nessun .lower() sparso nel codice.

Perché non TitleCase:
  La routing table in src/llm/routing.py usa lowercase come chiavi
  (_DEFAULT_ROUTING: dict[str, dict[str, str]] dove ogni sotto-dict ha
  "economy", "balanced", "premium"). Allineare il contratto di stato
  alla convenzione interna del router elimina il mismatch alla radice.
"""
from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# ── Tipo canonico ─────────────────────────────────────────────────────────
# Usato in:
#   DocumentState.quality_preset  (src/graph/state.py)
#   BudgetState.regime            (src/graph/state.py)
#   route_model() preset param    (src/llm/routing.py, come str)
QualityPreset = Literal["economy", "balanced", "premium"]

# Default quando l'utente non specifica un preset.
DEFAULT_PRESET: QualityPreset = "balanced"

# Label visibili all'utente (solo per display e log finali).
PRESET_LABELS: dict[str, str] = {
    "economy":  "Economy",
    "balanced": "Balanced",
    "premium":  "Premium",
}

# Sinonimi accettati: mappa varianti → canonical lowercase.
# Copre input dell'utente, vecchi config YAML, e costanti TitleCase precedenti.
_ALIASES: dict[str, QualityPreset] = {
    "economy":    "economy",
    "Economy":    "economy",
    "ECONOMY":    "economy",
    "balanced":   "balanced",
    "Balanced":   "balanced",
    "BALANCED":   "balanced",
    "premium":    "premium",
    "Premium":    "premium",
    "PREMIUM":    "premium",
    # Legacy alias che può arrivare da vecchi config
    "max_quality": "premium",
    "Max_Quality": "premium",
}

# Set per lookup O(1) post-normalizzazione
_VALID_PRESETS: frozenset[str] = frozenset(PRESET_LABELS.keys())


def normalize_preset(value: str | None) -> QualityPreset:
    """Normalizza qualsiasi stringa preset al canonical lowercase.

    QUESTA È L'UNICA FUNZIONE DI NORMALIZZAZIONE DEL CODEBASE.
    Deve essere chiamata esclusivamente da preflight_node() all'ingresso
    della pipeline. Tutti gli altri nodi ricevono il valore già normalizzato.

    Args:
        value: Valore grezzo dal config utente o dallo state. Può essere None,
               stringa vuota, TitleCase, UPPERCASE, lowercase, o alias legacy.

    Returns:
        "economy" | "balanced" | "premium" (mai None)

    Examples:
        normalize_preset("Economy")    -> "economy"
        normalize_preset("BALANCED")   -> "balanced"
        normalize_preset("premium")    -> "premium"
        normalize_preset(None)         -> "balanced"  (DEFAULT_PRESET)
        normalize_preset("invalid")    -> "balanced"  (DEFAULT_PRESET + warning)
        normalize_preset("max_quality")-> "premium"   (legacy alias)
    """
    if not value:
        return DEFAULT_PRESET

    # Lookup diretto con aliases (case-sensitive per le varianti comuni)
    canonical = _ALIASES.get(value)
    if canonical:
        return canonical

    # Fallback: .lower() generico per varianti non previste
    lower = value.strip().lower()
    if lower in _VALID_PRESETS:
        return lower  # type: ignore[return-value]

    logger.warning(
        "_presets.normalize_preset: valore sconosciuto '%s' — "
        "fallback a DEFAULT_PRESET '%s'. Aggiornare _ALIASES se è un "
        "valore legittimo non ancora mappato.",
        value,
        DEFAULT_PRESET,
    )
    return DEFAULT_PRESET
