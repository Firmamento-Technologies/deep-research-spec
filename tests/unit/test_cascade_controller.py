"""Tests for ModelCascadeController (BudgetMLAgent pattern)."""
import pytest
from src.budget.cascade_controller import ModelCascadeController, cascade_controller


class TestCascadeController:

    def test_base_model_returned_for_first_section(self):
        """Section 0 should always return base model."""
        model, rlm = cascade_controller.select_model(
            "writer", "economy", section_idx=0,
        )
        assert model == "qwen/qwen3.5-9b-instruct"
        assert rlm is False

    def test_no_escalation_when_css_high(self):
        """High CSS should not trigger escalation."""
        model, rlm = cascade_controller.select_model(
            "writer", "balanced", section_idx=1, prev_css=0.8,
        )
        assert model == "qwen/qwen3.5-35b-a3b"  # base balanced
        assert rlm is False

    def test_escalation_when_css_low(self):
        """Low CSS with sufficient budget should escalate."""
        model, rlm = cascade_controller.select_model(
            "writer", "balanced", section_idx=1,
            prev_css=0.3, budget_remaining=50.0,
        )
        assert model == "deepseek/deepseek-r1"  # escalated
        assert rlm is False

    def test_no_escalation_when_budget_low(self):
        """Low budget should prevent escalation even with low CSS."""
        model, rlm = cascade_controller.select_model(
            "writer", "balanced", section_idx=1,
            prev_css=0.3, budget_remaining=1.0,  # too low
        )
        assert model == "qwen/qwen3.5-35b-a3b"  # stays at base

    def test_rlm_mode_on_high_oscillation(self):
        """Oscillation > 2 should trigger RLM mode."""
        model, rlm = cascade_controller.select_model(
            "writer", "economy", section_idx=1,
            oscillation_count=3,
        )
        assert rlm is True

    def test_premium_writer_is_sonnet(self):
        """Premium writer should be Claude 3.7 Sonnet."""
        model, rlm = cascade_controller.select_model(
            "writer", "premium", section_idx=0,
        )
        assert model == "anthropic/claude-3.7-sonnet"

    def test_unknown_role_returns_default(self):
        """Unknown role should return a default model."""
        model, rlm = cascade_controller.select_model(
            "unknown_agent", "balanced", section_idx=0,
        )
        assert model == "qwen/qwen3.5-9b-instruct"
