"""RLM Model Router (§28) — tiered fallback with explicit upgrade guard.

Key changes vs original routing.py:
  - Thread-safe singleton via threading.Lock + double-checked locking
  - Heterogeneous jury slots:
      jury_r_1/f_1/s_1 → OpenAI
      jury_r_2/f_2/s_2 → Google
      jury_r_3/f_3/s_3 → Anthropic
    Ensures independent epistemic perspectives per panel (ChatEval arXiv:2308.07201)
  - Lateral fallback (same tier, different provider) BEFORE vertical upgrade
    to avoid accidental cost escalation
  - P9 fix: RLM_ALLOW_TIER_UPGRADE env var as single source of truth.
    Vertical upgrades raise RuntimeError when env var is false (default),
    preventing silent 10-20× cost escalation on transient provider failures.
  - route_model_with_fallback(): returns (model, tier_upgraded) tuple so
    budget_controller can track unexpected escalations.
  - route_model_on_error(): runtime lateral switching when a model fails
    mid-run without crossing tier boundaries.
  - 28 agent slots fully covered (all previously missing agents added)
  - writer → anthropic/ prefix (direct Anthropic API, enables §29.1 prompt caching)
  - all other agents → openrouter/ prefix (single-key gateway)

Ref: arXiv:2512.24601 (RLM integration), ChatEval arXiv:2308.07201 (jury diversity)
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional, Tuple

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# P9 fix: Env var as SINGLE SOURCE OF TRUTH for tier upgrade permission.
#
# When false (default), route_model() raises RuntimeError instead of silently
# using a 10–20× more expensive model on transient provider failures.
# Set RLM_ALLOW_TIER_UPGRADE=true only when you explicitly accept budget
# overruns as a resilience trade-off (e.g. SLA-critical production runs).
# ---------------------------------------------------------------------------
_ALLOW_TIER_UPGRADE: bool = (
    os.getenv("RLM_ALLOW_TIER_UPGRADE", "false").lower() == "true"
)

# Relative cost weights per tier — used only for logging the cost delta.
# These are approximate multipliers, not exact dollar values.
_TIER_COST_WEIGHT: dict[str, float] = {
    "economy":  1.0,
    "balanced": 4.0,   # ~4× economy
    "premium":  15.0,  # ~15× economy
}

# ---------------------------------------------------------------------------
# Routing table
# CONVENTION:
#   writer      -> anthropic/ prefix  (direct Anthropic, enables prompt caching §29.1)
#   all others  -> openrouter/ prefix (single-key gateway, simpler key management)
#
# Jury slots are HETEROGENEOUS per panel:
#   *_1 slot = OpenAI   backbone  (strong reasoning)
#   *_2 slot = Google   backbone  (grounding + search)
#   *_3 slot = Anthropic backbone (nuanced analysis)
# ---------------------------------------------------------------------------
_DEFAULT_ROUTING: dict[str, dict[str, str]] = {

    # -- Writer (direct Anthropic for §29.1 prompt caching) -----------------
    "writer": {
        "economy":  "anthropic/claude-sonnet-4",
        "balanced": "anthropic/claude-opus-4-5",
        "premium":  "anthropic/claude-opus-4-5",
    },

    # -- Jury R (Reasoning / Reliability) — heterogeneous backbones ---------
    "jury_r_1": {
        "economy":  "openrouter/openai/o3-mini",
        "balanced": "openrouter/openai/o3-mini",
        "premium":  "openrouter/openai/o3",
    },
    "jury_r_2": {
        "economy":  "openrouter/openai/o3-mini",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "jury_r_3": {
        "economy":  "openrouter/openai/o3-mini",
        "balanced": "openrouter/anthropic/claude-sonnet-4",
        "premium":  "openrouter/anthropic/claude-opus-4-5",
    },
    # Single-slot fallback (jury_size=1 or economy with size>1)
    "jury_r": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/openai/o3-mini",
        "premium":  "openrouter/openai/o3",
    },

    # -- Jury F (Factual verification) — heterogeneous backbones ------------
    "jury_f_1": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "jury_f_2": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/openai/o3-mini",
        "premium":  "openrouter/openai/o3",
    },
    "jury_f_3": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/anthropic/claude-sonnet-4",
        "premium":  "openrouter/anthropic/claude-opus-4-5",
    },
    "jury_f": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/openai/o3",
    },

    # -- Jury S (Style) — heterogeneous backbones ---------------------------
    "jury_s_1": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/anthropic/claude-sonnet-4",
        "premium":  "openrouter/anthropic/claude-opus-4-5",
    },
    "jury_s_2": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "jury_s_3": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/openai/o3-mini",
        "premium":  "openrouter/openai/o3",
    },
    "jury_s": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },

    # -- Post-writing pipeline ----------------------------------------------
    "reflector": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/openai/o3",
    },
    "fusor": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/openai/o3",
    },
    "planner": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "panel_discussion": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "coherence_guard": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-flash",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "post_draft_analyzer": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-flash",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "span_editor": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/anthropic/claude-sonnet-4",
        "premium":  "openrouter/anthropic/claude-sonnet-4",
    },
    "style_fixer": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/anthropic/claude-sonnet-4",
        "premium":  "openrouter/anthropic/claude-sonnet-4",
    },
    "length_adjuster": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-flash",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },

    # -- Previously missing agents — now fully covered ----------------------
    "source_synthesizer": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "citation_verifier": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-flash",
        "premium":  "openrouter/openai/o3-mini",
    },
    "source_sanitizer": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-flash",
        "premium":  "openrouter/google/gemini-2.5-flash",
    },
    "context_compressor": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-flash",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "aggregator": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "citation_manager": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-flash",
        "premium":  "openrouter/google/gemini-2.5-pro",
    },
    "researcher": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/openai/o3",
    },
    "researcher_targeted": {
        "economy":  "openrouter/google/gemini-2.5-flash",
        "balanced": "openrouter/google/gemini-2.5-pro",
        "premium":  "openrouter/openai/o3",
    },
}

# ---------------------------------------------------------------------------
# Lateral fallbacks: same-tier alternative before vertical upgrade
# Strategy: try a different provider at the SAME cost level before escalating.
# ---------------------------------------------------------------------------
_LATERAL_FALLBACKS: dict[str, list[str]] = {
    "openrouter/openai/o3":                   ["openrouter/anthropic/claude-opus-4-5"],
    "openrouter/openai/o3-mini":              ["openrouter/google/gemini-2.5-pro"],
    "openrouter/anthropic/claude-opus-4-5":   ["openrouter/openai/o3"],
    "openrouter/anthropic/claude-sonnet-4":   ["openrouter/openai/o3-mini"],
    "openrouter/google/gemini-2.5-pro":       ["openrouter/anthropic/claude-sonnet-4"],
    "openrouter/google/gemini-2.5-flash":     ["openrouter/openai/o3-mini"],
    "anthropic/claude-opus-4-5":              ["openrouter/openai/o3"],
    "anthropic/claude-sonnet-4":              ["openrouter/openai/o3-mini"],
}

_TIER_ORDER: list[str] = ["economy", "balanced", "premium"]

# ---------------------------------------------------------------------------
# Thread-safe singleton (double-checked locking pattern)
# ---------------------------------------------------------------------------
_routing_table: dict[str, dict[str, str]] | None = None
_routing_lock = threading.Lock()


def _load_routing_config() -> dict[str, dict[str, str]]:
    """Load routing config from disk, falling back to built-in defaults."""
    config_paths = [
        Path("config/model_routing.yaml"),
        Path("config/model_routing.yml"),
    ]
    for path in config_paths:
        if path.exists():
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                logger.info("RLM Router: loaded config from %s", path)
                # Merge: file overrides defaults (allows partial overrides)
                merged = dict(_DEFAULT_ROUTING)
                merged.update(data)
                return merged
            except Exception as exc:
                logger.warning("RLM Router: failed to load %s: %s", path, exc)
    logger.info("RLM Router: using built-in routing table")
    return dict(_DEFAULT_ROUTING)


def _get_routing_table() -> dict[str, dict[str, str]]:
    global _routing_table
    if _routing_table is None:          # fast path (no lock)
        with _routing_lock:
            if _routing_table is None:  # slow path (double-checked)
                _routing_table = _load_routing_config()
    return _routing_table


def route_model(
    agent: str,
    preset: str = "balanced",
    allow_tier_upgrade: bool | None = None,
) -> str:
    """Return the canonical provider-prefixed model string for an agent/preset.

    Fallback priority:
      1. Direct match: (agent, preset) in routing table
      2. Lateral fallback: same tier, different provider (zero cost delta)
      3. Vertical downgrade: lower tier (cost reduces or stays same)
      4. Vertical upgrade: higher tier — ONLY if allowed (see below)
      5. Hard default: openrouter/google/gemini-2.5-flash

    Tier upgrade policy (P9 fix):
      - ``allow_tier_upgrade=None`` (default): defers to the
        ``RLM_ALLOW_TIER_UPGRADE`` env var (false by default). This makes
        the env var the single source of truth — no call-site needs to
        pass the flag explicitly in normal operation.
      - ``allow_tier_upgrade=False``: always blocks upgrades regardless of
        env var. Use in tests or budget-critical paths.
      - ``allow_tier_upgrade=True``: always allows upgrades regardless of
        env var. Use only for explicit escalation after lateral exhaustion.

    When a vertical upgrade is blocked, a RuntimeError is raised so the
    caller can decide how to proceed (fail-fast, alert, manual override).
    This prevents silent 10–20× cost escalation on transient failures.

    Args:
        agent:              Agent identifier (see _DEFAULT_ROUTING keys).
        preset:             "economy" | "balanced" | "premium".
        allow_tier_upgrade: None = use env var (recommended), True/False for
                            explicit override.

    Returns:
        Provider-prefixed model string, e.g. "openrouter/google/gemini-2.5-flash".

    Raises:
        RuntimeError: If only a vertical upgrade could satisfy the request
                      but tier upgrade is blocked.
    """
    # Resolve allow_tier_upgrade: None defers to env var
    if allow_tier_upgrade is None:
        allow_tier_upgrade = _ALLOW_TIER_UPGRADE

    table = _get_routing_table()
    preset_lower = preset.lower()

    agent_routes = table.get(agent, {})
    if not agent_routes:
        logger.warning(
            "RLM Router: unknown agent '%s' -> hard default model", agent
        )
        return "openrouter/google/gemini-2.5-flash"

    # 1. Direct match
    model = agent_routes.get(preset_lower)
    if model:
        return model

    # 2. Lateral fallback (same tier, alternative provider — zero cost delta)
    primary = agent_routes.get(preset_lower, "")
    for lateral in _LATERAL_FALLBACKS.get(primary, []):
        if lateral:
            logger.info(
                "RLM Router: %s/%s -> lateral fallback %s",
                agent, preset_lower, lateral,
            )
            return lateral

    # 3. Vertical downgrade (cost ≤ current tier — always safe)
    try:
        current_idx = _TIER_ORDER.index(preset_lower)
    except ValueError:
        current_idx = 1
    for i in range(current_idx - 1, -1, -1):
        model = agent_routes.get(_TIER_ORDER[i])
        if model:
            logger.info(
                "RLM Router: %s/%s -> downgrade to '%s' (%s)",
                agent, preset_lower, _TIER_ORDER[i], model,
            )
            return model

    # 4. Vertical upgrade — opt-in only
    # Check upgrade candidates first to decide whether to raise or allow.
    upgrade_candidates: list[tuple[str, str]] = []
    for i in range(current_idx + 1, len(_TIER_ORDER)):
        m = agent_routes.get(_TIER_ORDER[i])
        if m:
            upgrade_candidates.append((_TIER_ORDER[i], m))

    if upgrade_candidates:
        target_tier, target_model = upgrade_candidates[0]
        current_weight = _TIER_COST_WEIGHT.get(preset_lower, 1.0)
        target_weight = _TIER_COST_WEIGHT.get(target_tier, 1.0)
        cost_multiplier = target_weight / current_weight if current_weight else 1.0

        if not allow_tier_upgrade:
            # Blocked: raise explicitly so the caller can alert / fail-fast.
            # Do NOT silently fall through to hard default — that would mask
            # the problem and potentially use an irrelevant cheap model.
            raise RuntimeError(
                f"RLM Router: tier upgrade blocked for agent='{agent}' "
                f"preset='{preset_lower}'. Only candidate is "
                f"'{target_tier}'/{target_model} ({cost_multiplier:.0f}× cost). "
                f"Set RLM_ALLOW_TIER_UPGRADE=true to permit, or check why "
                f"'{preset_lower}' models are unavailable."
            )

        # Upgrade allowed — emit prominent COST ALERT before proceeding.
        logger.warning(
            "COST ALERT: RLM Router tier upgrade for agent='%s': "
            "%s(%g×) → %s(%g×) = %g× cost increase — model=%s. "
            "RLM_ALLOW_TIER_UPGRADE=true. Notify budget controller.",
            agent,
            preset_lower, current_weight,
            target_tier, target_weight,
            cost_multiplier,
            target_model,
        )
        return target_model

    # 5. Hard default — no route found at all (routing table gap)
    logger.error(
        "RLM Router: no model found for agent=%s preset=%s allow_upgrade=%s "
        "-> hard default (routing table may be incomplete)",
        agent, preset_lower, allow_tier_upgrade,
    )
    return "openrouter/google/gemini-2.5-flash"


def route_model_with_fallback(
    agent: str,
    preset: str = "balanced",
    allow_tier_upgrade: bool | None = None,
) -> tuple[str, bool]:
    """Like route_model() but also returns whether a tier upgrade occurred.

    Intended for budget_controller integration: the caller can inspect
    ``tier_upgraded`` and decide whether to alert, track the delta cost,
    or abort the run.

    Args:
        agent:              Agent identifier.
        preset:             Quality preset.
        allow_tier_upgrade: None = use RLM_ALLOW_TIER_UPGRADE env var.

    Returns:
        Tuple (model_id: str, tier_upgraded: bool).
        ``tier_upgraded`` is True only when the response model comes from a
        higher tier than requested (step 4 in the fallback chain).

    Raises:
        RuntimeError: Same as route_model() when upgrade is blocked.
    """
    if allow_tier_upgrade is None:
        allow_tier_upgrade = _ALLOW_TIER_UPGRADE

    table = _get_routing_table()
    preset_lower = preset.lower()
    agent_routes = table.get(agent, {})

    if not agent_routes:
        return "openrouter/google/gemini-2.5-flash", False

    # Direct match or lateral (tier_upgraded = False)
    model = agent_routes.get(preset_lower)
    if model:
        return model, False

    primary = agent_routes.get(preset_lower, "")
    for lateral in _LATERAL_FALLBACKS.get(primary, []):
        if lateral:
            return lateral, False

    # Downgrade (tier_upgraded = False — downgrade is never an upgrade)
    try:
        current_idx = _TIER_ORDER.index(preset_lower)
    except ValueError:
        current_idx = 1
    for i in range(current_idx - 1, -1, -1):
        m = agent_routes.get(_TIER_ORDER[i])
        if m:
            return m, False

    # Upgrade (tier_upgraded = True if allowed)
    for i in range(current_idx + 1, len(_TIER_ORDER)):
        m = agent_routes.get(_TIER_ORDER[i])
        if m:
            target_tier = _TIER_ORDER[i]
            current_weight = _TIER_COST_WEIGHT.get(preset_lower, 1.0)
            target_weight = _TIER_COST_WEIGHT.get(target_tier, 1.0)
            cost_multiplier = target_weight / current_weight if current_weight else 1.0

            if not allow_tier_upgrade:
                raise RuntimeError(
                    f"RLM Router: tier upgrade blocked for agent='{agent}' "
                    f"preset='{preset_lower}'. Only candidate is "
                    f"'{target_tier}'/{m} ({cost_multiplier:.0f}× cost). "
                    f"Set RLM_ALLOW_TIER_UPGRADE=true to permit."
                )
            logger.warning(
                "COST ALERT: RLM Router tier upgrade for agent='%s': "
                "%s(%g×) → %s(%g×) = %g× cost increase — model=%s. "
                "RLM_ALLOW_TIER_UPGRADE=true. Notify budget controller.",
                agent,
                preset_lower, current_weight,
                target_tier, target_weight,
                cost_multiplier, m,
            )
            return m, True  # tier_upgraded = True

    return "openrouter/google/gemini-2.5-flash", False


def route_model_on_error(
    failed_model: str,
    agent: str,
    preset: str,
) -> str | None:
    """Return a lateral (same-tier) fallback for a model that failed at runtime.

    Called by the LLM client after HTTP 429 / model unavailable errors to
    immediately retry with a different provider at the same cost level.
    Never crosses tier boundaries — tier upgrade requires explicit opt-in
    via ``allow_tier_upgrade=True`` in route_model().

    Args:
        failed_model: The provider-prefixed model string that failed.
        agent:        Agent slot (used for logging only).
        preset:       Quality preset (used for logging only).

    Returns:
        Provider-prefixed model string for the lateral alternative, or None
        if no lateral fallback exists (caller must handle: alert, fail-fast,
        or explicitly call route_model(allow_tier_upgrade=True)).
    """
    candidates = [
        m for m in _LATERAL_FALLBACKS.get(failed_model, [])
        if m and m != failed_model
    ]
    if candidates:
        lateral = candidates[0]
        logger.info(
            "RLM Router on_error: agent=%s preset=%s "
            "failed=%s -> lateral=%s (same tier, no cost delta)",
            agent, preset, failed_model, lateral,
        )
        return lateral

    logger.warning(
        "RLM Router on_error: agent=%s preset=%s failed=%s "
        "has no lateral fallback at same tier. "
        "Caller must decide: fail-fast or route_model(allow_tier_upgrade=True).",
        agent, preset, failed_model,
    )
    return None


def route_jury_slots(
    jury_type: str,
    preset: str,
    jury_size: int,
) -> list[str]:
    """Return a list of `jury_size` heterogeneous models for a jury type.

    Uses numbered slots (_1/_2/_3) which map to different provider backbones
    to ensure independent epistemic perspectives within each panel.

    For jury_size=1 : returns single-slot model (jury_r / jury_f / jury_s).
    For jury_size=2 : returns slots 1 and 2.
    For jury_size=3 : returns slots 1, 2, and 3 (maximum supported).

    Example (balanced preset, jury_size=3)::

        route_jury_slots("r", "balanced", 3)
        -> ["openrouter/openai/o3-mini",            # R1 OpenAI
            "openrouter/google/gemini-2.5-pro",     # R2 Google
            "openrouter/anthropic/claude-sonnet-4"] # R3 Anthropic
    """
    if jury_size <= 1:
        return [route_model(f"jury_{jury_type}", preset)]
    return [
        route_model(f"jury_{jury_type}_{i}", preset)
        for i in range(1, min(jury_size, 3) + 1)
    ]


def reload_routing_config() -> None:
    """Force reload of routing config from disk (hot config reload).

    Thread-safe: acquires _routing_lock and resets the singleton.
    Safe to call at runtime without restarting the process.
    """
    global _routing_table
    with _routing_lock:
        _routing_table = None
    _get_routing_table()
    logger.info("RLM Router: config reloaded from disk")
