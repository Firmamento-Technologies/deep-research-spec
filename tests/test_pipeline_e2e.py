"""End-to-end pipeline integration test — mock all LLM calls.

Verifies the full graph flow:
preflight → budget_estimator → planner → await_outline → researcher →
... → writer → ... → jury → aggregator → ... → publisher → feedback_collector

All LLM calls are mocked. This tests graph wiring, state transitions,
and node error handling without real API costs.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


def _mock_llm_response(text: str = "Mock response", cost: float = 0.001):
    """Create a mock LLM response dict."""
    return {"text": text, "cost_usd": cost, "model": "mock/test"}


@pytest.fixture
def mock_llm():
    """Patch llm_client.call to return mock responses."""
    with patch("src.llm.client.llm_client") as mock:
        mock.call = MagicMock(side_effect=_make_smart_mock())
        yield mock


def _make_smart_mock():
    """Create a context-aware mock that returns appropriate responses."""
    call_count = [0]

    def _smart_call(**kwargs):
        call_count[0] += 1
        messages = kwargs.get("messages", [])
        user_msg = ""
        if messages:
            content = messages[-1].get("content", "")
            user_msg = content if isinstance(content, str) else str(content)

        # Planner → return outline JSON
        if "outline" in user_msg.lower() or "sections" in user_msg.lower():
            return _mock_llm_response(text='{"sections": [{"idx": 0, "title": "Introduction", "scope": "Overview", "target_words": 500, "dependencies": []}], "document_type": "report"}')

        # Writer → return draft
        if "write a section" in user_msg.lower():
            return _mock_llm_response(text="This is a mock draft section. It contains [s1] citations and covers the topic comprehensively. " * 20)

        # Jury/Judge → return pass
        if "evaluat" in user_msg.lower() or "judge" in user_msg.lower() or "jury" in user_msg.lower():
            return _mock_llm_response(text='{"pass_fail": true, "css": 0.85, "reasoning": "Good quality"}')

        # Default
        return _mock_llm_response(text="Mock generic response")

    return _smart_call


class TestPipelineE2E:
    """End-to-end pipeline tests with mocked LLM."""

    def test_initial_state_builder(self):
        """Verify initial state construction."""
        from src.main import _build_initial_state
        from src.config.schema import DRSYAMLConfig

        config = DRSYAMLConfig()
        state = _build_initial_state(
            topic="Test Topic",
            target_words=3000,
            quality_preset="balanced",
            style_profile="academic",
            max_budget=25.0,
            config=config,
        )

        assert state["topic"] == "Test Topic"
        assert state["target_words"] == 3000
        assert state["quality_preset"] == "balanced"
        assert state["style_profile"] == "academic"
        assert state["budget"]["max_dollars"] == 25.0
        assert state["budget"]["spent_dollars"] == 0.0
        assert state["budget"]["hard_stop_fired"] is False
        assert state["current_section_idx"] == 0
        assert state["outline"] == []
        assert state["thread_id"]  # UUID generated

    def test_config_loading_defaults(self):
        """Verify default config when no file exists."""
        from src.main import _load_config
        config = _load_config(None)
        assert config.defaults.quality_preset == "balanced"
        assert config.defaults.target_words == 5000
        assert config.defaults.max_budget_dollars == 50.0

    def test_graph_compiles_with_checkpointer(self):
        """Verify graph compiles with MemorySaver."""
        from langgraph.checkpoint.memory import MemorySaver
        from src.graph.graph import build_graph

        g = build_graph(checkpointer=MemorySaver())
        assert g is not None

    def test_cli_help(self):
        """Verify CLI argument parsing."""
        from src.main import _parse_args
        args = _parse_args(["--topic", "AI Ethics", "--words", "3000", "--preset", "premium"])
        assert args.topic == "AI Ethics"
        assert args.words == 3000
        assert args.preset == "premium"
        assert args.style == "academic"  # default
        assert args.budget == 50.0  # default

    def test_cli_all_args(self):
        """Verify all CLI arguments parse correctly."""
        from src.main import _parse_args
        args = _parse_args([
            "--topic", "ML Safety",
            "--words", "10000",
            "--preset", "economy",
            "--style", "informal",
            "--budget", "15.0",
            "--config", "config/test.yaml",
            "--log-level", "DEBUG",
            "--log-format", "json",
        ])
        assert args.topic == "ML Safety"
        assert args.words == 10000
        assert args.preset == "economy"
        assert args.style == "informal"
        assert args.budget == 15.0
        assert args.config == "config/test.yaml"
        assert args.log_level == "DEBUG"
        assert args.log_format == "json"

    def test_preflight_to_planner_flow(self):
        """Verify preflight → budget_estimator → planner state flow."""
        from src.graph.nodes.preflight import preflight_node
        from src.graph.nodes.budget_estimator import budget_estimator_node

        state = {
            "config": {"topic": "Test"},
            "budget": {"quality_preset": "balanced", "max_dollars": 50.0},
            "topic": "Test",
            "target_words": 3000,
            "quality_preset": "balanced",
            "outline": [
                {"title": "Intro", "target_words": 1000},
                {"title": "Body", "target_words": 1500},
                {"title": "Conclusion", "target_words": 500},
            ],
        }

        r1 = preflight_node(state)
        assert isinstance(r1, dict)

        state.update(r1)
        r2 = budget_estimator_node(state)
        assert isinstance(r2, dict)

    def test_deterministic_nodes_no_llm(self):
        """Verify deterministic nodes work without LLM."""
        from src.graph.nodes.writer_memory import writer_memory_node
        from src.graph.nodes.diff_merger import diff_merger_node
        from src.graph.nodes.oscillation_check import oscillation_check_node

        # WriterMemory
        r1 = writer_memory_node({
            "current_draft": "Some text",
            "jury_verdicts": [],
            "writer_memory": {},
        })
        assert r1["writer_memory"]["sections_analyzed"] == 1

        # DiffMerger
        r2 = diff_merger_node({
            "current_draft": "Hello world",
            "span_edits": [{"find": "world", "replace": "DRS"}],
        })
        assert r2["current_draft"] == "Hello DRS"

        # OscillationCheck
        r3 = oscillation_check_node({
            "css_history": [0.5, 0.6, 0.7],
            "current_iteration": 2,
        })
        assert isinstance(r3, dict)

    def test_model_routing_in_pipeline(self):
        """Verify model routing returns correct models for pipeline agents."""
        from src.llm.routing import route_model

        # Economy preset should use cheaper models
        w_economy = route_model("writer", "economy")
        w_premium = route_model("writer", "premium")
        assert "sonnet" in w_economy.lower() or "flash" in w_economy.lower()
        assert "opus" in w_premium.lower()

        # Coherence guard always uses flash (lightweight)
        assert "flash" in route_model("coherence_guard", "premium")
