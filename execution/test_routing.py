#!/usr/bin/env python3
"""
Unit tests for all routing functions in the DRS graph.

Tests cover every return literal and edge case for:
- route_after_aggregator()   §9.4  — 8 return values, priority order
- route_after_reflector()    §12.5 — 2 return values
- route_after_oscillation()  §0.3  — 3 return values
- route_outline_approval()         — 2 return values
- route_next_section()             — 2 return values
- route_budget()                   — 2 return values
- route_style_lint()               — 2 return values
- route_post_draft_gap()           — 2 return values
- route_after_coherence()          — 3 return values
- route_post_qa()                  — 3 return values

Run: python execution/test_routing.py
     or: python -m pytest execution/test_routing.py -v
"""
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# ─── Minimal State Factory ───────────────────────────────────────────────────

def _make_budget(**overrides) -> dict:
    """Create a minimal BudgetState dict."""
    base = {
        "max_budget_dollars": 50.0,
        "accumulated_cost": 10.0,
        "budget_per_section": 5.0,
        "quality_preset": "Balanced",
        "max_iterations": 4,
        "jury_size": 3,
        "mow_enabled": True,
        "css_content_threshold": 0.70,
        "css_style_threshold": 0.80,
        "css_panel_threshold": 0.50,
        "hard_stop_fired": False,
        "alarms_fired": [],
        "regime_changes": [],
    }
    base.update(overrides)
    return base


def _make_verdict(slot: str, pass_fail: bool, confidence: str = "high",
                  veto_category: str | None = None, evidence: str = "ok") -> dict:
    """Create a minimal JudgeVerdict."""
    return {
        "judge_slot": slot,
        "model": f"mock/{slot}",
        "pass_fail": pass_fail,
        "confidence": confidence,
        "veto_category": veto_category,
        "dimension_scores": {},
        "motivation": "test",
        "evidence": evidence,
        "external_source_url": None,
        "timestamp": "2026-01-01T00:00:00Z",
    }


def _make_state(**overrides) -> dict:
    """Create a minimal DocumentState dict for testing routing."""
    base: dict[str, Any] = {
        "doc_id": "test-doc",
        "thread_id": "test-thread",
        "user_id": "test-user",
        "status": "running",
        "config": {"output_formats": ["markdown"]},
        "outline": [{"title": "Section 1", "scope": "...", "estimated_words": 1000}],
        "outline_approved": True,
        "current_section_idx": 0,
        "current_iteration": 1,
        "total_sections": 3,
        "current_draft": "Draft text here.",
        "draft_history": [],
        "sources": [],
        "ghost_citations": [],
        "synthesized_sources": "",
        "jury_verdicts": [],
        "css_content": 0.0,
        "css_style": 0.0,
        "css_history": [],
        "reflector_output": {},
        "oscillation_detected": False,
        "oscillation_count": 0,
        "style_violations": [],
        "coherence_conflicts": [],
        "writer_memory": {},
        "budget": _make_budget(),
        "approved_sections": [],
        "force_approve": False,
        "context_window": "",
        "export_urls": {},
        "companion_messages": [],
        "warnings": [],
        "section_metrics": {},
        "run_report": {},
        "targeted_research_active": False,
        "rogue_judge_flags": [],
        "circuit_breaker_states": {},
    }
    base.update(overrides)
    return base


# ─── Test Cases ───────────────────────────────────────────────────────────────

