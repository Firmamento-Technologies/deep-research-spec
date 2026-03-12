"""Tests for observability metrics and LLM client integration."""
from __future__ import annotations

import unittest

from src.observability.metrics import (
    _HAS_PROMETHEUS,
    _StubMetric,
    DRS_LLM_CALLS,
    DRS_LLM_COST,
    DRS_LLM_LATENCY,
    DRS_TOKENS_IN,
    DRS_TOKENS_OUT,
    DRS_SECTIONS_COMPLETED,
    DRS_ITERATIONS,
    DRS_CSS_SCORE,
    DRS_BUDGET_SPENT,
    DRS_BUDGET_REMAINING_PCT,
    DRS_PIPELINE_DURATION,
    observe_llm_call,
    update_budget_gauge,
    update_css_scores,
)


class TestMetricsAvailability(unittest.TestCase):
    """Test that metrics module is importable and functional."""

    def test_has_prometheus_flag(self):
        """prometheus-client should be installed in dev."""
        self.assertTrue(_HAS_PROMETHEUS)

    def test_all_metrics_defined(self):
        """All 11 metric objects should exist."""
        metrics = [
            DRS_LLM_CALLS, DRS_LLM_COST, DRS_LLM_LATENCY,
            DRS_TOKENS_IN, DRS_TOKENS_OUT,
            DRS_SECTIONS_COMPLETED, DRS_ITERATIONS,
            DRS_CSS_SCORE, DRS_BUDGET_SPENT,
            DRS_BUDGET_REMAINING_PCT, DRS_PIPELINE_DURATION,
        ]
        for m in metrics:
            self.assertIsNotNone(m)


class TestStubMetric(unittest.TestCase):
    """Verify stub metric is safely callable."""

    def test_stub_inc(self):
        s = _StubMetric()
        s.inc()
        s.inc(5)

    def test_stub_observe(self):
        s = _StubMetric()
        s.observe(1.5)

    def test_stub_set(self):
        s = _StubMetric()
        s.set(42)

    def test_stub_labels(self):
        s = _StubMetric()
        labeled = s.labels(foo="bar")
        self.assertIsInstance(labeled, _StubMetric)
        labeled.inc()


class TestObserveLLMCall(unittest.TestCase):
    """Test the observe_llm_call helper."""

    def test_observe_increments_counters(self):
        """observe_llm_call should not raise."""
        observe_llm_call(
            agent="writer",
            model="anthropic/claude-sonnet-4",
            preset="balanced",
            tokens_in=1000,
            tokens_out=500,
            cost_usd=0.005,
            latency_s=2.3,
        )

    def test_observe_without_latency(self):
        """Should work without latency parameter."""
        observe_llm_call(
            agent="planner",
            model="google/gemini-2.5-pro",
            preset="premium",
            tokens_in=2000,
            tokens_out=1000,
            cost_usd=0.01,
        )


class TestBudgetGauges(unittest.TestCase):
    """Test budget gauge updates."""

    def test_update_budget_gauge(self):
        update_budget_gauge("doc-123", spent=5.0, max_dollars=10.0)

    def test_update_budget_zero_max(self):
        """Should handle zero max_dollars without error."""
        update_budget_gauge("doc-456", spent=0.0, max_dollars=0.0)


class TestCSSScores(unittest.TestCase):
    """Test CSS score gauge updates."""

    def test_update_css_scores(self):
        update_css_scores(css_content=0.85, css_style=0.90, css_source=0.75)


class TestPrometheusCounterValues(unittest.TestCase):
    """Test that Prometheus counters actually accumulate values."""

    @unittest.skipUnless(_HAS_PROMETHEUS, "prometheus-client required")
    def test_counter_increment(self):
        """LLM call counter should increment."""
        label_set = DRS_LLM_CALLS.labels(
            agent="test_agent", model="test/model", preset="test",
        )
        before = label_set._value.get()
        observe_llm_call(
            agent="test_agent", model="test/model", preset="test",
            tokens_in=100, tokens_out=50, cost_usd=0.001,
        )
        after = label_set._value.get()
        self.assertGreater(after, before)

    @unittest.skipUnless(_HAS_PROMETHEUS, "prometheus-client required")
    def test_cost_counter_accumulates(self):
        """Cost counter should accumulate dollar amounts."""
        label_set = DRS_LLM_COST.labels(agent="cost_test", model="test/cost")
        before = label_set._value.get()
        observe_llm_call(
            agent="cost_test", model="test/cost", preset="economy",
            tokens_in=500, tokens_out=200, cost_usd=0.05,
        )
        after = label_set._value.get()
        self.assertAlmostEqual(after - before, 0.05, places=4)


class TestLLMClientMetricsIntegration(unittest.TestCase):
    """Test that LLMClient.call() has agent/preset parameters."""

    def test_call_signature_has_agent_and_preset(self):
        """call() should accept agent and preset kwargs."""
        import inspect
        from src.llm.client import LLMClient
        sig = inspect.signature(LLMClient.call)
        params = list(sig.parameters.keys())
        self.assertIn("agent", params)
        self.assertIn("preset", params)

    def test_call_unsupported_provider_raises(self):
        """call() should still raise ValueError for unknown providers."""
        from src.llm.client import LLMClient
        client = LLMClient()
        with self.assertRaises(ValueError):
            client.call(
                model="unsupported/model",
                messages=[],
                agent="test",
                preset="balanced",
            )


if __name__ == "__main__":
    unittest.main()
