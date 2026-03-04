"""Unit tests for budget_estimator_v2.py

Validates all bug fixes from spec review 2026-03-04:
- BUG #1: gpt-4.5 cost correct ($150/M not $1.10/M)
- BUG #2: MoW amortization (2.1× not 1.4×)
- BUG #3: Input tokens included
- BUG #4: jury_size per regime (not hardcoded 9)
- BUG #5: avg_iter clamped to max_iterations
- GAP #6: Planner cost included
- SHINE: Panel contingency
- RLM: Compression savings
"""

import pytest
import sys
from pathlib import Path

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

from services.budget_estimator_v2 import (
    estimate_run_cost,
    BudgetEstimate,
    _derive_regime,
    get_regime_params,
    REGIME_PARAMS,
)


class TestRegimeDerivation:
    """Test regime auto-derivation from budget_per_word."""
    
    def test_economy_threshold(self):
        assert _derive_regime(0.0015) == "Economy"
        assert _derive_regime(0.0019) == "Economy"
    
    def test_balanced_threshold(self):
        assert _derive_regime(0.002) == "Balanced"
        assert _derive_regime(0.003) == "Balanced"
        assert _derive_regime(0.005) == "Balanced"
    
    def test_premium_threshold(self):
        assert _derive_regime(0.0051) == "Premium"
        assert _derive_regime(0.010) == "Premium"
    
    def test_regime_params_structure(self):
        """Validate REGIME_PARAMS matches spec §19.2."""
        for regime in ["Economy", "Balanced", "Premium"]:
            params = get_regime_params(regime)
            assert "css_threshold" in params
            assert "max_iterations" in params
            assert "jury_size" in params
            assert "mow_enabled" in params
        
        # Specific values per spec
        assert REGIME_PARAMS["Economy"]["max_iterations"] == 2
        assert REGIME_PARAMS["Economy"]["jury_size"] == 1
        assert REGIME_PARAMS["Balanced"]["max_iterations"] == 4
        assert REGIME_PARAMS["Balanced"]["jury_size"] == 2
        assert REGIME_PARAMS["Premium"]["max_iterations"] == 8
        assert REGIME_PARAMS["Premium"]["jury_size"] == 3