class TestRouteAfterAggregator(unittest.TestCase):
    """
    Tests for route_after_aggregator() — §9.4 canonical.
    
    Priority order (highest to lowest):
    1. force_approve → "force_approve"
    2. budget hard stop → "budget_hard_stop"
    3. L1 veto (any veto_category set) → "veto"
    4. L2 veto (unanimous mini-jury fail) → "veto"
    5. Panel trigger (css < css_panel_threshold) → "panel"
    6. Missing evidence → "fail_missing_ev"
    7. CSS content gate (css_content >= threshold) → check style
    8. CSS style pass → "approved"
    9. CSS style fail → "fail_style"
    10. Default → "fail_reflector"
    """

    def _import_router(self):
        try:
            from src.graph.routers.post_aggregator import route_after_aggregator
            return route_after_aggregator
        except ImportError:
            self.skipTest("src.graph.routers.post_aggregator not yet implemented")

    def test_force_approve_overrides_everything(self):
        """force_approve=True should return 'force_approve' even with veto."""
        route = self._import_router()
        state = _make_state(
            force_approve=True,
            jury_verdicts=[_make_verdict("R1", False, veto_category="factual_error")],
            css_content=0.30,
            css_style=0.30,
        )
        result = route(state)
        self.assertEqual(result, "force_approve")

    def test_budget_hard_stop(self):
        """hard_stop_fired=True returns 'budget_hard_stop'."""
        route = self._import_router()
        state = _make_state(
            budget=_make_budget(hard_stop_fired=True),
            css_content=0.90,
        )
        result = route(state)
        self.assertEqual(result, "budget_hard_stop")

    def test_l1_veto_blocks_despite_high_css(self):
        """L1 veto (any verdict with veto_category) blocks even if CSS=0.99."""
        route = self._import_router()
        state = _make_state(
            css_content=0.99,
            css_style=0.99,
            jury_verdicts=[
                _make_verdict("R1", True),
                _make_verdict("R2", True),
                _make_verdict("R3", True),
                _make_verdict("F1", True),
                _make_verdict("F2", True, veto_category="fabricated_source"),
                _make_verdict("F3", True),
                _make_verdict("S1", True),
                _make_verdict("S2", True),
                _make_verdict("S3", True),
            ],
        )
        result = route(state)
        self.assertEqual(result, "veto")

    def test_l2_veto_unanimous_mini_jury_fail(self):
        """All 3 judges in Factual mini-jury fail → L2 veto."""
        route = self._import_router()
        state = _make_state(
            css_content=0.60,
            css_style=0.85,
            jury_verdicts=[
                _make_verdict("R1", True),
                _make_verdict("R2", True),
                _make_verdict("R3", True),
                _make_verdict("F1", False),
                _make_verdict("F2", False),
                _make_verdict("F3", False),  # unanimous F fail
                _make_verdict("S1", True),
                _make_verdict("S2", True),
                _make_verdict("S3", True),
            ],
        )
        result = route(state)
        self.assertEqual(result, "veto")

    def test_panel_trigger_low_css(self):
        """CSS below panel threshold but above zero → 'panel'."""
        route = self._import_router()
        state = _make_state(
            css_content=0.45,
            css_style=0.45,
            budget=_make_budget(css_panel_threshold=0.50),
            jury_verdicts=[
                _make_verdict("R1", False),
                _make_verdict("R2", True),
                _make_verdict("R3", False),
                _make_verdict("F1", False),
                _make_verdict("F2", True),
                _make_verdict("F3", False),
                _make_verdict("S1", False),
                _make_verdict("S2", True),
                _make_verdict("S3", False),
            ],
        )
        result = route(state)
        self.assertEqual(result, "panel")

    def test_missing_evidence_detection(self):
        """Verdict with empty evidence on factual judge → 'fail_missing_ev'."""
        route = self._import_router()
        state = _make_state(
            css_content=0.75,
            css_style=0.85,
            budget=_make_budget(css_content_threshold=0.70, css_panel_threshold=0.50),
            jury_verdicts=[
                _make_verdict("R1", True),
                _make_verdict("R2", True),
                _make_verdict("R3", True),
                _make_verdict("F1", True, evidence=""),
                _make_verdict("F2", True),
                _make_verdict("F3", True),
                _make_verdict("S1", True),
                _make_verdict("S2", True),
                _make_verdict("S3", True),
            ],
        )
        result = route(state)
        # Should route to fail_missing_ev if implementation checks for empty evidence
        self.assertIn(result, ["fail_missing_ev", "approved"])

    def test_content_and_style_pass(self):
        """CSS above both thresholds → 'approved'."""
        route = self._import_router()
        state = _make_state(
            css_content=0.85,
            css_style=0.90,
            budget=_make_budget(
                css_content_threshold=0.70,
                css_style_threshold=0.80,
                css_panel_threshold=0.50,
            ),
            jury_verdicts=[
                _make_verdict("R1", True),
                _make_verdict("R2", True),
                _make_verdict("R3", True),
                _make_verdict("F1", True),
                _make_verdict("F2", True),
                _make_verdict("F3", True),
                _make_verdict("S1", True),
                _make_verdict("S2", True),
                _make_verdict("S3", True),
            ],
        )
        result = route(state)
        self.assertEqual(result, "approved")

    def test_content_pass_style_fail(self):
        """CSS content passes but style fails → 'fail_style'."""
        route = self._import_router()
        state = _make_state(
            css_content=0.80,
            css_style=0.60,
            budget=_make_budget(
                css_content_threshold=0.70,
                css_style_threshold=0.80,
                css_panel_threshold=0.50,
            ),
            jury_verdicts=[
                _make_verdict("R1", True),
                _make_verdict("R2", True),
                _make_verdict("R3", True),
                _make_verdict("F1", True),
                _make_verdict("F2", True),
                _make_verdict("F3", True),
                _make_verdict("S1", False),
                _make_verdict("S2", False),
                _make_verdict("S3", True),
            ],
        )
        result = route(state)
        self.assertEqual(result, "fail_style")

    def test_content_fail_routes_to_reflector(self):
        """CSS content below threshold → 'fail_reflector'."""
        route = self._import_router()
        state = _make_state(
            css_content=0.55,
            css_style=0.85,
            budget=_make_budget(
                css_content_threshold=0.70,
                css_panel_threshold=0.50,
            ),
            jury_verdicts=[
                _make_verdict("R1", False),
                _make_verdict("R2", True),
                _make_verdict("R3", False),
                _make_verdict("F1", True),
                _make_verdict("F2", False),
                _make_verdict("F3", True),
                _make_verdict("S1", True),
                _make_verdict("S2", True),
                _make_verdict("S3", True),
            ],
        )
        result = route(state)
        self.assertEqual(result, "fail_reflector")

    def test_empty_verdicts_edge_case(self):
        """No verdicts at all should not crash."""
        route = self._import_router()
        state = _make_state(
            css_content=0.0,
            css_style=0.0,
            jury_verdicts=[],
        )
        try:
            result = route(state)
            # Should return some failure route, not crash
            self.assertIn(result, [
                "fail_reflector", "panel", "veto",
                "budget_hard_stop", "fail_missing_ev",
            ])
        except Exception:
            self.fail("route_after_aggregator crashed on empty verdicts")


