"""Route after post-draft analyzer — §4.5."""
from __future__ import annotations
from typing import Literal


def route_post_draft_gap(state: dict) -> Literal["gap", "no_gap"]:
    """Route to targeted research when gap found on iteration 1 only. §4.5.

    The iteration guard is enforced here at the graph level to provide a
    structural guarantee against infinite loops on iter >= 2.
    INVARIANT: targeted re-research is only triggered on the first draft.
    """
    if state.get("post_draft_gaps") and state.get("current_iteration", 1) == 1:
        return "gap"
    return "no_gap"
