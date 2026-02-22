"""LangGraph graph definition — §4.5 canonical.

Defines build_graph() which registers all 31 nodes, all edges (fixed and
conditional), and compiles the graph with a checkpointer.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
from src.graph.state import DocumentState

# ── Routing functions ────────────────────────────────────────────────────────
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

# ── Node list — §4.5 ────────────────────────────────────────────────────────
# 31 nodes. MoW nodes (writer_a, writer_b, writer_c, jury_multi_draft, fusor)
# are NOT graph nodes — they are internal to the writer node (§7.6 authoritative).

NODES: list[str] = [
    "preflight",
    "budget_estimator",
    "planner",
    "await_outline",
    "researcher",
    "citation_manager",
    "citation_verifier",
    "source_sanitizer",
    "source_synthesizer",
    "writer",                   # MoW is internal (§7.6)
    "post_draft_analyzer",
    "researcher_targeted",
    "style_linter",
    "style_fixer",
    "metrics_collector",
    "jury",                     # runs jury_R, jury_F, jury_S in gather
    "aggregator",
    "reflector",
    "span_editor",
    "diff_merger",
    "oscillation_check",
    "panel_discussion",
    "coherence_guard",
    "context_compressor",       # no-op on idx==0 (§5.16)
    "section_checkpoint",
    "await_human",
    "budget_controller",
    "post_qa",
    "length_adjuster",
    "publisher",
    "feedback_collector",
]


# ── Stub node factory ────────────────────────────────────────────────────────

def _make_stub(name: str):
    """Create a stub node function that returns empty dict (pass-through).

    Stubs will be replaced by real implementations in later phases.
    """
    def _stub(state: dict) -> dict:
        return {}
    _stub.__name__ = name
    _stub.__qualname__ = name
    return _stub


# ── Build graph — §4.5 ──────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    """Build and compile the DRS LangGraph StateGraph. §4.5.

    Args:
        checkpointer: LangGraph checkpointer (AsyncPostgresSaver or MemorySaver).
                      Pass None for compilation without persistence.

    Returns:
        Compiled StateGraph ready for .ainvoke() / .invoke().
    """
    g = StateGraph(DocumentState)

    # ── Register all nodes with stubs ────────────────────────────────────
    for node_name in NODES:
        g.add_node(node_name, _make_stub(node_name))

    # ── Entry point ──────────────────────────────────────────────────────
    g.set_entry_point("preflight")

    # ══════════════════════════════════════════════════════════════════════
    # Phase A: Pre-Flight & Setup
    # ══════════════════════════════════════════════════════════════════════

    g.add_edge("preflight", "budget_estimator")
    g.add_edge("budget_estimator", "planner")
    g.add_edge("planner", "await_outline")
    g.add_conditional_edges("await_outline", route_outline_approval, {
        "approved": "researcher",
        "rejected": "planner",
    })

    # ══════════════════════════════════════════════════════════════════════
    # Phase B: Section Loop — Research Pipeline
    # ══════════════════════════════════════════════════════════════════════

    g.add_edge("researcher", "citation_manager")
    g.add_edge("citation_manager", "citation_verifier")
    g.add_edge("citation_verifier", "source_sanitizer")
    g.add_edge("source_sanitizer", "source_synthesizer")
    g.add_edge("source_synthesizer", "writer")

    # Writer → post_draft_analyzer (always; MoW is internal to writer §7.6)
    g.add_edge("writer", "post_draft_analyzer")

    # Post-draft gap analysis — iteration==1 guard enforced at graph level
    g.add_conditional_edges("post_draft_analyzer", route_post_draft_gap, {
        "gap": "researcher_targeted",
        "no_gap": "style_linter",
    })

    # Targeted re-research shares the citation/sanitize/synth pipeline
    g.add_edge("researcher_targeted", "citation_manager")
    # citation_manager → citation_verifier → ... → writer already defined

    # ── Style gate ───────────────────────────────────────────────────────
    g.add_conditional_edges("style_linter", route_style_lint, {
        "violation": "style_fixer",
        "clean": "metrics_collector",
    })
    g.add_edge("style_fixer", "style_linter")  # re-lint after fix

    # ── Budget controller pass-through before jury ───────────────────────
    g.add_edge("metrics_collector", "budget_controller")
    g.add_conditional_edges("budget_controller", route_budget, {
        "continue": "jury",
        "hard_stop": "publisher",
    })

    # ── Jury & Aggregator ────────────────────────────────────────────────
    g.add_edge("jury", "aggregator")

    # Canonical routing from §9.4 — force_approve checked FIRST
    g.add_conditional_edges("aggregator", route_after_aggregator, {
        "approved": "coherence_guard",
        "force_approve": "coherence_guard",
        "fail_reflector": "reflector",
        "fail_style": "style_fixer",
        "panel": "panel_discussion",
        "veto": "reflector",
        "fail_missing_ev": "researcher_targeted",
        "budget_hard_stop": "publisher",
    })

    # ── Span editor pipeline (SURGICAL scope) ────────────────────────────
    g.add_edge("span_editor", "diff_merger")
    g.add_edge("diff_merger", "style_linter")  # re-lint after surgical edits

    # ── Reflector routing — §12.5 ────────────────────────────────────────
    g.add_conditional_edges("reflector", route_after_reflector, {
        "oscillation_check": "oscillation_check",
        "await_human": "await_human",
    })

    # ── Oscillation check routing — §12.5 ────────────────────────────────
    g.add_conditional_edges("oscillation_check", route_after_oscillation, {
        "span_editor": "span_editor",
        "writer": "writer",
        "escalate_human": "await_human",
    })

    # ── Panel discussion self-loop — §9.5 ────────────────────────────────
    g.add_conditional_edges("panel_discussion", route_after_panel_internal, {
        "panel_discussion": "panel_discussion",
        "aggregator": "aggregator",
    })

    # ── Section approval pipeline ────────────────────────────────────────
    # coherence_guard → context_compressor → section_checkpoint
    g.add_conditional_edges("coherence_guard", route_after_coherence, {
        "no_conflict": "context_compressor",
        "soft_conflict": "context_compressor",
        "hard_conflict": "await_human",
    })
    g.add_edge("context_compressor", "section_checkpoint")
    g.add_conditional_edges("section_checkpoint", route_next_section, {
        "next_section": "researcher",
        "all_done": "post_qa",
    })

    # ══════════════════════════════════════════════════════════════════════
    # Phase C: Post-Flight QA
    # ══════════════════════════════════════════════════════════════════════

    g.add_conditional_edges("post_qa", route_post_qa, {
        "length_out_of_range": "length_adjuster",
        "conflicts": "await_human",
        "ok": "publisher",
    })
    g.add_edge("length_adjuster", "publisher")

    # ══════════════════════════════════════════════════════════════════════
    # Phase D: Publisher & Output
    # ══════════════════════════════════════════════════════════════════════

    g.add_edge("publisher", "feedback_collector")
    g.add_edge("feedback_collector", END)

    # ── Compile ──────────────────────────────────────────────────────────
    return g.compile(checkpointer=checkpointer)
