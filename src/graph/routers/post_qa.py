"""Route after post-QA — §4.5."""
from __future__ import annotations
from typing import Literal


def route_post_qa(state: dict) -> Literal[
    "length_out_of_range", "conflicts", "ok"
]:
    """Route based on post-QA results. §4.5.

    length_out_of_range → length_adjuster (§5.22), NOT reflector.
    conflicts → await_human (optional).
    ok → publisher.
    """
    if not state.get("format_validated", True):
        return "length_out_of_range"
    if state.get("coherence_conflicts"):
        return "conflicts"
    return "ok"
