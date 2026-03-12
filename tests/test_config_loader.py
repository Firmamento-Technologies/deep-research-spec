"""Tests for centralized configuration loader (Task 2.5)."""
from __future__ import annotations

import os
import unittest


class TestConfigLoader(unittest.TestCase):
    """Task 2.5: Verify config loader works correctly."""

    def test_config_singleton(self):
        """Config should be a singleton."""
        from src.config.loader import Config
        c1 = Config()
        c2 = Config()
        self.assertIs(c1, c2)

    def test_config_get_writer_temperature(self):
        """Should read nested config values."""
        from src.config.loader import config
        temp = config.get("writer.temperature")
        self.assertEqual(temp, 0.3)

    def test_config_get_with_default(self):
        """Should return default for missing keys."""
        from src.config.loader import config
        val = config.get("nonexistent.key", "fallback")
        self.assertEqual(val, "fallback")

    def test_config_get_deep_nested(self):
        """Should read deeply nested values."""
        from src.config.loader import config
        jury_size = config.get("budgets.economy.jury_size")
        self.assertEqual(jury_size, 1)

    def test_config_env_substitution(self):
        """${VAR:-default} should use default when var not set."""
        from src.config.loader import config
        env = config.get("system.environment")
        # If DRS_ENV not set, should be "development"
        expected = os.getenv("DRS_ENV", "development")
        self.assertEqual(env, expected)

    def test_config_raw_access(self):
        """raw property should return full dict."""
        from src.config.loader import config
        raw = config.raw
        self.assertIsInstance(raw, dict)
        self.assertIn("system", raw)
        self.assertIn("llm", raw)

    def test_config_system_yaml_exists(self):
        """config/system.yaml should exist in the project."""
        from pathlib import Path
        config_path = Path(__file__).resolve().parents[1] / "config" / "system.yaml"
        self.assertTrue(config_path.exists())

    def test_config_budgets_all_presets(self):
        """All three presets should be configured."""
        from src.config.loader import config
        for preset in ("economy", "balanced", "premium"):
            val = config.get(f"budgets.{preset}.jury_size")
            self.assertIsNotNone(val, f"Missing jury_size for '{preset}'")


if __name__ == "__main__":
    unittest.main()
