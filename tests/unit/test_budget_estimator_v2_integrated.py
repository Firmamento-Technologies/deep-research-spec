"""Tests for budget_estimator v2 — standalone (no graph import chain).

Uses sys.path manipulation to import budget_estimator without triggering
src.graph.__init__ which requires the full LangGraph pipeline.
"""
import sys
import os
import pytest

# Ensure the project root is in sys.path
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

# These imports work because they don't trigger src.graph.__init__
from src.llm.pricing import cost_usd, MODEL_PRICING


# Import estimate_run_cost function directly by executing the file
# without going through src.graph package init
import importlib.util as _ilu

def _load_budget_estimator():
    """Load budget_estimator.py without triggering full graph import chain."""
    # First ensure _presets is available
    presets_path = os.path.join(_root, "src", "graph", "_presets.py")
    spec = _ilu.spec_from_file_location("src.graph._presets", presets_path,
                                         submodule_search_locations=[])
    mod = _ilu.module_from_spec(spec)
    sys.modules["src.graph._presets"] = mod
    spec.loader.exec_module(mod)

    # Now load budget_estimator
    be_path = os.path.join(_root, "src", "graph", "nodes", "budget_estimator.py")
    mod_name = "src.graph.nodes.budget_estimator"
    spec2 = _ilu.spec_from_file_location(mod_name, be_path,
                                          submodule_search_locations=[])
    mod2 = _ilu.module_from_spec(spec2)
    sys.modules[mod_name] = mod2
    spec2.loader.exec_module(mod2)
    return mod2

_be = _load_budget_estimator()
estimate_run_cost = _be.estimate_run_cost
budget_estimator_node = _be.budget_estimator_node
BudgetEstimate = _be.BudgetEstimate
REGIME_PARAMS = _be.REGIME_PARAMS


class TestBugFixes:
    """Verify all 5 bugs are fixed."""

    def test_bug1_gpt45_cost_not_underestimated(self):
        est = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="balanced",
        )
        assert est.jury_cost_per_iter > 0.01

    def test_bug2_mow_writer_only(self):
        est_balanced = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="balanced",
        )
        est_economy = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="economy",
        )
        assert est_economy.writer_cost_per_iter <= est_balanced.writer_cost_per_iter

    def test_bug3_input_tokens_included(self):
        est = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="balanced",
        )
        assert est.reflector_cost_per_iter > 0

    def test_bug4_jury_size_per_regime(self):
        est_economy = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="economy",
        )
        est_premium = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="premium",
        )
        ratio = est_premium.jury_cost_per_iter / est_economy.jury_cost_per_iter
        assert abs(ratio - 3.0) < 0.1

    def test_bug5_avg_iter_clamped(self):
        est = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="economy", avg_iter=10.0,
        )
        assert est.estimated_total_usd < 100


class TestGapAndEnhancements:

    def test_gap6_planner_included(self):
        est = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="balanced",
        )
        assert est.planner_cost > 0

    def test_panel_contingency_balanced(self):
        est = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="balanced",
        )
        assert est.panel_contingency > 0

    def test_panel_contingency_zero_economy(self):
        est = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="economy",
        )
        assert est.panel_contingency == 0

    def test_rlm_reduces_total(self):
        est_normal = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="balanced",
        )
        est_rlm = estimate_run_cost(
            n_sections=8, target_words=8000, max_budget_usd=50.0,
            quality_preset="balanced", enable_rlm_offload=True,
        )
        assert est_rlm.estimated_total_usd < est_normal.estimated_total_usd
        assert est_rlm.compression_savings > 0


class TestNodeIntegration:

    def test_node_returns_budget_dict(self):
        state = {
            "outline": [{"title": f"Section {i}"} for i in range(8)],
            "budget": {"max_dollars": 50.0},
            "quality_preset": "balanced",
            "config": {"target_words": 8000},
        }
        result = budget_estimator_node(state)
        assert "budget" in result
        assert result["budget"]["estimated_total"] > 0
        assert result["budget"]["planner_cost"] > 0

    def test_node_warns_on_budget_exceeded(self):
        state = {
            "outline": [{"title": f"Section {i}"} for i in range(20)],
            "budget": {"max_dollars": 1.0},
            "quality_preset": "premium",
            "config": {"target_words": 20000},
        }
        result = budget_estimator_node(state)
        assert "budget_warning" in result["budget"]
