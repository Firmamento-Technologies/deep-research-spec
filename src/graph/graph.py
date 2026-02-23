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
from src.graph.routers.post_await_human import route_after_await_human

# ── Real node implementations (all phases — 32/32) ───────────────────────────
# Phase 0-1
from src.graph.nodes.shine_adapter import shine_adapter_node
from src.graph.nodes.planner import planner_node
from src.graph.nodes.writer import writer_node
# Phase 2
from src.graph.nodes.jury import jury_node
from src.graph.nodes.aggregator import aggregator_node
# Phase 3
from src.graph.nodes.reflector import reflector_node
from src.graph.nodes.style_linter import style_linter_node
from src.graph.nodes.style_fixer import style_fixer_node
from src.graph.nodes.oscillation_check import oscillation_check_node
# Phase 4
from src.graph.nodes.panel_discussion import panel_discussion_node
from src.graph.nodes.coherence_guard import coherence_guard_node
# Pre-existing implementations
from src.graph.nodes.citation_manager import citation_manager_node
from src.graph.nodes.citation_verifier import citation_verifier_node
from src.graph.nodes.source_sanitizer import source_sanitizer_node
from src.graph.nodes.source_synthesizer import source_synthesizer_node
from src.graph.nodes.researcher_targeted import researcher_targeted_node
from src.graph.nodes.budget_controller import budget_controller_node
from src.graph.nodes.context_compressor import run as context_compressor_node
from src.graph.nodes.section_checkpoint import run as section_checkpoint_node
# Remaining stubs (now real)
from src.graph.nodes.preflight import preflight_node
from src.graph.nodes.budget_estimator import budget_estimator_node
from src.graph.nodes.await_outline import await_outline_node
from src.graph.nodes.researcher import researcher_node
from src.graph.nodes.post_draft_analyzer import post_draft_analyzer_node
from src.graph.nodes.metrics_collector import metrics_collector_node
from src.graph.nodes.span_editor import span_editor_node
from src.graph.nodes.diff_merger import diff_merger_node
from src.graph.nodes.await_human import await_human_node
from src.graph.nodes.post_qa import post_qa_node
from src.graph.nodes.length_adjuster import length_adjuster_node
from src.graph.nodes.publisher import publisher_node
from src.graph.nodes.feedback_collector import feedback_collector_node

# ── Node list — §4.5 ────────────────────────────────────────────────────────
# 32 nodes. MoW nodes (writer_a, writer_b, writer_c, jury_multi_draft, fusor)
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
    "shine_adapter",
    "writer",
    "post_draft_analyzer",
    "researcher_targeted",
    "style_linter",
    "style_fixer",
    "metrics_collector",
    "jury",
    "aggregator",
    "reflector",
    "span_editor",
    "diff_merger",
    "oscillation_check",
    "panel_discussion",
    "coherence_guard",
    "context_compressor",
    "section_checkpoint",
    "await_human",
    "budget_controller",
    "post_qa",
    "length_adjuster",
    "publisher",
    "feedback_collector",
]

# ── All 32 nodes have real implementations — zero stubs ──────────────────────
_REAL_NODES: dict[str, callable] = {
    "preflight": preflight_node,
    "budget_estimator": budget_estimator_node,
    "planner": planner_node,
    "await_outline": await_outline_node,
    "researcher": researcher_node,
    "citation_manager": citation_manager_node,
    "citation_verifier": citation_verifier_node,
    "source_sanitizer": source_sanitizer_node,
    "source_synthesizer": source_synthesizer_node,
    "shine_adapter": shine_adapter_node,
    "writer": writer_node,
    "post_draft_analyzer": post_draft_analyzer_node,
    "researcher_targeted": researcher_targeted_node,
    "style_linter": style_linter_node,
    "style_fixer": style_fixer_node,
    "metrics_collector": metrics_collector_node,
    "jury": jury_node,
    "aggregator": aggregator_node,
    "reflector": reflector_node,
    "span_editor": span_editor_node,
    "diff_merger": diff_merger_node,
    "oscillation_check": oscillation_check_node,
    "panel_discussion": panel_discussion_node,
    "coherence_guard": coherence_guard_node,
    "context_compressor": context_compressor_node,
    "section_checkpoint": section_checkpoint_node,
    "await_human": await_human_node,
    "budget_controller": budget_controller_node,
    "post_qa": post_qa_node,
    "length_adjuster": length_adjuster_node,
    "publisher": publisher_node,
    "feedback_collector": feedback_collector_node,
}


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

    # ── Register nodes: real implementations override stubs ──────────────
    for node_name in NODES:
        fn = _REAL_NODES.get(node_name, _make_stub(node_name))
        g.add_node(node_name, fn)

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
    g.add_edge("source_synthesizer", "shine_adapter")   # → SHINE LoRA generation
    g.add_edge("shine_adapter", "writer")               # → Writer (with or without LoRA)

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

    # ── Await human routing — resume after escalation ─────────────────
    g.add_conditional_edges("await_human", route_after_await_human, {
        "aggregator": "aggregator",   # auto-resolved → force_approve
        "__end__": END,               # interactive → pause graph
    })

    g.add_edge("publisher", "feedback_collector")
    g.add_edge("feedback_collector", END)

    # ── Compile ──────────────────────────────────────────────────────────
    return g.compile(checkpointer=checkpointer)
