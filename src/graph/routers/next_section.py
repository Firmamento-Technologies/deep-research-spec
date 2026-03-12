"""Route after section checkpoint — §4.5."""
from __future__ import annotations
from typing import Literal


def route_next_section(state: dict) -> Literal["next_section", "all_done"]:
    """Route to next section or Phase C when all sections are approved."""
    next_idx = state["current_section_idx"] + 1
    return "all_done" if next_idx >= state["total_sections"] else "next_section"
