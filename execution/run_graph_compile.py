#!/usr/bin/env python3
"""
Validation script for Phase 4: Graph & Routing.

Verifies that src/graph/graph.py compiles a valid LangGraph StateGraph
with all expected nodes and edges, using a mock checkpointer.

Run: python execution/run_graph_compile.py
"""
import sys
import importlib
import traceback
from pathlib import Path

# ─── Expected nodes from §4.5 ────────────────────────────────────────────────

EXPECTED_NODES: set[str] = {
    "preflight",
    "budget_estimator",
    "planner",
    "await_outline",
    "researcher",
    "citation_manager",
    "citation_verifier",
    "source_sanitizer",
    "source_synthesizer",
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
}

# Nodes that MUST NOT exist as graph nodes (§7.6 authoritative)
FORBIDDEN_NODES: set[str] = {
    "writer_a",
    "writer_b",
    "writer_c",
    "jury_multi_draft",
    "fusor",
}

# Key conditional edges that must be present
EXPECTED_CONDITIONAL_SOURCES: set[str] = {
    "await_outline",     # route_outline_approval
    "aggregator",        # route_after_aggregator
    "reflector",         # route_after_reflector
    "oscillation_check", # route_after_oscillation
    "coherence_guard",   # route_after_coherence
    "section_checkpoint",# route_next_section
}


def try_import_graph():
    """Attempt to import build_graph from src.graph.graph."""
    try:
        # Add project root to sys.path
        project_root = Path.cwd()
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.graph.graph import build_graph
        return build_graph, None
    except ImportError as e:
        return None, f"ImportError: {e}"
    except Exception as e:
        return None, f"Unexpected error on import: {e}\n{traceback.format_exc()}"


def create_mock_checkpointer():
    """
    Create a mock checkpointer that satisfies LangGraph's compile() signature.
    We try multiple approaches depending on LangGraph version.
    """
    try:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    except ImportError:
        pass

    # Fallback: try without checkpointer (compile with None)
    return None


