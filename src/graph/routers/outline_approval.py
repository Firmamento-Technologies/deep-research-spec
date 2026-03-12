"""Route after outline approval — §4.5."""
from __future__ import annotations
from typing import Literal


def route_outline_approval(state: dict) -> Literal["approved", "rejected"]:
    """Route based on whether the human approved the outline."""
    return "approved" if state.get("outline_approved") else "rejected"
