"""Route after aggregator — §9.4 CANONICAL.

This is the single authoritative definition of route_after_aggregator().
Do not define this function elsewhere.
"""
from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

AggregatorRoute = Literal[
    "approved",
    "force_approve",
    "fail_style",
    "fail_missing_ev",
    "fail_reflector",
    "panel",
    "veto",
    "budget_hard_stop",
]

# L1 veto categories — any single judge with these blocks unconditionally
_VETO_CATEGORIES_L1: set[str] = {
    "fabricated_source",
    "factual_error",
    "logical_contradiction",
    "plagiarism",
}


def _get_thresholds(state: dict) -> dict[str, float]:
    """Read thresholds from budget state. §9.3 / §9.4."""
    budget = state.get("budget", {})
    if budget.get("css_content_threshold") and budget.get("css_style_threshold"):
        return {
            "css_content_threshold": budget["css_content_threshold"],
            "css_style_threshold": budget["css_style_threshold"],
            "css_panel_trigger": budget.get("css_panel_threshold", 0.50),
        }
    # Fallback: derive from quality_preset via THRESHOLD_TABLE
    from src.budget.regime import THRESHOLD_TABLE
    preset: str = state.get("config", {}).get("user", {}).get("quality_preset", "balanced")
    return THRESHOLD_TABLE.get(preset.lower(), THRESHOLD_TABLE["balanced"])


def route_after_aggregator(state: dict) -> AggregatorRoute:
    """Canonical routing after aggregator. §9.4.

    Priority order:
      force_approve > budget_hard_stop > veto > panel >
      missing_ev > content_gate > style_pass > fail_reflector
    """
    budget = state.get("budget", {})
    verdicts = state.get("jury_verdicts", [])
    # Support both field naming conventions
    css_content = state.get("css_content_current", state.get("css_content", 0.0))
    css_style = state.get("css_style_current", state.get("css_style", 0.0))
    thresholds = _get_thresholds(state)

    # ── Priority 0: Force-approve (iteration cap reached — §19.5) ────────
    if state.get("force_approve", False):
        logger.warning(
            "FORCE_APPROVE: section_idx=%s reached max_iterations without "
            "CSS convergence. Forcing approval.",
            state.get("current_section_idx"),
        )
        return "force_approve"

    # ── Priority 1: Budget Hard Stop ─────────────────────────────────────
    if budget.get("hard_stop_fired", False) or (
        budget.get("spent_dollars", 0) >= budget.get("max_dollars", float("inf"))
    ):
        return "budget_hard_stop"

    # ── Priority 2: Minority Veto L1 (individual judge) ──────────────────
    for v in verdicts:
        if v.get("veto_category") in _VETO_CATEGORIES_L1:
            return "veto"

    # ── Priority 3: Minority Veto L2 (full mini-jury unanimous FAIL) ──────
    r_verdicts = [v for v in verdicts if v.get("judge_slot", "").startswith("R")]
    f_verdicts = [v for v in verdicts if v.get("judge_slot", "").startswith("F")]
    if (r_verdicts and all(v.get("pass_fail") is False for v in r_verdicts)) \
    or (f_verdicts and all(v.get("pass_fail") is False for v in f_verdicts)):
        return "veto"

    # ── Priority 4: Panel Discussion Trigger ─────────────────────────────
    panel_max_rounds: int = state.get("config", {}).get(
        "convergence", {}
    ).get("panel_max_rounds", 2)
    if css_content < thresholds["css_panel_trigger"] \
    and state.get("panel_round", 0) < panel_max_rounds:
        return "panel"

    # ── Priority 5: Content Gate PASS check ──────────────────────────────
    content_passes = css_content >= thresholds["css_content_threshold"]

    if not content_passes:
        # Check if Judge F flagged missing_evidence specifically
        missing_ev_flags = [
            v for v in f_verdicts
            if v.get("missing_evidence") and not v.get("pass_fail")
        ]
        if missing_ev_flags:
            return "fail_missing_ev"
        return "fail_reflector"

    # ── Priority 6: Style Pass check ─────────────────────────────────────
    style_passes = css_style >= thresholds["css_style_threshold"]
    if not style_passes:
        return "fail_style"

    # ── All gates cleared ─────────────────────────────────────────────────
    return "approved"
