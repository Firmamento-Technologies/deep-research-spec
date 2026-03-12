"""Route after section checkpoint — §4.5."""
from __future__ import annotations
from typing import Literal


def route_next_section(state: dict) -> Literal["next_section", "all_done"]:
    """Route to next section or Phase C when all sections are approved.

    Note: section_checkpoint already increments current_section_idx before
    this router runs, so we compare directly (no +1 needed).
    """
    current_idx = state["current_section_idx"]
    return "all_done" if current_idx >= state["total_sections"] else "next_section"
