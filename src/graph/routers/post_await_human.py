"""Post-await-human routing — decide where to resume after escalation.

Auto-resolve: route back to aggregator (with force_approve).
Interactive: route to END (graph pauses for external polling).
"""


def route_after_await_human(state: dict) -> str:
    """Route after human review gate.

    Returns:
        - ``aggregator`` if auto-resolved (force_approve set)
        - ``__end__`` if waiting for interactive human decision
    """
    if state.get("force_approve"):
        return "aggregator"
    return "__end__"
