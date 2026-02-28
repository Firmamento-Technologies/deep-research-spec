"""RLM Integration Test Suite — Steps 1–12 of the RLM Optimisation Plan.

Covers all six optimisation areas introduced by the plan:
  - Per-model rate limiter  (src.llm.rate_limiter)
  - Heterogeneous routing   (src.llm.routing)
  - Writer rlm_mode path    (src.graph.nodes.writer)
  - RLM budget controller   (src.budget.controller)
  - Source synthesizer bypass (src.graph.nodes.source_synthesizer)
  - Context compressor bypass (src.graph.nodes.context_compressor)

Run::

    pytest tests/test_rlm_integration.py -v
    pytest tests/test_rlm_integration.py -v -k TestRLMBudgetController

All async node functions are invoked via asyncio.run() so no pytest-asyncio
plugin is required.
"""
from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# TestRLMRateLimiter
# =============================================================================

class TestRLMRateLimiter:
    """Tests for PerModelRateLimiter and singleton (src.llm.rate_limiter)."""

    def test_estimate_tokens_str(self):
        from src.llm.rate_limiter import estimate_tokens
        result = estimate_tokens("hello world this is a test string")
        assert isinstance(result, int)
        assert result > 0

    def test_estimate_tokens_messages_list(self):
        from src.llm.rate_limiter import estimate_tokens
        messages = [
            {"role": "user",      "content": "hello world"},
            {"role": "assistant", "content": "sure, here you go"},
        ]
        result = estimate_tokens(messages)
        assert isinstance(result, int)
        assert result > 0

    def test_estimate_tokens_cache_control_blocks(self):
        """Handles Anthropic list[dict] system prompt with cache_control."""
        from src.llm.rate_limiter import estimate_tokens
        blocks = [
            {"type": "text", "text": "You are a helpful assistant.",
             "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "Style rules: be concise."},
        ]
        result = estimate_tokens(blocks)
        assert isinstance(result, int)
        assert result > 0

    def test_singleton_identity(self):
        """rlm_rate_limiter must be the exact same object on every import."""
        from src.llm.rate_limiter import rlm_rate_limiter as r1
        from src.llm.rate_limiter import rlm_rate_limiter as r2
        assert r1 is r2

    def test_acquire_does_not_block_indefinitely(self):
        """acquire() for a known model must complete within a reasonable timeout."""
        from src.llm.rate_limiter import rlm_rate_limiter
        start = time.monotonic()
        rlm_rate_limiter.acquire(
            model="anthropic/claude-sonnet-4",
            estimated_tokens=50,
            timeout=5.0,
        )
        assert (time.monotonic() - start) < 3.0

    def test_on_429_does_not_raise(self):
        """on_429() must update backoff state without raising."""
        from src.llm.rate_limiter import rlm_rate_limiter
        rlm_rate_limiter.on_429(model="openrouter/openai/o3-mini")


# =============================================================================
# TestRLMRouting
# =============================================================================

class TestRLMRouting:
    """Tests for route_jury_slots() heterogeneous assignments (src.llm.routing)."""

    def test_route_jury_slots_size_1(self):
        from src.llm.routing import route_jury_slots
        result = route_jury_slots("r", "economy", 1)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], str)

    def test_route_jury_slots_size_2(self):
        from src.llm.routing import route_jury_slots
        result = route_jury_slots("r", "balanced", 2)
        assert len(result) == 2

    def test_route_jury_slots_size_3(self):
        from src.llm.routing import route_jury_slots
        result = route_jury_slots("r", "premium", 3)
        assert len(result) == 3

    def test_route_jury_slots_heterogeneous_premium(self):
        """Premium preset: 3 slots must use 3 distinct provider backbones."""
        from src.llm.routing import route_jury_slots
        slots = route_jury_slots("r", "premium", 3)
        for s in slots:
            assert isinstance(s, str) and len(s) > 0
        assert len(set(slots)) == 3, (
            f"Expected 3 distinct models for premium jury, got: {slots}"
        )

    def test_route_jury_slots_all_panels(self):
        """route_jury_slots() must work for all three jury panels."""
        from src.llm.routing import route_jury_slots
        for panel in ("r", "f", "s"):
            result = route_jury_slots(panel, "balanced", 3)
            assert len(result) == 3, f"Panel {panel} returned wrong size"

    def test_route_jury_slots_invalid_preset_fallback(self):
        """Unknown preset must not raise — must return a valid model string."""
        from src.llm.routing import route_jury_slots
        result = route_jury_slots("r", "nonexistent_preset_xyz", 1)
        assert len(result) == 1
        assert isinstance(result[0], str)

    def test_route_model_writer_uses_anthropic_prefix(self):
        """Writer must always route to anthropic/ for \u00a729.1 prompt caching."""
        from src.llm.routing import route_model
        for preset in ("economy", "balanced", "premium"):
            model = route_model("writer", preset)
            assert model.startswith("anthropic/"), (
                f"Writer model '{model}' must start with 'anthropic/' "
                f"(preset={preset}) to enable \u00a729.1 prompt caching"
            )


