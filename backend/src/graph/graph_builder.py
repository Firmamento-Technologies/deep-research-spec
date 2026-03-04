"""LangGraph StateGraph builder for the Deep Research System.

This module assembles the DRS pipeline as a LangGraph StateGraph with:
- 5 nodes: planner, researcher, writer, critic, finalizer
- Conditional routing for critic → approve/rewrite
- Section loop for processing multiple sections sequentially
- PostgreSQL checkpointer for HITL interrupts
- State reducer for merging partial node updates

Graph structure:

    START
      ↓
    planner (generates outline + HITL approval)
      ↓
    ┌─ section_loop ────────────────┐
    │                               │
    │  researcher (gather sources)  │
    │       ↓                       │
    │  writer (generate content)    │
    │       ↓                       │
    │  critic (evaluate quality)    │
    │       ↓                       │
    │  critic_router                │
    │    ├─ APPROVE → next section  │
    │    └─ REWRITE → back to writer│
    │                               │
    └───────────────────────────────┘
      ↓
    finalizer (merge all sections)
      ↓
    END

Usage:
    from src.graph.graph_builder import build_graph
    
    graph = build_graph()
    
    initial_state = build_initial_state(
        doc_id="doc-123",
        topic="Quantum Computing",
        target_words=5000,
        quality_preset="Balanced",
    )
    
    # Run the graph
    result = await graph.ainvoke(initial_state)
    
    # Or with streaming events
    async for event in graph.astream_events(initial_state):
        print(event)

Spec: §10 Graph orchestration, §20 HITL, §21 Quality presets
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

from src.models.state import ResearchState, Section
from src.graph.nodes import (
    planner_node,
    researcher_node,
    writer_node,
    critic_node,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State Reducer
# ---------------------------------------------------------------------------

def merge_state(existing: ResearchState, updates: dict) -> ResearchState:
    """Merge partial state updates from nodes into existing state.
    
    LangGraph calls this reducer to combine node outputs with current state.
    
    Args:
        existing: Current state dict
        updates:  Partial updates from a node
    
    Returns:
        Merged state dict
    """
    # Simple shallow merge for most keys
    merged = {**existing, **updates}
    
    # Special handling for budget tracking
    if "budget_spent" in updates:
        merged["budget_spent"] = existing.get("budget_spent", 0.0) + updates["budget_spent"]
    
    if "budget_remaining_pct" in updates:
        max_budget = existing.get("max_budget", 100.0)
        merged["budget_remaining_pct"] = (
            (max_budget - merged["budget_spent"]) / max_budget * 100
        )
    
    return merged


# ---------------------------------------------------------------------------
# Additional Nodes
# ---------------------------------------------------------------------------

async def finalizer_node(state: ResearchState) -> dict:
    """Final node: merge all sections into complete document.
    
    Args:
        state: ResearchState with all sections complete.
    
    Returns:
        State update with final_document and status='completed'.
    """
    doc_id = state["doc_id"]
    sections = state.get("sections", [])
    
    logger.info("[%s] Finalizer: merging %d sections", doc_id, len(sections))
    
    # Build final Markdown document
    parts = []
    
    # Add title
    topic = state.get("topic", "Research Document")
    parts.append(f"# {topic}\n")
    
    # Add each section
    for i, section in enumerate(sections, start=1):
        parts.append(f"\n## {i}. {section.title}\n")
        parts.append(section.content or "(No content)")
        parts.append("\n")
    
    final_document = "\n".join(parts)
    
    # Calculate totals
    total_words = sum(s.word_count or 0 for s in sections)
    total_cost = sum(s.cost_usd or 0.0 for s in sections)
    
    logger.info(
        "[%s] Finalizer: document complete (%d words, $%.4f)",
        doc_id, total_words, total_cost,
    )
    
    # Emit final event
    broker = state.get("broker")
    if broker:
        await broker.emit(doc_id, "DOCUMENT_COMPLETED", {
            "total_words": total_words,
            "total_cost": total_cost,
            "sections_count": len(sections),
        })
    
    return {
        "final_document": final_document,
        "status": "completed",
    }


# ---------------------------------------------------------------------------
# Routing Functions
# ---------------------------------------------------------------------------

def critic_router(state: ResearchState) -> Literal["writer", "next_section"]:
    """Route after critic evaluation.
    
    If rewrite required: go back to writer.
    If approved: move to next section (or finalizer if last section).
    
    Args:
        state: ResearchState after critic node.
    
    Returns:
        "writer" if rewrite needed, "next_section" otherwise.
    """
    rewrite_required = state.get("rewrite_required", False)
    
    if rewrite_required:
        logger.info(
            "[%s] Critic router: REWRITE (section %d)",
            state["doc_id"], state.get("current_section", 0),
        )
        # Clear the flag for next iteration
        state["rewrite_required"] = False
        return "writer"
    
    else:
        logger.info(
            "[%s] Critic router: APPROVE (section %d)",
            state["doc_id"], state.get("current_section", 0),
        )
        return "next_section"


def section_loop_router(state: ResearchState) -> Literal["researcher", "finalizer"]:
    """Route to next section or finalize.
    
    Increments current_section and checks if more sections remain.
    
    Args:
        state: ResearchState after a section is complete.
    
    Returns:
        "researcher" to process next section, "finalizer" if all done.
    """
    current = state.get("current_section", 0)
    total = state.get("total_sections", 0)
    
    # Move to next section
    state["current_section"] = current + 1
    
    if state["current_section"] < total:
        logger.info(
            "[%s] Section loop: continuing to section %d/%d",
            state["doc_id"], state["current_section"] + 1, total,
        )
        return "researcher"
    else:
        logger.info(
            "[%s] Section loop: all sections complete, finalizing",
            state["doc_id"],
        )
        return "finalizer"


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_graph(
    checkpointer_dsn: str | None = None,
) -> StateGraph:
    """Build the DRS research pipeline as a LangGraph StateGraph.
    
    Args:
        checkpointer_dsn: PostgreSQL DSN for checkpointing (optional).
                         Format: "postgresql://user:pass@host/db"
                         If None, no checkpointing (no HITL support).
    
    Returns:
        Compiled StateGraph ready for execution.
    """
    # Create graph with state schema
    graph = StateGraph(
        state_schema=ResearchState,
        # state_reducer=merge_state,  # LangGraph will auto-merge dicts
    )
    
    # --- Add nodes ---
    
    # 1. Planner: generates outline
    graph.add_node("planner", planner_node)
    
    # 2. Researcher: gathers sources for current section
    graph.add_node("researcher", researcher_node)
    
    # 3. Writer: generates section content
    graph.add_node("writer", writer_node)
    
    # 4. Critic: evaluates section quality
    graph.add_node("critic", critic_node)
    
    # 5. Finalizer: merges all sections into final document
    graph.add_node("finalizer", finalizer_node)
    
    # --- Add edges ---
    
    # START → planner
    graph.set_entry_point("planner")
    
    # planner → researcher (start first section)
    graph.add_edge("planner", "researcher")
    
    # researcher → writer
    graph.add_edge("researcher", "writer")
    
    # writer → critic
    graph.add_edge("writer", "critic")
    
    # critic → conditional routing
    graph.add_conditional_edges(
        "critic",
        critic_router,
        {
            "writer": "writer",        # Rewrite: loop back
            "next_section": "section_loop_check",  # Approve: continue
        },
    )
    
    # Section loop check: next section or finalize?
    graph.add_node("section_loop_check", lambda state: state)  # No-op node
    graph.add_conditional_edges(
        "section_loop_check",
        section_loop_router,
        {
            "researcher": "researcher",  # More sections
            "finalizer": "finalizer",     # All done
        },
    )
    
    # finalizer → END
    graph.add_edge("finalizer", END)
    
    # --- Compile with checkpointer ---
    
    checkpointer = None
    if checkpointer_dsn:
        try:
            checkpointer = PostgresSaver.from_conn_string(checkpointer_dsn)
            logger.info("Graph checkpointer enabled: PostgreSQL")
        except Exception as exc:
            logger.error("Failed to create checkpointer: %s", exc)
    
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=[],  # No pre-interrupts (use manual interrupts in nodes)
        interrupt_after=[],   # No post-interrupts
    )
    
    logger.info("Graph compiled with %d nodes", len(graph.nodes))
    
    return compiled


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

async def run_graph(
    graph: StateGraph,
    initial_state: ResearchState,
    thread_id: str | None = None,
) -> ResearchState:
    """Execute the graph and return final state.
    
    Args:
        graph:         Compiled StateGraph.
        initial_state: Starting state.
        thread_id:     Thread ID for checkpointing (required if checkpointer enabled).
    
    Returns:
        Final state after execution.
    """
    config = {}
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}
    
    result = await graph.ainvoke(initial_state, config=config)
    return result


async def stream_graph_events(
    graph: StateGraph,
    initial_state: ResearchState,
    thread_id: str | None = None,
):
    """Stream graph execution events.
    
    Args:
        graph:         Compiled StateGraph.
        initial_state: Starting state.
        thread_id:     Thread ID for checkpointing.
    
    Yields:
        Event dicts with keys: event, data, metadata.
    """
    config = {}
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}
    
    async for event in graph.astream_events(initial_state, config=config, version="v1"):
        yield event
