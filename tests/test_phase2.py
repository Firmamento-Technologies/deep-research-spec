"""Tests for Phase 2: style profiles and Prometheus metrics integration."""
from __future__ import annotations

import unittest
from pathlib import Path


class TestStyleProfiles(unittest.TestCase):
    """Task 2.2: Verify style profile loading from config."""

    def test_config_file_exists(self):
        """style_profiles.yaml should exist."""
        config_path = Path(__file__).resolve().parents[1] / "config" / "style_profiles.yaml"
        self.assertTrue(config_path.exists(), f"Missing: {config_path}")

    def test_config_has_profiles(self):
        """Config should have at least 3 profiles."""
        import yaml
        config_path = Path(__file__).resolve().parents[1] / "config" / "style_profiles.yaml"
        with open(config_path) as f:
            profiles = yaml.safe_load(f)
        self.assertGreaterEqual(len(profiles), 3)
        for name in ("academic", "business", "technical"):
            self.assertIn(name, profiles)

    def test_each_profile_has_rules(self):
        """Each profile should have a rules list."""
        import yaml
        config_path = Path(__file__).resolve().parents[1] / "config" / "style_profiles.yaml"
        with open(config_path) as f:
            profiles = yaml.safe_load(f)
        for name, profile in profiles.items():
            self.assertIn("rules", profile, f"Profile '{name}' missing rules")
            self.assertGreater(len(profile["rules"]), 0, f"Profile '{name}' has no rules")

    def test_writer_loads_academic_profile(self):
        """Writer should load academic rules from config."""
        from src.graph.nodes.writer import _get_style_profile_rules
        result = _get_style_profile_rules("academic")
        self.assertIn("Style rules:", result)
        self.assertIn("Cite every", result)

    def test_writer_loads_business_profile(self):
        """Writer should load business rules from config."""
        from src.graph.nodes.writer import _get_style_profile_rules
        result = _get_style_profile_rules("business")
        self.assertIn("Executive summary", result)

    def test_writer_loads_technical_profile(self):
        """Writer should load technical rules from config."""
        from src.graph.nodes.writer import _get_style_profile_rules
        result = _get_style_profile_rules("technical")
        self.assertIn("Code examples", result)

    def test_writer_fallback_unknown_profile(self):
        """Unknown profile name should fallback to academic."""
        from src.graph.nodes.writer import _get_style_profile_rules
        result = _get_style_profile_rules("nonexistent_profile")
        # Falls back to academic
        self.assertIn("Style rules:", result)

    def test_writer_inline_rules_override(self):
        """Legacy inline rules dict should take precedence."""
        from src.graph.nodes.writer import _get_style_profile_rules
        result = _get_style_profile_rules({"rules": ["Custom rule A", "Custom rule B"]})
        self.assertIn("Custom rule A", result)

    def test_writer_fallback_no_config(self):
        """If config file missing, should return default."""
        from src.graph.nodes.writer import _get_style_profile_rules
        from unittest.mock import patch
        with patch("pathlib.Path.exists", return_value=False):
            result = _get_style_profile_rules("academic")
        self.assertEqual(result, "Follow academic writing conventions. Be precise and well-sourced.")


class TestPrometheusMetrics(unittest.TestCase):
    """Task 2.4: Verify metrics infrastructure."""

    def test_metrics_module_imports(self):
        """Observability metrics should import without error."""
        from src.observability import metrics
        self.assertTrue(hasattr(metrics, "DRS_LLM_CALLS"))

    def test_jury_pass_rate_metric_exists(self):
        """Jury pass rate metric should be available."""
        from src.observability.metrics import DRS_JURY_QUALITY
        self.assertIsNotNone(DRS_JURY_QUALITY)


if __name__ == "__main__":
    unittest.main()
