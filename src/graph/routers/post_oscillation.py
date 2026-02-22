"""Route after oscillation check — §12.5, §4.5."""
from __future__ import annotations
from typing import Literal


def route_after_oscillation(state: dict) -> Literal[
    "span_editor", "writer", "escalate_human"
]:
    """Scope-aware routing from oscillation_check node. §12.5.

    Priority:
      oscillation_detected → escalate_human (any scope)
      SURGICAL + iteration <= 2 → span_editor
      all other cases (PARTIAL, or SURGICAL iter > 2) → writer
    """
    if state.get("oscillation_detected"):
        return "escalate_human"
    ro = state.get("reflector_output", {})
    scope = ro.get("dominant_scope", ro.get("scope", "PARTIAL"))
    iteration = state.get("current_iteration", 1)
    if scope == "SURGICAL" and iteration <= 2:
        return "span_editor"
    return "writer"