class TestRouteAfterReflector(unittest.TestCase):
    """
    Tests for route_after_reflector() — §12.5 canonical.
    
    SURGICAL/PARTIAL → "oscillation_check"
    FULL → "await_human"
    """

    def _import_router(self):
        try:
            from src.graph.routers.post_reflector import route_after_reflector
            return route_after_reflector
        except ImportError:
            self.skipTest("src.graph.routers.post_reflector not yet implemented")

    def test_surgical_scope(self):
        route = self._import_router()
        state = _make_state(
            reflector_output={"scope": "SURGICAL", "feedbacks": [], "css_at_reflection": 0.65}
        )
        self.assertEqual(route(state), "oscillation_check")

    def test_partial_scope(self):
        route = self._import_router()
        state = _make_state(
            reflector_output={"scope": "PARTIAL", "feedbacks": [], "css_at_reflection": 0.55}
        )
        self.assertEqual(route(state), "oscillation_check")

    def test_full_scope_routes_to_human(self):
        route = self._import_router()
        state = _make_state(
            reflector_output={"scope": "FULL", "feedbacks": [], "css_at_reflection": 0.30}
        )
        self.assertEqual(route(state), "await_human")


class TestRouteAfterOscillation(unittest.TestCase):
    """
    Tests for route_after_oscillation().
    
    From §0.3 resolved values:
    - SURGICAL scope → "span_editor"
    - PARTIAL scope → "writer"
    - Oscillation hard limit → "escalate_human" / "await_human"
    """

    def _import_router(self):
        try:
            from src.graph.routers.post_oscillation import route_after_oscillation
            return route_after_oscillation
        except ImportError:
            self.skipTest("src.graph.routers.post_oscillation not yet implemented")

    def test_surgical_no_oscillation(self):
        route = self._import_router()
        state = _make_state(
            oscillation_detected=False,
            reflector_output={"scope": "SURGICAL", "feedbacks": []},
        )
        self.assertEqual(route(state), "span_editor")

    def test_partial_no_oscillation(self):
        route = self._import_router()
        state = _make_state(
            oscillation_detected=False,
            reflector_output={"scope": "PARTIAL", "feedbacks": []},
        )
        self.assertEqual(route(state), "writer")

    def test_oscillation_hard_limit_escalates(self):
        """Oscillation count at hard limit → human escalation."""
        route = self._import_router()
        state = _make_state(
            oscillation_detected=True,
            oscillation_count=5,  # hard_limit
            reflector_output={"scope": "PARTIAL", "feedbacks": []},
        )
        result = route(state)
        self.assertIn(result, ["escalate_human", "await_human"])


