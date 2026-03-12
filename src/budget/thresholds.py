"""Threshold utilities — §9.3 public API.

This module provides a stable API for reading and validating CSS thresholds.
All threshold values originate from THRESHOLD_TABLE in regime.py (§9.3 SSOT).
"""
from __future__ import annotations

from typing import Literal

from src.budget.regime import THRESHOLD_TABLE, populate_budget_thresholds

# Re-export for convenience — callers can import from here
__all__ = [
    "THRESHOLD_TABLE",
    "populate_budget_thresholds",
    "get_thresholds_for_regime",
    "validate_threshold_invariants",
]


def get_thresholds_for_regime(
    regime: str,
) -> dict[str, float]:
    """Return the threshold dict for a given regime. §9.3.

    Args:
        regime: One of ``"Economy"``, ``"Balanced"``, ``"Premium"``
                (case-insensitive — C14 resolution).

    Returns:
        Dict with keys ``css_content_threshold``, ``css_style_threshold``,
        ``css_panel_trigger``.

    Raises:
        KeyError: If regime is not in THRESHOLD_TABLE.
    """
    return dict(THRESHOLD_TABLE[regime.lower()])


def validate_threshold_invariants(regime: str | None = None) -> list[str]:
    """Validate the §9.3 invariants for one or all regimes.

    Invariants checked:
        - css_style_threshold >= css_content_threshold
          (style pass is stricter than content gate)
        - css_panel_trigger < css_content_threshold
          (panel only triggers below approval threshold)

    Args:
        regime: Specific regime to validate (case-insensitive),
                or ``None`` to validate all.

    Returns:
        List of violation messages (empty = all OK).
    """
    violations: list[str] = []
    regimes = [regime.lower()] if regime else list(THRESHOLD_TABLE.keys())

    for r in regimes:
        t = THRESHOLD_TABLE.get(r)
        if t is None:
            violations.append(f"Unknown regime: {r!r}")
            continue

        content = t["css_content_threshold"]
        style = t["css_style_threshold"]
        panel = t["css_panel_trigger"]

        if style < content:
            violations.append(
                f"{r}: css_style_threshold ({style}) < css_content_threshold ({content})"
            )
        if panel >= content:
            violations.append(
                f"{r}: css_panel_trigger ({panel}) >= css_content_threshold ({content})"
            )

    return violations


def thresholds_match_regime_params() -> list[str]:
    """Cross-check that THRESHOLD_TABLE content values match REGIME_PARAMS. §19.2.

    Returns:
        List of mismatch messages (empty = all OK).
    """
    from src.budget.regime import REGIME_PARAMS

    mismatches: list[str] = []
    mapping = {
        "Economy": "economy",
        "Balanced": "balanced",
        "Premium": "premium",
    }

    for regime_key, table_key in mapping.items():
        rp = REGIME_PARAMS.get(regime_key, {})
        tt = THRESHOLD_TABLE.get(table_key, {})

        rp_css = rp.get("css_threshold")  # Note: regime.py may not have this
        tt_css = tt.get("css_content_threshold")

        # Only check if REGIME_PARAMS has a css_threshold field
        if rp_css is not None and tt_css is not None and rp_css != tt_css:
            mismatches.append(
                f"{regime_key}: REGIME_PARAMS.css_threshold ({rp_css}) != "
                f"THRESHOLD_TABLE.css_content_threshold ({tt_css})"
            )

    return mismatches
