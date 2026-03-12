"""Test SHINE adapter for LoRA generation from text corpus.

All tests mock SHINE since it requires GPU + the ``shine`` package.
Tests validate the fallback logic exhaustively.
"""

import pytest
from unittest.mock import patch, MagicMock

# We need to reset the module-level SHINE availability flag between tests
import src.graph.nodes.shine_adapter as shine_mod
from src.graph.nodes.shine_adapter import ShineAdapter, shine_adapter_node


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_state(**overrides) -> dict:
    """Build a minimal DocumentState dict for testing."""
    base = {
        "quality_preset": "Premium",
        "config": {"quality_preset": "Premium"},
        "outline": [{"idx": 0, "title": "Test", "scope": "Test scope", "target_words": 800}],
        "current_section_idx": 0,
        "current_iteration": 1,
        "synthesized_sources": "This is a test corpus about LoRA adapters and SHINE hypernetworks.",
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _reset_shine_flag():
    """Reset module-level SHINE availability between tests."""
    shine_mod._SHINE_AVAILABLE = None
    shine_mod._ShineHypernet = None
    yield
    shine_mod._SHINE_AVAILABLE = None
    shine_mod._ShineHypernet = None


# ── Tests ────────────────────────────────────────────────────────────────────

class TestShineAdapter:
    """Test suite for ShineAdapter node."""

    def test_fallback_when_shine_not_installed(self):
        """shine_active=False when SHINE package is not installed."""
        # _check_shine will fail with ImportError (shine not installed)
        result = shine_adapter_node(_make_state())
        assert result["shine_active"] is False

    def test_fallback_on_economy_preset(self):
        """SHINE skipped for Economy preset (budget §19)."""
        # Force SHINE as "available" to test the preset check
        shine_mod._SHINE_AVAILABLE = True
        shine_mod._ShineHypernet = MagicMock()

        state = _make_state(quality_preset="Economy")
        adapter = ShineAdapter()
        result = adapter.run(state)
        assert result["shine_active"] is False

    def test_fallback_on_economy_preset_from_config(self):
        """SHINE skipped when quality_preset is nested in config dict."""
        shine_mod._SHINE_AVAILABLE = True
        shine_mod._ShineHypernet = MagicMock()

        state = _make_state()
        del state["quality_preset"]
        state["config"]["quality_preset"] = "Economy"
        adapter = ShineAdapter()
        result = adapter.run(state)
        assert result["shine_active"] is False

    def test_fallback_on_small_section(self):
        """SHINE skipped for sections < 400 target words."""
        shine_mod._SHINE_AVAILABLE = True
        shine_mod._ShineHypernet = MagicMock()

        state = _make_state()
        state["outline"][0]["target_words"] = 200
        adapter = ShineAdapter()
        result = adapter.run(state)
        assert result["shine_active"] is False

    def test_fallback_on_retry_iteration(self):
        """SHINE skipped on iteration > 1."""
        shine_mod._SHINE_AVAILABLE = True
        shine_mod._ShineHypernet = MagicMock()

        state = _make_state(current_iteration=2)
        adapter = ShineAdapter()
        result = adapter.run(state)
        assert result["shine_active"] is False

    def test_fallback_on_empty_corpus(self):
        """SHINE skipped when corpus is empty."""
        shine_mod._SHINE_AVAILABLE = True
        shine_mod._ShineHypernet = MagicMock()

        state = _make_state(synthesized_sources="")
        adapter = ShineAdapter()
        result = adapter.run(state)
        assert result["shine_active"] is False

    def test_lora_generation_success(self):
        """Successful LoRA generation returns shine_active=True + lora."""
        mock_shine_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.generate_lora.return_value = {"weights": "fake_lora"}
        mock_shine_cls.return_value = mock_instance

        shine_mod._SHINE_AVAILABLE = True
        shine_mod._ShineHypernet = mock_shine_cls

        adapter = ShineAdapter()
        result = adapter.run(_make_state())

        assert result["shine_active"] is True
        assert result["shine_lora"] == {"weights": "fake_lora"}
        mock_instance.generate_lora.assert_called_once()

    def test_fallback_on_shine_runtime_error(self):
        """shine_active=False when SHINE.generate_lora raises."""
        mock_shine_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.generate_lora.side_effect = RuntimeError("GPU OOM")
        mock_shine_cls.return_value = mock_instance

        shine_mod._SHINE_AVAILABLE = True
        shine_mod._ShineHypernet = mock_shine_cls

        adapter = ShineAdapter()
        result = adapter.run(_make_state())
        assert result["shine_active"] is False

    def test_node_function_returns_dict(self):
        """shine_adapter_node() returns a dict."""
        result = shine_adapter_node(_make_state())
        assert isinstance(result, dict)
        assert "shine_active" in result

    def test_balanced_preset_allowed(self):
        """SHINE is allowed on Balanced preset (not just Premium)."""
        mock_shine_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.generate_lora.return_value = {"weights": "lora"}
        mock_shine_cls.return_value = mock_instance

        shine_mod._SHINE_AVAILABLE = True
        shine_mod._ShineHypernet = mock_shine_cls

        state = _make_state(quality_preset="Balanced")
        adapter = ShineAdapter()
        result = adapter.run(state)
        assert result["shine_active"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
