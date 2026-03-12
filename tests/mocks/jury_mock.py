"""Mock jury node for MVP — always approves (test/development only).

Previously located at ``src/graph/nodes/jury_mock.py`` (P12 fix: moved
here so the graph builder cannot auto-discover it as a production node).

Import in tests::

    from tests.mocks.jury_mock import jury_mock_node

Returns a fixed APPROVED verdict with mock CSS scores so the pipeline can
proceed to section_checkpoint without invoking the real jury (§8).

DO NOT import this module from production code.
"""
from __future__ import annotations


def jury_mock_node(state: dict) -> dict:
    """Mock approval for MVP pipeline.

    Returns:
        Partial state update with ``jury_verdicts`` and ``aggregator_verdict``.
    """
    return {
        "jury_verdicts": [
            {
                "judge_slot": "R1",
                "model": "mock",
                "dimension_scores": {},
                "pass_fail": True,
                "veto_category": None,
                "confidence": "high",
                "motivation": "[MOCK] Auto-approved for MVP",
                "failed_claims": [],
                "missing_evidence": [],
                "external_sources_consulted": [],
                "css_contribution": 0.85,
            }
        ],
        "aggregator_verdict": {
            "verdict_type": "APPROVED",
            "css_content": 0.85,
            "css_style": 0.85,
            "css_composite": 0.85,
            "dissenting_reasons": [],
            "best_elements": [],
        },
        "css_content_current": 0.85,
        "css_style_current": 0.85,
        "css_composite_current": 0.85,
    }
