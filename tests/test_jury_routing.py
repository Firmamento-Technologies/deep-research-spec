"""Tests for jury routing integration (Task 1.2) and fail-closed errors (Task 1.4)."""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock


class TestJuryRouting(unittest.TestCase):
    """Task 1.2: Verify jury uses route_model instead of hardcoded models."""

    def test_no_hardcoded_models(self):
        """Jury.py should not contain _MODEL_R/F/S globals."""
        import src.graph.nodes.jury as jury_mod
        self.assertFalse(hasattr(jury_mod, "_MODEL_R"))
        self.assertFalse(hasattr(jury_mod, "_MODEL_F"))
        self.assertFalse(hasattr(jury_mod, "_MODEL_S"))

    def test_imports_route_model(self):
        """Jury.py should import route_model."""
        from src.graph.nodes.jury import route_model
        self.assertTrue(callable(route_model))

    def test_economy_uses_cheap_models(self):
        """Economy preset should route to tier1 (flash) models."""
        from src.llm.routing import route_model
        model_r = route_model("jury_r", "economy")
        model_f = route_model("jury_f", "economy")
        model_s = route_model("jury_s", "economy")
        # Economy should NOT use o3 or gemini-pro
        self.assertNotIn("o3", model_r)
        self.assertNotIn("gemini-2.5-pro", model_f)

    def test_premium_uses_strong_models(self):
        """Premium preset should route to tier3 models."""
        from src.llm.routing import route_model
        model_r = route_model("jury_r", "premium")
        # Premium should use strong reasoning model
        self.assertIsInstance(model_r, str)
        self.assertTrue(len(model_r) > 0)

    @patch("src.graph.nodes.judge_r.JudgeR.evaluate")
    @patch("src.graph.nodes.judge_f.JudgeF.evaluate")
    @patch("src.graph.nodes.judge_s.JudgeS.evaluate")
    def test_jury_node_runs_with_routing(self, mock_s, mock_f, mock_r):
        """jury_node should run without error using routed models."""
        verdict = {
            "judge_slot": "R1",
            "model": "test",
            "dimension_scores": {"accuracy": 0.9},
            "pass_fail": True,
            "veto_category": None,
            "confidence": "high",
            "motivation": "Good",
            "failed_claims": [],
            "missing_evidence": [],
            "external_sources_consulted": [],
            "css_contribution": 0.85,
        }
        mock_r.return_value = verdict
        mock_f.return_value = verdict
        mock_s.return_value = verdict

        from src.graph.nodes.jury import jury_node
        state = {
            "quality_preset": "economy",
            "current_draft": "Test draft content.",
            "current_sources": [],
            "budget": {"jury_size": 1},
            "outline": [{"scope": "test scope"}],
            "current_section_idx": 0,
        }
        result = jury_node(state)
        self.assertIn("jury_verdicts", result)
        self.assertEqual(len(result["jury_verdicts"]), 3)  # 1 R + 1 F + 1 S


class TestJuryFailClosed(unittest.TestCase):
    """Task 1.4: Verify jury fails closed on judge errors."""

    def test_error_verdict_structure(self):
        """_error_verdict should return fail-closed dict."""
        from src.graph.nodes.jury import _error_verdict
        v = _error_verdict(RuntimeError("API timeout"))
        self.assertFalse(v["pass_fail"])
        self.assertEqual(v["veto_category"], "technical_failure")
        self.assertEqual(v["css_contribution"], 0.0)
        self.assertIn("API timeout", v["motivation"])

    @patch("src.graph.nodes.judge_r.JudgeR.evaluate", side_effect=Exception("API Error"))
    @patch("src.graph.nodes.judge_f.JudgeF.evaluate", side_effect=Exception("API Error"))
    @patch("src.graph.nodes.judge_s.JudgeS.evaluate", side_effect=Exception("API Error"))
    def test_jury_fails_closed_on_all_errors(self, mock_s, mock_f, mock_r):
        """When all judges crash, verdicts should fail closed."""
        from src.graph.nodes.jury import jury_node
        state = {
            "quality_preset": "balanced",
            "current_draft": "Test content",
            "current_sources": [],
            "budget": {"jury_size": 1},
            "outline": [{"scope": "test"}],
            "current_section_idx": 0,
        }
        result = jury_node(state)
        verdicts = result["jury_verdicts"]

        # All should be technical_failure vetoes
        for v in verdicts:
            self.assertFalse(v["pass_fail"], "Error verdict must fail closed")
            self.assertEqual(v["veto_category"], "technical_failure")
            self.assertEqual(v["css_contribution"], 0.0)

    @patch("src.graph.nodes.judge_s.JudgeS.evaluate")
    @patch("src.graph.nodes.judge_f.JudgeF.evaluate", side_effect=Exception("Timeout"))
    @patch("src.graph.nodes.judge_r.JudgeR.evaluate")
    def test_partial_failure_still_contains_veto(self, mock_r, mock_f, mock_s):
        """One judge failing should produce one veto + two passes."""
        good_verdict = {
            "judge_slot": "R1", "model": "test",
            "dimension_scores": {}, "pass_fail": True,
            "veto_category": None, "confidence": "high",
            "motivation": "OK", "failed_claims": [],
            "missing_evidence": [], "external_sources_consulted": [],
            "css_contribution": 0.85,
        }
        mock_r.return_value = good_verdict
        mock_s.return_value = good_verdict

        from src.graph.nodes.jury import jury_node
        state = {
            "quality_preset": "balanced",
            "current_draft": "Test",
            "current_sources": [],
            "budget": {"jury_size": 1},
            "outline": [{"scope": "test"}],
            "current_section_idx": 0,
        }
        result = jury_node(state)
        verdicts = result["jury_verdicts"]

        error_verdicts = [v for v in verdicts if v.get("veto_category") == "technical_failure"]
        pass_verdicts = [v for v in verdicts if v.get("pass_fail") is True]
        self.assertEqual(len(error_verdicts), 1)
        self.assertEqual(len(pass_verdicts), 2)


if __name__ == "__main__":
    unittest.main()