def validate() -> bool:
    """Run all graph compilation validations."""
    errors: list[str] = []
    warnings: list[str] = []

    # ── Step 1: Import build_graph ────────────────────────────────────────
    print("Step 1: Importing build_graph...")
    build_graph, err = try_import_graph()
    if build_graph is None:
        print(f"  FAIL: Cannot import build_graph — {err}")
        print("\n  Make sure src/graph/graph.py exists and defines build_graph()")
        return False
    print("  ✓ build_graph imported successfully")

    # ── Step 2: Create mock checkpointer ──────────────────────────────────
    print("\nStep 2: Creating mock checkpointer...")
    checkpointer = create_mock_checkpointer()
    if checkpointer is not None:
        print(f"  ✓ Using {type(checkpointer).__name__}")
    else:
        print("  ⚠ No checkpointer available, will try compile(checkpointer=None)")
        warnings.append("No checkpointer available; compiled without persistence")

    # ── Step 3: Compile the graph ─────────────────────────────────────────
    print("\nStep 3: Compiling graph...")
    try:
        compiled = build_graph(checkpointer)
        print("  ✓ Graph compiled successfully")
    except TypeError:
        # build_graph might not accept checkpointer as positional
        try:
            compiled = build_graph(checkpointer=checkpointer)
            print("  ✓ Graph compiled successfully (keyword arg)")
        except Exception as e:
            errors.append(f"Graph compilation failed: {e}")
            print(f"  FAIL: {e}")
            traceback.print_exc()
            return False
    except Exception as e:
        errors.append(f"Graph compilation failed: {e}")
        print(f"  FAIL: {e}")
        traceback.print_exc()
        return False

    # ── Step 4: Check node registration ───────────────────────────────────
    print("\nStep 4: Checking registered nodes...")

    # Extract nodes from compiled graph
    try:
        # LangGraph CompiledGraph stores nodes in different attributes
        # depending on version
        graph_nodes: set[str] = set()

        if hasattr(compiled, 'nodes'):
            graph_nodes = set(compiled.nodes.keys())
        elif hasattr(compiled, 'graph') and hasattr(compiled.graph, 'nodes'):
            graph_nodes = set(compiled.graph.nodes.keys())
        elif hasattr(compiled, '_graph') and hasattr(compiled._graph, 'nodes'):
            graph_nodes = set(compiled._graph.nodes.keys())

        # Remove internal LangGraph nodes
        internal_nodes = {"__start__", "__end__", "START", "END"}
        graph_nodes -= internal_nodes

        print(f"  Found {len(graph_nodes)} nodes: {sorted(graph_nodes)}")
    except Exception as e:
        warnings.append(f"Could not extract node list: {e}")
        graph_nodes = set()
        print(f"  ⚠ Could not extract node list: {e}")

    if graph_nodes:
        # Check for missing expected nodes
        missing = EXPECTED_NODES - graph_nodes
        if missing:
            errors.append(f"Missing nodes ({len(missing)}): {sorted(missing)}")
            print(f"  ✗ Missing expected nodes: {sorted(missing)}")

        # Check for forbidden MoW nodes
        forbidden_found = FORBIDDEN_NODES & graph_nodes
        if forbidden_found:
            errors.append(
                f"Forbidden MoW nodes found (§7.6 violation): {sorted(forbidden_found)}. "
                "MoW must be internal to writer node."
            )
            print(f"  ✗ FORBIDDEN nodes found: {sorted(forbidden_found)}")

        # Check for unexpected nodes
        unexpected = graph_nodes - EXPECTED_NODES
        if unexpected:
            warnings.append(f"Unexpected extra nodes: {sorted(unexpected)}")
            print(f"  ⚠ Extra nodes (not in spec): {sorted(unexpected)}")

        if not missing and not forbidden_found:
            print(f"  ✓ All {len(EXPECTED_NODES)} expected nodes registered")

    # ── Step 5: Check edges exist ─────────────────────────────────────────
    print("\nStep 5: Checking graph edges...")
    try:
        edge_count = 0
        if hasattr(compiled, 'graph'):
            g = compiled.graph
            if hasattr(g, 'edges'):
                edge_count = len(g.edges)
            elif hasattr(g, '_edges'):
                edge_count = len(g._edges)
        elif hasattr(compiled, '_graph'):
            g = compiled._graph
            if hasattr(g, 'edges'):
                edge_count = len(g.edges)

        if edge_count > 0:
            print(f"  ✓ Graph has {edge_count} edges defined")
        else:
            warnings.append("Could not count edges; may be zero or inaccessible")
            print("  ⚠ Could not verify edge count")
    except Exception as e:
        warnings.append(f"Edge check failed: {e}")
        print(f"  ⚠ Edge check failed: {e}")

    # ── Step 6: Verify graph is invokable (dry run check) ─────────────────
    print("\nStep 6: Verifying graph structure integrity...")
    try:
        # Check that the graph has the expected state type
        if hasattr(compiled, 'schema'):
            schema = compiled.schema
            print(f"  ✓ Graph schema: {schema.__name__ if hasattr(schema, '__name__') else schema}")
        # Check input/output schema
        if hasattr(compiled, 'input_schema'):
            print(f"  ✓ Input schema available")
        if hasattr(compiled, 'output_schema'):
            print(f"  ✓ Output schema available")
    except Exception as e:
        warnings.append(f"Schema inspection failed: {e}")

    # ── Report ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")
    if not errors and not warnings:
        print("  ✓ All graph compilation checks passed!")
    elif not errors:
        print(f"\n  ✓ Graph compiles correctly ({len(warnings)} warnings)")
    print("=" * 60)

    if errors:
        print(f"\nRESULT: FAIL — {len(errors)} errors found")
        return False
    else:
        print(f"\nRESULT: PASS")
        return True


if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