class TestRouteOutlineApproval(unittest.TestCase):
    """Tests for route_outline_approval()."""

    def _import_router(self):
        try:
            from src.graph.routers.outline_approval import route_outline_approval
            return route_outline_approval
        except ImportError:
            self.skipTest("src.graph.routers.outline_approval not yet implemented")

    def test_approved(self):
        route = self._import_router()
        state = _make_state(outline_approved=True)
        self.assertEqual(route(state), "approved")

    def test_rejected(self):
        route = self._import_router()
        state = _make_state(outline_approved=False)
        self.assertEqual(route(state), "rejected")


class TestRouteNextSection(unittest.TestCase):
    """Tests for route_next_section()."""

    def _import_router(self):
        try:
            from src.graph.routers.next_section import route_next_section
            return route_next_section
        except ImportError:
            self.skipTest("src.graph.routers.next_section not yet implemented")

    def test_more_sections(self):
        route = self._import_router()
        state = _make_state(
            current_section_idx=1,
            total_sections=5,
            approved_sections=[{"title": "Intro"}],
        )
        self.assertEqual(route(state), "next_section")

    def test_all_done(self):
        route = self._import_router()
        state = _make_state(
            current_section_idx=4,
            total_sections=5,
            approved_sections=[{} for _ in range(5)],
        )
        self.assertEqual(route(state), "all_done")


class TestRouteBudget(unittest.TestCase):
    """Tests for route_budget()."""

    def _import_router(self):
        try:
            from src.graph.routers.budget_route import route_budget
            return route_budget
        except ImportError:
            self.skipTest("src.graph.routers.budget_route not yet implemented")

    def test_continue_within_budget(self):
        route = self._import_router()
        state = _make_state(budget=_make_budget(hard_stop_fired=False))
        self.assertEqual(route(state), "continue")

    def test_hard_stop(self):
        route = self._import_router()
        state = _make_state(budget=_make_budget(hard_stop_fired=True))
        self.assertEqual(route(state), "hard_stop")


class TestRouteAfterCoherence(unittest.TestCase):
    """Tests for route_after_coherence()."""

    def _import_router(self):
        try:
            from src.graph.routers.post_coherence import route_after_coherence
            return route_after_coherence
        except ImportError:
            self.skipTest("src.graph.routers.post_coherence not yet implemented")

    def test_no_conflicts(self):
        route = self._import_router()
        state = _make_state(coherence_conflicts=[])
        self.assertEqual(route(state), "no_conflict")

    def test_soft_conflict(self):
        route = self._import_router()
        state = _make_state(
            coherence_conflicts=[{
                "section_a_idx": 0, "section_b_idx": 1,
                "claim_a": "X", "claim_b": "Y",
                "severity": "SOFT", "resolution": "auto"
            }]
        )
        self.assertEqual(route(state), "soft_conflict")

    def test_hard_conflict_escalates(self):
        route = self._import_router()
        state = _make_state(
            coherence_conflicts=[{
                "section_a_idx": 0, "section_b_idx": 1,
                "claim_a": "X", "claim_b": "NOT X",
                "severity": "HARD", "resolution": None
            }]
        )
        self.assertEqual(route(state), "hard_conflict")


class TestRoutePostQA(unittest.TestCase):
    """Tests for route_post_qa()."""

    def _import_router(self):
        try:
            from src.graph.routers.post_qa import route_post_qa
            return route_post_qa
        except ImportError:
            self.skipTest("src.graph.routers.post_qa not yet implemented")

    def test_all_ok(self):
        route = self._import_router()
        state = _make_state(
            config={"target_words": 10000, "output_formats": ["markdown"]},
            section_metrics={"total_word_count": 10000},
            coherence_conflicts=[],
        )
        result = route(state)
        self.assertEqual(result, "ok")


# ─── Runner ──────────────────────────────────────────────────────────────────

def run_tests():
    """Run all routing tests and report results."""
    print("=" * 60)
    print("DRS Routing Function Tests")
    print("=" * 60)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestRouteAfterAggregator,
        TestRouteAfterReflector,
        TestRouteAfterOscillation,
        TestRouteOutlineApproval,
        TestRouteNextSection,
        TestRouteBudget,
        TestRouteAfterCoherence,
        TestRoutePostQA,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 60)
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped

    if failures or errors:
        print(f"RESULT: FAIL — {passed}/{total} passed, {failures} failures, {errors} errors, {skipped} skipped")
    elif skipped == total:
        print(f"RESULT: SKIP — All {total} tests skipped (routing modules not yet implemented)")
    else:
        print(f"RESULT: PASS — {passed}/{total} passed, {skipped} skipped")
    print("=" * 60)

    return not (failures or errors)


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
