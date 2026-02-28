"""Tests for RLM runtime, REPL sandbox, DocumentState contracts, and budget bridge.

Test strategy mirrors the failure modes identified in the critical analysis:
  1. Async isolation — no event loop nesting under LangGraph
  2. REPL sandbox — filesystem and import access blocked
  3. DocumentState contract — adapters return exactly the right keys
  4. Budget bridge — every sub-call becomes a CostEntry
  5. §5.11 preconditions — PostDraftAnalyzer skips correctly
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rlm.runtime import RLMRuntime, RLMResult, get_rlm_runtime


# ===========================================================================
# Fixtures
# ===========================================================================

def _minimal_state(
    quality_preset: str = "Balanced",
    iteration: int = 1,
    n_sources: int = 5,
    rlm_flags: dict | None = None,
) -> dict:
    """Minimal valid DocumentState for adapter tests."""
    if rlm_flags is None:
        rlm_flags = {
            "rlm_enabled": True,
            "rlm_agents": ["source_synthesizer_rlm", "coherence_guard_rlm"],
            "rlm_source_synthesizer": True,
            "rlm_coherence_guard": True,
            "rlm_post_draft_analyzer": True,
        }
    return {
        "doc_id": "test-doc-001",
        "current_section_idx": 0,
        "current_iteration": iteration,
        "current_draft": "The global economy expanded by 3.2% in 2023 according to IMF data.",
        "current_sources": [
            {
                "title": f"Source {i}",
                "source_type": "academic",
                "reliability_score": 0.85,
                "nli_entailment": 0.91,
                "abstract": f"Abstract text for source {i}.",
                "full_text": f"Full text for source {i}. " * 50,
            }
            for i in range(n_sources)
        ],
        "approved_sections": [],
        "outline": [
            {
                "title": "Economic Overview",
                "scope": "Global economic trends 2023",
                "target_words": 800,
                "dependencies": [],
            }
        ],
        "config": {
            "quality_preset": quality_preset,
            "max_budget_dollars": 50.0,
            "target_compression_ratio": 0.40,
            "rlm_root_model": "claude-sonnet-4-5",
            "rlm_sub_model": "claude-haiku-3-5",
            "features": rlm_flags,
        },
        "budget": {
            "max_dollars": 50.0,
            "spent_dollars": 0.0,
            "projected_final": 0.0,
            "regime": "Balanced",
            "css_threshold": 0.70,
            "max_iterations": 4,
            "jury_size": 2,
            "mow_enabled": True,
            "alarm_70_fired": False,
            "alarm_90_fired": False,
            "hard_stop_fired": False,
        },
    }


def _make_rlm_result(
    output: object = None,
    method: str = "repl_final",
    cost: float = 0.02,
    subcalls: int = 3,
) -> RLMResult:
    return RLMResult(
        output=output or {"test": True},
        cost_usd=cost,
        subcalls=subcalls,
        iterations=2,
        log=[
            {
                "event": "SUBCALL",
                "detail": {
                    "n": 1,
                    "tokens_in": 500,
                    "tokens_out": 200,
                    "cost_usd": 0.001,
                    "latency_ms": 400,
                },
                "ts": 0.0,
            },
            {
                "event": "ROOT_TOKENS",
                "detail": {
                    "tokens_in": 2000,
                    "tokens_out": 600,
                    "cost_usd": 0.015,
                    "latency_ms": 1200,
                },
                "ts": 0.1,
            },
        ],
        method=method,
        root_model="claude-sonnet-4-5",
        sub_model="claude-haiku-3-5",
    )


# ===========================================================================
# 1. Async isolation tests
# ===========================================================================

class TestRLMRuntimeAsyncIsolation:
    """Verify run() works from an active event loop (LangGraph scenario)."""

    @pytest.mark.asyncio
    async def test_run_does_not_raise_event_loop_error(self):
        """run() must not raise RuntimeError('cannot run nested event loop')."""
        rlm = get_rlm_runtime(max_subcalls=2, cost_hard_limit=0.01, timeout_seconds=10)

        with patch.object(rlm, "_run_async", new_callable=AsyncMock) as mock:
            mock.return_value = _make_rlm_result()
            # Awaiting from an active event loop — must not deadlock or raise
            result = await rlm.run(context={"x": 1}, task_instruction="test task")

        assert result is not None

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback(self):
        """If thread does not complete in time, return fallback result."""
        rlm = get_rlm_runtime(timeout_seconds=1)

        async def _slow(*_a, **_kw):  # noqa: ANN002, ANN003
            await asyncio.sleep(10)  # far exceeds timeout
            return _make_rlm_result()

        with patch.object(rlm, "_run_async", side_effect=_slow):
            # Override queue.get timeout to 0.1s for test speed
            with patch("src.rlm.runtime.Queue") as MockQueue:
                from queue import Empty
                mock_q = MagicMock()
                mock_q.get.side_effect = Empty
                MockQueue.return_value = mock_q
                result = await rlm.run(context={}, task_instruction="test")

        assert result.method == "fallback"
        assert result.output is None


# ===========================================================================
# 2. REPL sandbox tests
# ===========================================================================

class TestREPLSandbox:
    """Verify RestrictedPython blocks dangerous operations."""

    def setup_method(self):
        self.rlm = RLMRuntime()

    def test_file_open_blocked(self):
        state = {}
        result = self.rlm._exec_code_sandboxed(
            "f = open('/etc/passwd', 'r')\nprint(f.read())", state
        )
        assert "/etc/passwd" not in result
        assert "Error" in result or "NameError" in result

    def test_import_os_blocked(self):
        state = {}
        result = self.rlm._exec_code_sandboxed(
            "import os\nprint(os.listdir('/'))", state
        )
        assert "Error" in result or "ImportError" in result

    def test_import_subprocess_blocked(self):
        state = {}
        result = self.rlm._exec_code_sandboxed(
            "import subprocess\nsubprocess.run(['ls'])", state
        )
        assert "Error" in result or "ImportError" in result

    def test_final_answer_propagated_to_state(self):
        state = {"data": [1, 2, 3]}
        self.rlm._exec_code_sandboxed(
            "final_answer = {'total': sum(data), 'count': len(data)}", state
        )
        assert state.get("final_answer") == {"total": 6, "count": 3}

    def test_stdout_captured(self):
        state = {}
        result = self.rlm._exec_code_sandboxed("x = 2 + 2\nprint(f'result: {x}')", state)
        assert "result: 4" in result

    def test_runtime_error_does_not_raise(self):
        """REPL errors must be returned as strings, not propagated as exceptions."""
        state = {}
        result = self.rlm._exec_code_sandboxed("x = 1 / 0", state)
        assert "Error" in result
        assert "ZeroDivision" in result

    def test_json_available_in_repl(self):
        state = {}
        result = self.rlm._exec_code_sandboxed(
            'import json\ndata = json.dumps({"k": 1})\nprint(data)', state
        )
        assert '{"k": 1}' in result


# ===========================================================================
# 3. DocumentState contract tests
# ===========================================================================

COHERENCE_GUARD_KEYS = frozenset({"coherence_conflicts", "conflict_detected"})
POST_DRAFT_KEYS = frozenset({"post_draft_gaps", "gap_found"})
SOURCE_SYNTH_KEYS = frozenset({"compressed_corpus", "compression_ratio_achieved", "skipped_source_ids"})


class TestDocumentStateContract:
    """Adapters must return exactly the keys their spec requires — no more, no less."""

    @pytest.mark.asyncio
    async def test_coherence_guard_output_keys(self):
        from src.rlm.adapters.coherence_guard_rlm import coherence_guard_rlm_node

        state = _minimal_state()
        state["approved_sections"] = [
            {"idx": i, "title": f"Section {i}", "content": "Some content here."}
            for i in range(4)
        ]

        with patch("src.rlm.runtime.RLMRuntime.run", new_callable=AsyncMock) as mock_run, \
             patch("src.rlm.budget_bridge.emit_cost_entries", new_callable=AsyncMock):
            mock_run.return_value = _make_rlm_result(
                output={"conflicts": [], "conflict_detected": False, "sections_checked": []}
            )
            result = await coherence_guard_rlm_node(state)

        unexpected = set(result.keys()) - COHERENCE_GUARD_KEYS
        assert not unexpected, f"Unexpected output keys: {unexpected}"
        assert "coherence_conflicts" in result
        assert "conflict_detected" in result

    @pytest.mark.asyncio
    async def test_source_synthesizer_output_keys(self):
        from src.rlm.adapters.source_synthesizer_rlm import source_synthesizer_rlm_node

        state = _minimal_state(n_sources=5)

        with patch("src.rlm.runtime.RLMRuntime.run", new_callable=AsyncMock) as mock_run, \
             patch("src.rlm.budget_bridge.emit_cost_entries", new_callable=AsyncMock):
            mock_run.return_value = _make_rlm_result(
                output={
                    "compressed_corpus": "Compressed text [src:0] [src:1]",
                    "compression_ratio_achieved": 0.38,
                    "skipped_source_ids": [],
                }
            )
            result = await source_synthesizer_rlm_node(state)

        unexpected = set(result.keys()) - SOURCE_SYNTH_KEYS
        assert not unexpected, f"Unexpected output keys: {unexpected}"

    @pytest.mark.asyncio
    async def test_post_draft_output_keys(self):
        from src.rlm.adapters.post_draft_analyzer_rlm import post_draft_analyzer_rlm_node

        state = _minimal_state(n_sources=5)

        with patch("src.rlm.runtime.RLMRuntime.run", new_callable=AsyncMock) as mock_run, \
             patch("src.rlm.budget_bridge.emit_cost_entries", new_callable=AsyncMock):
            mock_run.return_value = _make_rlm_result(
                output={
                    "gaps": [{"category": "missing_evidence",
                              "description": "Missing Q4 data",
                              "suggested_queries": ["Q4 2023 GDP"]}],
                    "gap_found": True,
                }
            )
            result = await post_draft_analyzer_rlm_node(state)

        unexpected = set(result.keys()) - POST_DRAFT_KEYS
        assert not unexpected, f"Unexpected output keys: {unexpected}"


# ===========================================================================
# 4. §5.11 precondition tests
# ===========================================================================

class TestPostDraftPreconditions:
    """§5.11 requires specific conditions — adapter must skip otherwise."""

    @pytest.mark.asyncio
    async def test_skips_on_economy_preset(self):
        from src.rlm.adapters.post_draft_analyzer_rlm import post_draft_analyzer_rlm_node
        state = _minimal_state(quality_preset="Economy")
        result = await post_draft_analyzer_rlm_node(state)
        assert result == {"post_draft_gaps": [], "gap_found": False}

    @pytest.mark.asyncio
    async def test_skips_on_iteration_gt_1(self):
        from src.rlm.adapters.post_draft_analyzer_rlm import post_draft_analyzer_rlm_node
        state = _minimal_state(iteration=2)
        result = await post_draft_analyzer_rlm_node(state)
        assert result == {"post_draft_gaps": [], "gap_found": False}

    @pytest.mark.asyncio
    async def test_skips_when_20_or_more_sources(self):
        from src.rlm.adapters.post_draft_analyzer_rlm import post_draft_analyzer_rlm_node
        state = _minimal_state(n_sources=20)
        result = await post_draft_analyzer_rlm_node(state)
        assert result == {"post_draft_gaps": [], "gap_found": False}

    @pytest.mark.asyncio
    async def test_skips_when_target_words_below_400(self):
        from src.rlm.adapters.post_draft_analyzer_rlm import post_draft_analyzer_rlm_node
        state = _minimal_state()
        state["outline"][0]["target_words"] = 350
        result = await post_draft_analyzer_rlm_node(state)
        assert result == {"post_draft_gaps": [], "gap_found": False}

    @pytest.mark.asyncio
    async def test_caps_gaps_at_3(self):
        from src.rlm.adapters.post_draft_analyzer_rlm import post_draft_analyzer_rlm_node
        state = _minimal_state(n_sources=5)

        many_gaps = [
            {"category": "missing_evidence", "description": f"Gap {i}",
             "suggested_queries": [f"query {i}"]}
            for i in range(6)  # 6 gaps → must be capped at 3
        ]

        with patch("src.rlm.runtime.RLMRuntime.run", new_callable=AsyncMock) as mock_run, \
             patch("src.rlm.budget_bridge.emit_cost_entries", new_callable=AsyncMock):
            mock_run.return_value = _make_rlm_result(
                output={"gaps": many_gaps, "gap_found": True}
            )
            result = await post_draft_analyzer_rlm_node(state)

        assert len(result["post_draft_gaps"]) <= 3


# ===========================================================================
# 5. Budget bridge tests
# ===========================================================================

class TestBudgetBridge:
    """emit_cost_entries must produce exactly one CostEntry per log event."""

    @pytest.mark.asyncio
    async def test_emits_one_entry_per_subcall_and_root(self):
        from src.rlm.budget_bridge import emit_cost_entries

        result = _make_rlm_result()  # 1 SUBCALL + 1 ROOT_TOKENS
        state = _minimal_state()
        recorded: list = []

        with patch("src.rlm.budget_bridge.RealTimeCostTracker") as MockTracker:
            instance = MagicMock()
            instance.record = AsyncMock(side_effect=lambda e, b: recorded.append(e))
            MockTracker.return_value = instance

            await emit_cost_entries(state=state, agent="test_agent", rlm_result=result)

        assert len(recorded) == 2
        agents = [e.agent for e in recorded]
        assert "test_agent" in agents
        assert "test_agent_root" in agents

    @pytest.mark.asyncio
    async def test_no_crash_if_tracker_missing(self):
        """If budget tracker module not yet implemented, emit a warning and continue."""
        from src.rlm.budget_bridge import emit_cost_entries
        result = _make_rlm_result()
        state = _minimal_state()

        with patch("src.rlm.budget_bridge.RealTimeCostTracker", side_effect=ImportError):
            # Must not raise — just log warning
            await emit_cost_entries(state=state, agent="test_agent", rlm_result=result)


# ===========================================================================
# 6. Budget overhead estimation
# ===========================================================================

class TestBudgetOverheadEstimate:

    def test_overhead_positive_for_known_agents(self):
        from src.rlm.budget_bridge import estimate_rlm_overhead
        overhead = estimate_rlm_overhead(
            n_sections=10,
            rlm_agents_enabled=["source_synthesizer_rlm", "coherence_guard_rlm"],
        )
        assert overhead > 0
        assert isinstance(overhead, float)

    def test_overhead_zero_for_empty_agents(self):
        from src.rlm.budget_bridge import estimate_rlm_overhead
        assert estimate_rlm_overhead(n_sections=10, rlm_agents_enabled=[]) == 0.0

    def test_overhead_scales_with_sections(self):
        from src.rlm.budget_bridge import estimate_rlm_overhead
        overhead_10 = estimate_rlm_overhead(10, ["source_synthesizer_rlm"])
        overhead_20 = estimate_rlm_overhead(20, ["source_synthesizer_rlm"])
        assert abs(overhead_20 - overhead_10 * 2) < 0.0001

    def test_unknown_agent_is_skipped(self):
        from src.rlm.budget_bridge import estimate_rlm_overhead
        # Should not raise, just log a warning
        overhead = estimate_rlm_overhead(5, ["nonexistent_agent_rlm"])
        assert overhead == 0.0
