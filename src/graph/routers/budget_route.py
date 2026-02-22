"""Route after budget controller — §4.5."""
from __future__ import annotations
from typing import Literal


def route_budget(state: dict) -> Literal["continue", "hard_stop"]:
    """Route based on budget status. §4.5.

    'hard_stop' routes to publisher (partial document) when budget exhausted.
    'continue' routes to the next node in the writer/jury pipeline.
    """
    budget = state.get("budget", {})
    # Check both hard_stop_fired flag and spent vs max comparison
    if budget.get("hard_stop_fired", False):
        return "hard_stop"
    if budget.get("spent_dollars", 0) >= budget.get("max_dollars", float("inf")):
        return "hard_stop"
    return "continue"
