"""Graph routing functions — all routers re-exported."""
from src.graph.routers.outline_approval import route_outline_approval
from src.graph.routers.post_aggregator import route_after_aggregator
from src.graph.routers.post_reflector import route_after_reflector
from src.graph.routers.post_oscillation import route_after_oscillation
from src.graph.routers.post_coherence import route_after_coherence
from src.graph.routers.next_section import route_next_section
from src.graph.routers.budget_route import route_budget
from src.graph.routers.style_lint import route_style_lint
from src.graph.routers.post_draft_gap import route_post_draft_gap
from src.graph.routers.post_qa import route_post_qa
from src.graph.routers.panel_loop import route_after_panel_internal

__all__ = [
    "route_outline_approval",
    "route_after_aggregator",
    "route_after_reflector",
    "route_after_oscillation",
    "route_after_coherence",
    "route_next_section",
    "route_budget",
    "route_style_lint",
    "route_post_draft_gap",
    "route_post_qa",
    "route_after_panel_internal",
]
