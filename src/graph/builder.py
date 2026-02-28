"""LangGraph graph builder with inline RLM feature flags.

Replaces the standard node registrations with RLM adapter nodes when the
corresponding feature flags are enabled in config. The graph is compiled
statically — feature flags are resolved at build time, not at node-call time.

Usage:
    from src.graph.builder import build_graph
    graph = build_graph(settings, checkpointer)

See §4.5 for the full LangGraph topology. This module only covers the
RLM-affected nodes; all other nodes are registered by the original builder.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_graph(settings: Any, checkpointer: Any) -> Any:
    """Build and compile the DRS LangGraph with optional RLM adapters.

    Args:
        settings:     Application settings object with .features dict.
        checkpointer: LangGraph checkpointer (e.g. SqliteSaver).

    Returns:
        Compiled LangGraph graph.
    """
    from langgraph.graph import END, StateGraph

    # DocumentState is defined in §4.6; import from the canonical location
    try:
        from src.state import DocumentState
    except ImportError:
        logger.warning(
            "src.state.DocumentState not found — using dict as state type."
        )
        DocumentState = dict  # type: ignore[assignment, misc]

    g = StateGraph(DocumentState)

    features = getattr(settings, "features", {}) or {}
    rlm_enabled = features.get("rlm_enabled", False)
    rlm_agents = set(features.get("rlm_agents", []))

    # ------------------------------------------------------------------
    # BudgetEstimator — patched to include RLM overhead before 80% cap
    # ------------------------------------------------------------------
    if rlm_enabled:
        from src.rlm.budget_bridge import patched_budget_estimator_node
        g.add_node("budget_estimator", patched_budget_estimator_node)
        logger.info("RLM: patched BudgetEstimator node registered.")
    else:
        _register_standard(g, "budget_estimator", "src.nodes.budget_estimator")

    # ------------------------------------------------------------------
    # SourceSynthesizer
    # ------------------------------------------------------------------
    if rlm_enabled and "source_synthesizer_rlm" in rlm_agents:
        from src.rlm.adapters.source_synthesizer_rlm import source_synthesizer_rlm_node
        g.add_node("source_synthesizer", source_synthesizer_rlm_node)
        logger.info("RLM: source_synthesizer_rlm node registered.")
    else:
        _register_standard(g, "source_synthesizer", "src.nodes.source_synthesizer")

    # ------------------------------------------------------------------
    # CoherenceGuard
    # ------------------------------------------------------------------
    if rlm_enabled and "coherence_guard_rlm" in rlm_agents:
        from src.rlm.adapters.coherence_guard_rlm import coherence_guard_rlm_node
        g.add_node("coherence_guard", coherence_guard_rlm_node)
        logger.info("RLM: coherence_guard_rlm node registered.")
    else:
        _register_standard(g, "coherence_guard", "src.nodes.coherence_guard")

    # ------------------------------------------------------------------
    # PostDraftAnalyzer
    # ------------------------------------------------------------------
    if rlm_enabled and "post_draft_analyzer_rlm" in rlm_agents:
        from src.rlm.adapters.post_draft_analyzer_rlm import post_draft_analyzer_rlm_node
        g.add_node("post_draft_analyzer", post_draft_analyzer_rlm_node)
        logger.info("RLM: post_draft_analyzer_rlm node registered.")
    else:
        _register_standard(g, "post_draft_analyzer", "src.nodes.post_draft_analyzer")

    # ------------------------------------------------------------------
    # NOTE: All other DRS nodes (researcher, writer, jury, reflector, …)
    # are registered by the original builder. Import and call it here:
    # ------------------------------------------------------------------
    try:
        from src.graph.base_builder import register_remaining_nodes, add_all_edges
        register_remaining_nodes(g)
        add_all_edges(g)
    except ImportError:
        logger.warning(
            "src.graph.base_builder not found — only RLM nodes are registered. "
            "Integrate with the existing graph builder to get a complete graph."
        )

    return g.compile(checkpointer=checkpointer)


def _register_standard(g: Any, node_name: str, module_path: str) -> None:
    """Register a standard (non-RLM) node, with graceful import error handling."""
    try:
        module = __import__(module_path, fromlist=[f"{node_name}_node"])
        fn = getattr(module, f"{node_name}_node")
        g.add_node(node_name, fn)
    except (ImportError, AttributeError) as exc:
        logger.warning(
            "Could not register standard node '%s' from '%s': %s. "
            "Skipping — ensure the node module exists.",
            node_name, module_path, exc,
        )
