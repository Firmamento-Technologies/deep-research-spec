"""Tests for cost_usd() fallback behavior (FIX BUG #1.1)."""
import pytest
from src.llm.pricing import cost_usd, MODEL_PRICING


def test_known_model_returns_cost():
    """Known model should return non-zero cost."""
    result = cost_usd("openai/o3-mini", 1000, 1000)
    assert result > 0
    # o3-mini: (1000 * 1.10 + 1000 * 4.40) / 1_000_000 = 0.0055
    assert abs(result - 0.0055) < 0.0001


def test_unknown_model_returns_zero():
    """Unknown model should return 0.0 without crashing."""
    result = cost_usd("unknown/nonexistent-model", 1000, 1000)
    assert result == 0.0


def test_gpt45_price_is_150():
    """BUG #1: gpt-4.5 output must be $150/M, not $1.10/M."""
    p = MODEL_PRICING["openai/gpt-4.5"]
    assert p["out"] == 150.00


def test_qwen35_models_present():
    """Qwen 3.5 frontier models should be in MODEL_PRICING."""
    expected = [
        "qwen/qwen3.5-0.8b",
        "qwen/qwen3.5-2b",
        "qwen/qwen3.5-4b",
        "qwen/qwen3.5-9b-instruct",
        "qwen/qwen3.5-35b-a3b",
        "qwen/qwen3.5-flash",
        "qwen/qwen3.5-plus",
    ]
    for model in expected:
        assert model in MODEL_PRICING, f"Missing: {model}"
