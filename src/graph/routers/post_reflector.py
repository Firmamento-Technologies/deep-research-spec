"""Route after reflector — §12.5 canonical."""
from __future__ import annotations
from typing import Literal


def route_after_reflector(state: dict) -> Literal["oscillation_check", "await_human"]:
    """Route based on reflector_output.dominant_scope. §12.5.

    FULL     → await_human directly (argument structurally broken;
               oscillation detection irrelevant)
    SURGICAL → oscillation_check
    PARTIAL  → oscillation_check
    """
    ro = state.get("reflector_output", {})
    scope = ro.get("dominant_scope", ro.get("scope", "PARTIAL"))
    if scope == "FULL":
        return "await_human"
    return "oscillation_check"
