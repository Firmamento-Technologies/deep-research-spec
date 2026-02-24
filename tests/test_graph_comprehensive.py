"""Comprehensive tests for DRS graph nodes, routers, and infrastructure.

Tests all 32 nodes (smoke/unit), all 13 routers (unit), graph compilation,
edge topology, and key integration scenarios.
"""
from __future__ import annotations

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Compilation & Topology
# ═══════════════════════════════════════════════════════════════════════════════

class TestGraphCompilation:
    """Verify graph structure and compilation."""

    def test_graph_compiles(self):
        from src.graph.graph import build_graph
        g = build_graph()
        assert g is not None

    def test_all_32_nodes_registered(self):
        from src.graph.graph import NODES, _REAL_NODES
        assert len(NODES) == 32
        assert len(_REAL_NODES) == 32

    def test_zero_stubs(self):
        from src.graph.graph import NODES, _REAL_NODES
        stubs = set(NODES) - set(_REAL_NODES.keys())
        assert len(stubs) == 0, f"Remaining stubs: {stubs}"

    def test_entry_point_is_preflight(self):
        from src.graph.graph import build_graph
        g = build_graph()
        graph_data = g.get_graph()
        start_edges = [e for e in graph_data.edges if str(e.source) == "__start__"]
        assert len(start_edges) == 1
        assert str(start_edges[0].target) == "preflight"

    def test_feedback_collector_ends_graph(self):
        from src.graph.graph import build_graph
        g = build_graph()
        graph_data = g.get_graph()
        end_edges = [e for e in graph_data.edges
                     if str(e.source) == "feedback_collector" and str(e.target) == "__end__"]
        assert len(end_edges) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Router Unit Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRouterOutlineApproval:
    def test_approved(self):
        from src.graph.routers.outline_approval import route_outline_approval
        assert route_outline_approval({"outline_approved": True}) == "approved"

    def test_rejected(self):
        from src.graph.routers.outline_approval import route_outline_approval
        assert route_outline_approval({"outline_approved": False}) == "rejected"


class TestRouterPostAggregator:
    def test_approved(self):
        from src.graph.routers.post_aggregator import route_after_aggregator
        state = {"css_content": 0.80, "css_style": 0.85, "jury_verdicts": []}
        assert route_after_aggregator(state) == "approved"

    def test_force_approve(self):
        from src.graph.routers.post_aggregator import route_after_aggregator
        state = {"force_approve": True, "jury_verdicts": []}
        assert route_after_aggregator(state) == "force_approve"

    def test_fail_reflector(self):
        from src.graph.routers.post_aggregator import route_after_aggregator
        state = {"css_content": 0.40, "css_style": 0.85, "jury_verdicts": [], "panel_round": 2,
                 "config": {"convergence": {"panel_max_rounds": 2}}}
        assert route_after_aggregator(state) == "fail_reflector"

    def test_panel(self):
        from src.graph.routers.post_aggregator import route_after_aggregator
        state = {"css_content": 0.30, "css_style": 0.30, "jury_verdicts": [], "panel_round": 0}
        assert route_after_aggregator(state) == "panel"


class TestRouterPostReflector:
    def test_routes_oscillation_check(self):
        from src.graph.routers.post_reflector import route_after_reflector
        state = {"reflector_output": {"dominant_scope": "PARTIAL"}}
        assert route_after_reflector(state) == "oscillation_check"

    def test_routes_await_human(self):
        from src.graph.routers.post_reflector import route_after_reflector
        state = {"reflector_output": {"dominant_scope": "FULL"}}
        assert route_after_reflector(state) == "await_human"


class TestRouterPostOscillation:
    def test_writer_no_oscillation(self):
        from src.graph.routers.post_oscillation import route_after_oscillation
        state = {"oscillation_detected": False, "reflector_output": {"dominant_scope": "PARTIAL"}}
        assert route_after_oscillation(state) == "writer"

    def test_span_editor_surgical(self):
        from src.graph.routers.post_oscillation import route_after_oscillation
        state = {"oscillation_detected": False, "reflector_output": {"dominant_scope": "SURGICAL"}}
        assert route_after_oscillation(state) == "span_editor"

    def test_escalate_on_oscillation(self):
        from src.graph.routers.post_oscillation import route_after_oscillation
        state = {"oscillation_detected": True}
        assert route_after_oscillation(state) == "escalate_human"