class TestBugFixes:
    """Regression tests for all identified bugs."""
    
    def test_bug_1_gpt45_cost_not_underestimated(self):
        """BUG #1: gpt-4.5 judge_s1 cost must reflect $150/M not $1.10/M."""
        estimate = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=10.0,
            quality_preset="Balanced",
            avg_iter=1.0,  # Single iter to isolate jury cost
        )
        
        # With jury_size=2, judge_s1 and judge_s2 are active
        # judge_s1 = gpt-4.5 @ $150/M out
        # For 600 output tokens (1000 words * 0.4): 600 * $150 / 1M = $0.09
        # judge_s2 = mistral @ $6/M out: 600 * $6 / 1M = $0.0036
        # Total jury should be significantly > $0.02 (old buggy estimate)
        
        assert estimate.jury_cost_per_iter > 0.10, (
            f"Jury cost {estimate.jury_cost_per_iter} too low, "
            f"gpt-4.5 likely still underestimated"
        )
    
    def test_bug_2_mow_multiplier_correct(self):
        """BUG #2: MoW multiplier should be ~2.1× on writer only, not 1.4× on all."""
        # Test with MoW enabled (Balanced)
        est_mow = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=20.0,
            quality_preset="Balanced",
            avg_iter=2.5,
        )
        
        # Test without MoW (Economy)
        est_no_mow = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=20.0,
            quality_preset="Economy",
            avg_iter=2.5,
        )
        
        # MoW factor = (3.75 + (2.5 - 1)) / 2.5 = 2.1
        # Writer cost should be ~2.1× higher in Balanced vs Economy
        ratio = est_mow.writer_cost_per_iter / est_no_mow.writer_cost_per_iter
        
        assert 2.0 < ratio < 2.3, (
            f"MoW multiplier ratio {ratio:.2f} outside expected range 2.0-2.3. "
            f"Should be ~2.1×, not 1.4× or 3.75×"
        )
    
    def test_bug_3_input_tokens_included(self):
        """BUG #3: Input tokens must be included for all agents."""
        estimate = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=10.0,
            quality_preset="Premium",
            avg_iter=1.0,
        )
        
        # Reflector: o3 @ $10/M in, $40/M out
        # tok_reflector_in = tok_judge_out * 5 = 600 * 5 = 3000
        # tok_reflector_out = 800
        # Cost = (3000 * 10 + 800 * 40) / 1M = $0.062
        # Old formula (output only): 800 * 40 / 1M = $0.032
        
        assert estimate.reflector_cost_per_iter > 0.055, (
            f"Reflector cost {estimate.reflector_cost_per_iter} too low, "
            f"input tokens likely not included"
        )
    
    def test_bug_4_jury_size_not_hardcoded(self):
        """BUG #4: Jury cost must scale with regime jury_size, not hardcoded * 9."""
        est_economy = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=5.0,
            quality_preset="Economy",
            avg_iter=1.0,
        )
        
        est_premium = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=20.0,
            quality_preset="Premium",
            avg_iter=1.0,
        )
        
        # Economy: jury_size=1 → 3 judges total (R1, F1, S1)
        # Premium: jury_size=3 → 9 judges total (R1-3, F1-3, S1-3)
        # Ratio should be ~3× (not 1× if hardcoded)
        
        ratio = est_premium.jury_cost_per_iter / est_economy.jury_cost_per_iter
        
        assert 2.5 < ratio < 3.5, (
            f"Jury cost ratio {ratio:.2f} between Premium/Economy should be ~3×, "
            f"indicating jury_size scaling. If ~1×, hardcoded * 9 bug present."
        )
    
    def test_bug_5_avg_iter_clamped(self):
        """BUG #5: avg_iter must not exceed regime max_iterations."""
        # Economy max_iterations = 2, force avg_iter = 2.5
        estimate = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=5.0,
            quality_preset="Economy",
            avg_iter=2.5,  # Should be clamped to 2.0
        )
        
        # If clamped correctly, cost should reflect max 2 iterations
        # Per-section cost = iter_cost * 2.0 (not * 2.5)
        # Verify by comparing to explicit avg_iter=2.0
        
        est_explicit = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=5.0,
            quality_preset="Economy",
            avg_iter=2.0,
        )
        
        assert abs(estimate.cost_per_section - est_explicit.cost_per_section) < 0.01, (
            f"avg_iter=2.5 was not clamped to max_iterations=2.0. "
            f"Cost {estimate.cost_per_section} != {est_explicit.cost_per_section}"
        )
    
    def test_gap_6_planner_cost_included(self):
        """GAP #6: Planner cost must be in total estimate."""
        estimate = estimate_run_cost(
            n_sections=8,
            target_words=8000,
            max_budget_usd=15.0,
            quality_preset="Balanced",
        )
        
        assert estimate.planner_cost > 0.03, (
            f"Planner cost {estimate.planner_cost} suspiciously low or missing"
        )
        
        # Planner: gemini-2.5-pro @ $1.25/M in, $10/M out
        # (2000 * 1.25 + 4096 * 10) / 1M ≈ $0.043
        assert 0.04 < estimate.planner_cost < 0.05, (
            f"Planner cost {estimate.planner_cost} outside expected range $0.04-$0.05"
        )


class TestSHINEAwareness:
    """Test Panel Discussion contingency integration."""
    
    def test_panel_contingency_in_balanced(self):
        estimate = estimate_run_cost(
            n_sections=8,
            target_words=8000,
            max_budget_usd=15.0,
            quality_preset="Balanced",
        )
        
        # Panel: 40% prob, 2 rounds max, tier-1 jury
        # Should be non-zero and < 20% of total
        assert estimate.panel_contingency > 0.5, "Panel contingency missing"
        assert estimate.panel_contingency < estimate.estimated_total_usd * 0.2, (
            "Panel contingency unrealistically high"
        )
    
    def test_panel_zero_in_economy(self):
        estimate = estimate_run_cost(
            n_sections=8,
            target_words=8000,
            max_budget_usd=5.0,
            quality_preset="Economy",
        )
        
        # Economy: no Panel Discussion per spec
        assert estimate.panel_contingency == 0.0, (
            "Panel contingency should be 0 in Economy regime"
        )


