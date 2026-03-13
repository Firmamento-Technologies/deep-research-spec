"""Await Human node — human review gate for escalations.

Triggered when:
- Reflector scope is FULL (argument structurally broken)
- Oscillation detected (revision loop)
- Budget hard stop
- Coherence hard conflict
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def await_human_node(state: dict) -> dict:
    """Gate for human intervention on escalated issues.

    In automated mode, applies best-effort resolution.
    In interactive mode, sets flag for external polling.

    Returns:
        Partial state with resolution metadata.
    """
    config = state.get("config", {})
    auto_resolve = config.get("auto_resolve_escalations", True)
    section_idx = state.get("current_section_idx", 0)

    # Determine escalation reason
    reason = _determine_reason(state)

    logger.warning(
        "AwaitHuman: escalation for section %d — reason: %s",
        section_idx, reason,
    )

    if auto_resolve:
        # In automated mode, force-approve and continue
        logger.warning(
            "AwaitHuman: auto-resolving escalation (auto_resolve=True)"
        )
        return {
            "force_approve": True,
            "human_review_pending": None,
            "escalation_log": state.get("escalation_log", []) + [{
                "section_idx": section_idx,
                "reason": reason,
                "resolution": "auto_force_approve",
            }],
        }

    # In interactive mode, pause for human
    return {
        "human_review_pending": reason,
        "active_escalation": {
            "section_idx": section_idx,
            "reason": reason,
            "requires": "human_decision",
        },
    }


def _determine_reason(state: dict) -> str:
    """Determine why we escalated to human."""
    if state.get("oscillation_detected"):
        osc_type = state.get("oscillation_type", "unknown")
        return f"oscillation_{osc_type}"

    ro = state.get("reflector_output") or {}
    if isinstance(ro, dict) and ro.get("dominant_scope") == "FULL":
        return "structural_rewrite_needed"

    conflicts = state.get("coherence_conflicts") or []
    hard = [c for c in conflicts if isinstance(c, dict) and c.get("level") == "HARD"]
    if hard:
        return f"coherence_hard_conflict ({len(hard)} conflicts)"

    budget = state.get("budget") or {}
    if isinstance(budget, dict) and budget.get("hard_stop_fired"):
        return "budget_exhausted"

    # PostQA failure — QA routed here due to high-severity issues
    qa_issues = state.get("qa_issues") or []
    if qa_issues:
        high = [i for i in qa_issues if isinstance(i, dict) and i.get("severity") == "high"]
        if high:
            return f"post_qa_failure ({len(high)} high-severity issues)"

    return "unknown_escalation"