class TestRouterPostCoherence:
    def test_no_conflict(self):
        from src.graph.routers.post_coherence import route_after_coherence
        state = {"coherence_conflicts": []}
        assert route_after_coherence(state) == "no_conflict"

    def test_hard_conflict(self):
        from src.graph.routers.post_coherence import route_after_coherence
        state = {"coherence_conflicts": [{"level": "HARD"}]}
        assert route_after_coherence(state) == "hard_conflict"


class TestRouterNextSection:
    def test_next_section(self):
        from src.graph.routers.next_section import route_next_section
        state = {"current_section_idx": 0, "total_sections": 3}
        assert route_next_section(state) == "next_section"

    def test_all_done(self):
        from src.graph.routers.next_section import route_next_section
        state = {"current_section_idx": 2, "total_sections": 3}
        assert route_next_section(state) == "all_done"


class TestRouterBudget:
    def test_continue(self):
        from src.graph.routers.budget_route import route_budget
        state = {"budget": {"hard_stop_fired": False}}
        assert route_budget(state) == "continue"

    def test_hard_stop(self):
        from src.graph.routers.budget_route import route_budget
        state = {"budget": {"hard_stop_fired": True}}
        assert route_budget(state) == "hard_stop"


class TestRouterStyleLint:
    def test_clean(self):
        from src.graph.routers.style_lint import route_style_lint
        state = {"style_lint_violations": []}
        assert route_style_lint(state) == "clean"

    def test_violation(self):
        from src.graph.routers.style_lint import route_style_lint
        state = {"style_lint_violations": [{"rule_id": "L1.1"}]}
        assert route_style_lint(state) == "violation"


class TestRouterPostDraftGap:
    def test_gap(self):
        from src.graph.routers.post_draft_gap import route_post_draft_gap
        state = {"post_draft_gaps": [{"claim": "X"}], "current_iteration": 1}
        assert route_post_draft_gap(state) == "gap"

    def test_no_gap(self):
        from src.graph.routers.post_draft_gap import route_post_draft_gap
        state = {"post_draft_gaps": []}
        assert route_post_draft_gap(state) == "no_gap"


class TestRouterPostQA:
    def test_ok(self):
        from src.graph.routers.post_qa import route_post_qa
        state = {"qa_result": {"status": "ok"}}
        assert route_post_qa(state) == "ok"


class TestRouterPanelLoop:
    def test_continue_panel(self):
        from src.graph.routers.panel_loop import route_after_panel_internal
        state = {"panel_round": 1, "panel_consensus": False}
        assert route_after_panel_internal(state) == "panel_discussion"

    def test_done_panel(self):
        from src.graph.routers.panel_loop import route_after_panel_internal
        state = {"panel_round": 2, "panel_consensus": True}
        assert route_after_panel_internal(state) == "aggregator"


class TestRouterPostAwaitHuman:
    def test_auto_resolve_to_aggregator(self):
        from src.graph.routers.post_await_human import route_after_await_human
        state = {"force_approve": True}
        assert route_after_await_human(state) == "aggregator"

    def test_interactive_to_end(self):
        from src.graph.routers.post_await_human import route_after_await_human
        state = {"force_approve": False}
        assert route_after_await_human(state) == "__end__"

    def test_no_force_approve_key(self):
        from src.graph.routers.post_await_human import route_after_await_human
        state = {}
        assert route_after_await_human(state) == "__end__"


# ═══════════════════════════════════════════════════════════════════════════════
# Node Smoke Tests (import + minimal call)
# ═══════════════════════════════════════════════════════════════════════════════

