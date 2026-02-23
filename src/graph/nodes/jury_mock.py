"""Mock jury for MVP — always approves (temporary).

This is a placeholder for the full jury system (§8) that will be
implemented in Phase 2.  Returns a fixed APPROVED verdict with
mock CSS scores so the pipeline can proceed to section_checkpoint.
"""
from __future__ import annotations


def jury_mock_node(state: dict) -> dict:
    """Mock approval for MVP pipeline.

    Returns:
        Partial state update with jury_verdicts and aggregator_verdict.
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
