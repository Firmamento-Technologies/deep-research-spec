"""Route after panel discussion — §9.5."""
from __future__ import annotations
from typing import Literal


def route_after_panel_internal(state: dict) -> Literal["panel_discussion", "aggregator"]:
    """Self-loop or return to aggregator after panel round. §9.5.

    Returns 'panel_discussion' if additional rounds remain,
    otherwise 'aggregator' to re-evaluate CSS with updated verdicts.
    """
    panel_max_rounds: int = state.get("config", {}).get(
        "convergence", {}
    ).get("panel_max_rounds", 2)
    if state.get("panel_round", 0) < panel_max_rounds:
        return "panel_discussion"
    return "aggregator"