# =============================================================================
# TestRLMWriter
# =============================================================================

class TestRLMWriter:
    """Tests for writer_node rlm_mode path (Step 5)."""

    _MOCK_RESPONSE = {"text": "Generated section draft.", "cost_usd": 0.01}

    def _base_state(self, **overrides) -> dict:
        state: dict = {
            "current_section_idx": 0,
            "outline": [{"scope": "Introduction", "title": "Intro", "target_words": 500}],
            "style_profile": "academic",
            "style_exemplar": "",
            "writer_memory": {},
            "current_sources": [],
            "quality_preset": "balanced",
            "current_iteration": 0,
        }
        state.update(overrides)
        return state

    @patch("src.graph.nodes.writer.llm_client")
    @patch("src.graph.nodes.writer.route_model", return_value="anthropic/claude-sonnet-4")
    def test_rlm_mode_uses_sanitized_sources(self, _route, mock_client):
        """rlm_mode=True: corpus must come from sanitized_sources (not synthesized)."""
        mock_client.call.return_value = self._MOCK_RESPONSE
        from src.graph.nodes.writer import writer_node
        state = self._base_state(
            rlm_mode=True,
            sanitized_sources="RAW_CORPUS_CONTENT",
            synthesized_sources="SYNTHESIZED_CONTENT",
        )
        writer_node(state)
        user_content = mock_client.call.call_args[1]["messages"][0]["content"]
        assert "RAW_CORPUS_CONTENT"  in user_content
        assert "SYNTHESIZED_CONTENT" not in user_content

    @patch("src.graph.nodes.writer.llm_client")
    @patch("src.graph.nodes.writer.route_model", return_value="anthropic/claude-sonnet-4")
    def test_standard_mode_uses_synthesized_sources(self, _route, mock_client):
        """rlm_mode=False: corpus must come from synthesized_sources."""
        mock_client.call.return_value = self._MOCK_RESPONSE
        from src.graph.nodes.writer import writer_node
        state = self._base_state(
            rlm_mode=False,
            sanitized_sources="RAW_CORPUS_CONTENT",
            synthesized_sources="SYNTHESIZED_CONTENT",
        )
        writer_node(state)
        user_content = mock_client.call.call_args[1]["messages"][0]["content"]
        assert "SYNTHESIZED_CONTENT" in user_content
        assert "RAW_CORPUS_CONTENT"  not in user_content

    @patch("src.graph.nodes.writer.llm_client")
    @patch("src.graph.nodes.writer.route_model", return_value="anthropic/claude-sonnet-4")
    def test_rlm_mode_fallback_chain_to_research_results(self, _route, mock_client):
        """sanitized_sources empty → fallback to research_results."""
        mock_client.call.return_value = self._MOCK_RESPONSE
        from src.graph.nodes.writer import writer_node
        state = self._base_state(
            rlm_mode=True,
            sanitized_sources="",
            research_results="RESEARCH_RESULTS_CONTENT",
            synthesized_sources="SYNTHESIZED_CONTENT",
        )
        writer_node(state)
        user_content = mock_client.call.call_args[1]["messages"][0]["content"]
        assert "RESEARCH_RESULTS_CONTENT" in user_content

    @patch("src.graph.nodes.writer.llm_client")
    @patch("src.graph.nodes.writer.route_model", return_value="anthropic/claude-sonnet-4")
    def test_shine_path_takes_priority_over_rlm(self, _route, mock_client):
        """shine_active=True overrides rlm_mode=True (SHINE wins)."""
        mock_client.call.return_value = self._MOCK_RESPONSE
        from src.graph.nodes.writer import writer_node
        state = self._base_state(
            rlm_mode=True,
            shine_active=True,
            sanitized_sources="RAW_CORPUS_MUST_NOT_APPEAR",
        )
        writer_node(state)
        user_content = mock_client.call.call_args[1]["messages"][0]["content"]
        # SHINE prompt template does not include corpus text
        assert "RAW_CORPUS_MUST_NOT_APPEAR" not in user_content

    @patch("src.graph.nodes.writer.llm_client")
    @patch("src.graph.nodes.writer.route_model", return_value="anthropic/claude-sonnet-4")
    def test_writer_returns_correct_keys(self, _route, mock_client):
        """writer_node must return current_draft and current_iteration."""
        mock_client.call.return_value = {"text": "My draft.", "cost_usd": 0.005}
        from src.graph.nodes.writer import writer_node
        result = writer_node(self._base_state(
            rlm_mode=False, synthesized_sources="corpus"
        ))
        assert result["current_draft"] == "My draft."
        assert "current_iteration" in result