class TestRLMAwareness:
    """Test RLM context offload calculations."""
    
    def test_rlm_compression_savings(self):
        est_standard = estimate_run_cost(
            n_sections=8,
            target_words=8000,
            max_budget_usd=15.0,
            quality_preset="Balanced",
            enable_rlm_offload=False,
        )
        
        est_rlm = estimate_run_cost(
            n_sections=8,
            target_words=8000,
            max_budget_usd=15.0,
            quality_preset="Balanced",
            enable_rlm_offload=True,
        )
        
        # RLM should reduce total cost via compression
        assert est_rlm.estimated_total_usd < est_standard.estimated_total_usd, (
            "RLM mode should reduce total cost via compression savings"
        )
        
        assert est_rlm.compression_savings > 0.0, (
            "RLM compression_savings should be > 0"
        )
        
        # But reflector cost increases (recursive overhead)
        assert est_rlm.reflector_cost_per_iter > est_standard.reflector_cost_per_iter, (
            "RLM should increase reflector cost (1.3× overhead)"
        )
    
    def test_rlm_recursive_factor(self):
        estimate = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=10.0,
            enable_rlm_offload=True,
        )
        
        assert estimate.recursive_call_factor == 1.3, (
            f"RLM recursive_call_factor should be 1.3, got {estimate.recursive_call_factor}"
        )


class TestGoldenSetComparison:
    """Compare against golden values from spec review."""
    
    def test_8_sections_balanced_regime(self):
        """Golden test case from review: 8 sec × 1k words, Balanced."""
        estimate = estimate_run_cost(
            n_sections=8,
            target_words=8000,
            max_budget_usd=15.0,
            quality_preset="Balanced",
            avg_iter=2.5,
        )
        
        # Expected from review (after all fixes): ~$11.80 - $13.50
        assert 11.5 < estimate.estimated_total_usd < 14.0, (
            f"Golden test failed: expected $11.80-$13.50, got ${estimate.estimated_total_usd:.2f}"
        )
        
        assert estimate.regime == "Balanced"
        assert not estimate.blocked  # Should pass 80% threshold at $15 cap
    
    def test_blocking_threshold(self):
        """Test 80% blocking logic."""
        # Force a high-cost scenario
        estimate = estimate_run_cost(
            n_sections=20,
            target_words=20000,
            max_budget_usd=10.0,  # Intentionally too low
            quality_preset="Premium",
        )
        
        assert estimate.blocked, "Should block when estimate > 80% of max_budget"
        assert estimate.block_reason is not None
        assert "80% cap" in estimate.block_reason


class TestEdgeCases:
    """Test boundary conditions and error handling."""
    
    def test_minimum_sections(self):
        estimate = estimate_run_cost(
            n_sections=1,
            target_words=1000,
            max_budget_usd=5.0,
        )
        assert estimate.estimated_total_usd > 0.0
    
    def test_zero_sections_raises(self):
        with pytest.raises(ValueError, match="n_sections must be > 0"):
            estimate_run_cost(
                n_sections=0,
                target_words=1000,
                max_budget_usd=10.0,
            )
    
    def test_zero_budget_raises(self):
        with pytest.raises(ValueError, match="max_budget_usd must be > 0"):
            estimate_run_cost(
                n_sections=5,
                target_words=5000,
                max_budget_usd=0.0,
            )
    
    def test_tiny_word_count_raises(self):
        with pytest.raises(ValueError, match="target_words must be >= 1000"):
            estimate_run_cost(
                n_sections=5,
                target_words=500,
                max_budget_usd=10.0,
            )
    
    def test_large_document(self):
        """50k word document should not crash or produce absurd costs."""
        estimate = estimate_run_cost(
            n_sections=50,
            target_words=50000,
            max_budget_usd=500.0,
            quality_preset="Premium",
        )
        
        assert estimate.estimated_total_usd < 500.0, (
            "50k word Premium doc should stay under $500 cap"
        )
        assert estimate.estimated_total_usd > 100.0, (
            "50k word Premium doc cost suspiciously low"
        )


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--color=yes",
    ])