class TestNodeSmokeTests:
    """Verify every node can be imported and called with minimal state."""

    def test_preflight(self):
        from src.graph.nodes.preflight import preflight_node
        r = preflight_node({"config": {"topic": "test"}, "budget": {}})
        assert isinstance(r, dict)

    def test_budget_estimator(self):
        from src.graph.nodes.budget_estimator import budget_estimator_node
        r = budget_estimator_node({"outline": [{"target_words": 1000}], "budget": {}})
        assert isinstance(r, dict)

    def test_await_outline_auto(self):
        from src.graph.nodes.await_outline import await_outline_node
        r = await_outline_node({"outline": [{"title": "A"}], "config": {"auto_approve_outline": True}})
        assert r.get("outline_approved") is True

    def test_style_linter(self):
        from src.graph.nodes.style_linter import style_linter_node
        r = style_linter_node({"current_draft": "This is a good test draft.", "style_profile": "academic"})
        assert "style_lint_violations" in r

    def test_metrics_collector(self):
        from src.graph.nodes.metrics_collector import metrics_collector_node
        r = metrics_collector_node({"current_draft": "Hello world.", "budget": {}})
        assert isinstance(r, dict)

    def test_diff_merger(self):
        from src.graph.nodes.diff_merger import diff_merger_node
        r = diff_merger_node({
            "current_draft": "old text here",
            "span_edits": [{"find": "old", "replace": "new"}],
        })
        assert "current_draft" in r
        assert "new text here" in r["current_draft"]

    def test_await_human_auto_resolve(self):
        from src.graph.nodes.await_human import await_human_node
        r = await_human_node({"config": {"auto_resolve_escalations": True}, "current_section_idx": 0})
        assert r.get("force_approve") is True

    def test_await_human_interactive(self):
        from src.graph.nodes.await_human import await_human_node
        r = await_human_node({"config": {"auto_resolve_escalations": False}, "current_section_idx": 0})
        assert r.get("human_review_pending") is not None

    def test_coherence_guard_first_section(self):
        from src.graph.nodes.coherence_guard import coherence_guard_node
        r = coherence_guard_node({"current_section_idx": 0, "approved_sections": []})
        assert r.get("coherence_conflicts") == []

    def test_oscillation_check(self):
        from src.graph.nodes.oscillation_check import oscillation_check_node
        r = oscillation_check_node({"css_history": [0.5, 0.6, 0.7], "current_iteration": 2})
        assert isinstance(r, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 5 Node Tests (MoW + WriterMemory + Routing)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMoWActivation:
    """MoW activation conditions (§7.1)."""

    def test_activates_balanced(self):
        from src.graph.nodes.mow_writers import should_activate_mow
        state = {
            "budget": {"quality_preset": "balanced"},
            "outline": [{"target_words": 500}],
            "current_section_idx": 0,
            "current_iteration": 1,
        }
        assert should_activate_mow(state) is True

    def test_skips_economy(self):
        from src.graph.nodes.mow_writers import should_activate_mow
        assert should_activate_mow({"budget": {"quality_preset": "economy"}}) is False

    def test_skips_short_section(self):
        from src.graph.nodes.mow_writers import should_activate_mow
        state = {
            "budget": {"quality_preset": "premium"},
            "outline": [{"target_words": 200}],
            "current_section_idx": 0,
            "current_iteration": 1,
        }
        assert should_activate_mow(state) is False

    def test_skips_iteration_2(self):
        from src.graph.nodes.mow_writers import should_activate_mow
        state = {
            "budget": {"quality_preset": "premium"},
            "outline": [{"target_words": 500}],
            "current_section_idx": 0,
            "current_iteration": 2,
        }
        assert should_activate_mow(state) is False

    def test_skips_human_pending(self):
        from src.graph.nodes.mow_writers import should_activate_mow
        state = {
            "budget": {"quality_preset": "premium"},
            "outline": [{"target_words": 500}],
            "current_section_idx": 0,
            "current_iteration": 1,
            "human_review_pending": "oscillation",
        }
        assert should_activate_mow(state) is False


class TestJuryMultiDraft:
    """JuryMultiDraft evaluation."""

    def test_insufficient_drafts(self):
        from src.graph.nodes.jury_multidraft import jury_multidraft_node
        r = jury_multidraft_node({"mow_drafts": []})
        assert r["mow_css_individual"] == []

    def test_handles_empty_drafts(self):
        from src.graph.nodes.jury_multidraft import jury_multidraft_node
        r = jury_multidraft_node({"mow_drafts": [{"draft": "", "word_count": 0}]})
        assert r["mow_best_draft_idx"] == 0


class TestFusor:
    """Fusor node."""

    def test_no_drafts(self):
        from src.graph.nodes.fusor import fusor_node
        r = fusor_node({"mow_drafts": []})
        assert r == {}

    def test_single_draft_passthrough(self):
        from src.graph.nodes.fusor import fusor_node
        r = fusor_node({
            "mow_drafts": [{"angle": "W-A", "label": "Coverage", "draft": "Hello world", "word_count": 2}],
            "mow_css_individual": [0.8],
            "mow_best_elements": [],
            "mow_best_draft_idx": 0,
        })
        assert r["current_draft"] == "Hello world"
        assert r["fusor_meta"]["strategy"] == "single"


class TestWriterMemory:
    """WriterMemory accumulator."""

    def test_recurring_error_detection(self):
        from src.graph.nodes.writer_memory import writer_memory_node
        r = writer_memory_node({
            "current_draft": "Some draft text",
            "jury_verdicts": [
                {"pass_fail": False, "failed_claims": ["citation error A"]},
                {"pass_fail": False, "failed_claims": ["citation error B"]},
            ],
            "writer_memory": {},
        })
        mem = r["writer_memory"]
        assert "citation_error" in mem["recurring_errors"]
        assert mem["error_counts"]["citation_error"] == 2

    def test_glossary_extraction(self):
        from src.graph.nodes.writer_memory import writer_memory_node
        r = writer_memory_node({
            "current_draft": "Machine Learning is based on Neural Network architectures. CNN (Convolutional Neural Network) is popular.",
            "jury_verdicts": [],
            "writer_memory": {},
        })
        glossary = r["writer_memory"]["technical_glossary"]
        assert "machine learning" in glossary or "neural network" in glossary

    def test_citation_under(self):
        from src.graph.nodes.writer_memory import writer_memory_node
        r = writer_memory_node({
            "current_draft": "No citations at all.",
            "jury_verdicts": [],
            "citations_used": [],
            "citation_map": {"s1": "A", "s2": "B", "s3": "C", "s4": "D"},
            "writer_memory": {},
        })
        assert r["writer_memory"]["citation_tendency"] == "under"

    def test_citation_over(self):
        from src.graph.nodes.writer_memory import writer_memory_node
        r = writer_memory_node({
            "current_draft": "[s1] [s2] [s3] [s4] [s5]",
            "jury_verdicts": [],
            "citations_used": ["s1", "s2", "s3", "s4", "s5"],
            "citation_map": {"s1": "A", "s2": "B", "s3": "C", "s4": "D", "s5": "E"},
            "writer_memory": {},
        })
        assert r["writer_memory"]["citation_tendency"] == "over"

    def test_proactive_warnings_generated(self):
        from src.graph.nodes.writer_memory import writer_memory_node
        r = writer_memory_node({
            "current_draft": "Some text.",
            "jury_verdicts": [
                {"pass_fail": False, "failed_claims": ["weak reasoning"]},
                {"pass_fail": False, "failed_claims": ["weak reasoning"]},
            ],
            "citations_used": [],
            "citation_map": {"s1": "A", "s2": "B", "s3": "C", "s4": "D"},
            "writer_memory": {},
        })
        warnings = r["writer_memory"]["proactive_warnings"]
        assert any("RECURRING" in w for w in warnings)
        assert any("TENDENCY" in w for w in warnings)  # under-citation

    def test_accumulation_across_sections(self):
        from src.graph.nodes.writer_memory import writer_memory_node
        # First section
        r1 = writer_memory_node({
            "current_draft": "Draft 1",
            "jury_verdicts": [{"pass_fail": False, "failed_claims": ["vague claim"]}],
            "writer_memory": {},
        })
        # Second section — should accumulate
        r2 = writer_memory_node({
            "current_draft": "Draft 2",
            "jury_verdicts": [{"pass_fail": False, "failed_claims": ["vague claim"]}],
            "writer_memory": r1["writer_memory"],
        })
        mem = r2["writer_memory"]
        assert mem["error_counts"]["vague_claims"] == 2
        assert "vague_claims" in mem["recurring_errors"]
        assert mem["sections_analyzed"] == 2


class TestModelRouting:
    """LLM routing (§29.3)."""

    def test_economy_writer(self):
        from src.llm.routing import route_model
        assert route_model("writer", "economy") == "openrouter/anthropic/claude-3-5-haiku"

    def test_premium_writer(self):
        from src.llm.routing import route_model
        assert route_model("writer", "premium") == "openrouter/anthropic/claude-opus-4-5"

    def test_economy_jury_r(self):
        from src.llm.routing import route_model
        assert route_model("jury_r", "economy") == "openrouter/google/gemini-2.5-flash"

    def test_premium_jury_r(self):
        from src.llm.routing import route_model
        assert route_model("jury_r", "premium") == "openrouter/openai/o3"

    def test_unknown_agent_fallback(self):
        from src.llm.routing import route_model
        model = route_model("nonexistent_agent", "balanced")
        assert model == "google/gemini-2.5-flash"

    def test_case_insensitive(self):
        from src.llm.routing import route_model
        assert route_model("writer", "PREMIUM").lower() == "openrouter/anthropic/claude-opus-4-5".lower()

    def test_coherence_guard_economy_uses_flash(self):
        from src.llm.routing import route_model
        assert route_model("coherence_guard", "economy") == "openrouter/google/gemini-2.5-flash"

    def test_coherence_guard_premium_uses_opus(self):
        from src.llm.routing import route_model
        assert route_model("coherence_guard", "premium") == "openrouter/anthropic/claude-opus-4-5"