# =============================================================================
# TestRLMBudgetController
# =============================================================================

class TestRLMBudgetController:
    """Tests for RLMBudgetController (src.budget.controller)."""

    def setup_method(self):
        from src.budget.controller import RLMBudgetController
        self.ctrl = RLMBudgetController()  # fresh instance per test

    def test_initial_state_zero(self):
        s = self.ctrl.summary()
        assert s["rlm_subcall_count"]    == 0
        assert s["rlm_tokens_total"]     == 0
        assert s["rlm_cost_total"]       == 0.0

    def test_track_single_subcall(self):
        self.ctrl.track_rlm_subcall(1000, 500, "openai/o3-mini", 0.003)
        s = self.ctrl.summary()
        assert s["rlm_subcall_count"]    == 1
        assert s["rlm_tokens_in_total"]  == 1000
        assert s["rlm_tokens_out_total"] == 500
        assert s["rlm_tokens_total"]     == 1500
        assert abs(s["rlm_cost_total"] - 0.003) < 1e-9

    def test_track_multiple_subcalls_accumulate(self):
        self.ctrl.track_rlm_subcall(100, 50, "model-a", 0.001)
        self.ctrl.track_rlm_subcall(200, 100, "model-b", 0.002)
        self.ctrl.track_rlm_subcall(300, 150, "model-c", 0.003)
        s = self.ctrl.summary()
        assert s["rlm_subcall_count"] == 3
        assert s["rlm_tokens_total"]  == 900
        assert abs(s["rlm_cost_total"] - 0.006) < 1e-9

    def test_reset_clears_everything(self):
        self.ctrl.track_rlm_subcall(500, 250, "model-x", 0.005)
        self.ctrl.reset()
        s = self.ctrl.summary()
        assert s["rlm_subcall_count"] == 0
        assert s["rlm_tokens_total"]  == 0
        assert s["rlm_cost_total"]    == 0.0

    def test_properties_reflect_state(self):
        self.ctrl.track_rlm_subcall(100, 50, "model", 0.001)
        assert self.ctrl.rlm_tokens_total == 150
        assert abs(self.ctrl.rlm_cost_total - 0.001) < 1e-9

    def test_thread_safety_concurrent_writes(self):
        """500 concurrent track_rlm_subcall() calls must produce exact totals."""
        errors: list = []

        def worker(n: int) -> None:
            try:
                for _ in range(n):
                    self.ctrl.track_rlm_subcall(
                        tokens_in=10, tokens_out=5,
                        model="test-model", cost_usd=0.0001,
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(50,)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        s = self.ctrl.summary()
        assert s["rlm_subcall_count"] == 500
        assert s["rlm_tokens_total"]  == 500 * 15        # 10 + 5 per call
        assert abs(s["rlm_cost_total"] - 500 * 0.0001) < 1e-6

    def test_module_singleton_importable(self):
        from src.budget.controller import rlm_budget_controller
        assert rlm_budget_controller is not None

    def test_repr_contains_class_name(self):
        assert "RLMBudgetController" in repr(self.ctrl)


# =============================================================================
# TestSourceSynthesizerBypass
# =============================================================================

class TestSourceSynthesizerBypass:
    """Tests for rlm_mode bypass guard in source_synthesizer_node (Step 6)."""

    def test_bypass_returns_same_state_object(self):
        """rlm_mode=True: must return the exact same state dict (no-op)."""
        from src.graph.nodes.source_synthesizer import source_synthesizer_node
        state = {
            "rlm_mode": True,
            "current_sources": [{"source_id": "s1", "abstract": "content"}],
            "synthesized_sources": "existing",
        }
        result = asyncio.run(source_synthesizer_node(state))
        assert result is state, "Expected same object (no-op bypass)"

    def test_no_bypass_when_rlm_mode_false(self):
        """rlm_mode=False: must run normally and return synthesized_sources."""
        from src.graph.nodes.source_synthesizer import source_synthesizer_node
        state = {"rlm_mode": False, "current_sources": []}
        result = asyncio.run(source_synthesizer_node(state))
        assert "synthesized_sources" in result

    def test_no_bypass_when_rlm_mode_absent(self):
        """Absent rlm_mode (default False) must not bypass."""
        from src.graph.nodes.source_synthesizer import source_synthesizer_node
        state = {"current_sources": []}
        result = asyncio.run(source_synthesizer_node(state))
        assert "synthesized_sources" in result


# =============================================================================
# TestContextCompressorBypass
# =============================================================================

class TestContextCompressorBypass:
    """Tests for rlm_mode bypass guard in context_compressor.run (Step 7)."""

    def test_bypass_returns_same_state_object(self):
        """rlm_mode=True: run() must return the exact same state dict."""
        from src.graph.nodes import context_compressor
        state = {
            "rlm_mode": True,
            "current_section_idx": 1,
            "approved_sections": [{"idx": 0, "content": "Section 0."}],
            "outline": [{"title": "Intro"}, {"title": "Methods"}],
            "run_id": "test-run-cc-001",
        }
        result = asyncio.run(context_compressor.run(state))
        assert result is state, "Expected same object (no-op bypass)"

    def test_no_bypass_section_0_returns_none_context(self):
        """Section 0 (no prior sections) — legitimate skip per §14.4, not an RLM bypass."""
        from src.graph.nodes import context_compressor
        state = {
            "rlm_mode": False,
            "current_section_idx": 0,
            "approved_sections": [],
            "outline": [{"title": "Intro"}],
            "run_id": "test-run-cc-002",
            "shine_enabled": False,
        }
        result = asyncio.run(context_compressor.run(state))
        assert result.get("compressed_context") is None    # §14.4 spec
        assert result.get("active_lora_section_idxs") == []

    def test_bypass_preserves_all_state_fields(self):
        """Bypass must not mutate or lose any field in the state dict."""
        from src.graph.nodes import context_compressor
        state = {
            "rlm_mode": True,
            "run_id": "preserve-test",
            "sanitized_sources": "raw corpus content",
            "current_section_idx": 5,
            "quality_preset": "premium",
        }
        result = asyncio.run(context_compressor.run(state))
        assert result["run_id"]               == "preserve-test"
        assert result["sanitized_sources"]    == "raw corpus content"
        assert result["current_section_idx"]  == 5
        assert result["quality_preset"]       == "premium"
