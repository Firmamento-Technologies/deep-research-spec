"""Route after style linter — §4.5."""
from __future__ import annotations
from typing import Literal


def route_style_lint(state: dict) -> Literal["violation", "clean"]:
    """Route based on whether style violations were found."""
    return "violation" if state.get("style_lint_violations") else "clean"
