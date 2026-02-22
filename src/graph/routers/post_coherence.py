"""Route after coherence guard — §4.5."""
from __future__ import annotations
from typing import Literal


def route_after_coherence(state: dict) -> Literal[
    "no_conflict", "soft_conflict", "hard_conflict"
]:
    """Route based on coherence conflict severity. §4.5.

    no_conflict / soft_conflict → context_compressor
    hard_conflict → await_human
    """
    conflicts = state.get("coherence_conflicts", [])
    if not conflicts:
        return "no_conflict"
    # Check for HARD conflicts — field is "level" per §4.6, compat with "severity"
    if any(c.get("level", c.get("severity")) == "HARD" for c in conflicts):
        return "hard_conflict"
    return "soft_conflict"
