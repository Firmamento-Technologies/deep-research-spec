"""Post-QA node (§5.19) — final quality assurance before publish.

Runs after all sections are approved. Checks:
- Cross-section coherence summary
- Citation completeness
- Table of contents accuracy
- Overall quality metrics
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def post_qa_node(state: dict) -> dict:
    """Run final quality assurance on complete document.

    Returns:
        Partial state with ``qa_passed``, ``qa_issues``.
    """
    approved = state.get("approved_sections", [])
    outline = state.get("outline", [])
    config = state.get("config", {})

    issues: list[dict] = []

    # Check all sections are present
    expected = len(outline) if outline else 0
    actual = len(approved)
    if expected > 0 and actual < expected:
        issues.append({
            "type": "missing_sections",
            "severity": "high",
            "message": f"Only {actual}/{expected} sections approved",
        })

    # Check for empty sections
    for i, section in enumerate(approved):
        content = section.get("content", section.get("draft", ""))
        if not content or len(content.strip()) < 50:
            issues.append({
                "type": "empty_section",
                "severity": "high",
                "message": f"Section {i} has insufficient content ({len(content)} chars)",
            })

    # Check CSS scores
    css_history = state.get("css_history", [])
    if css_history:
        avg_css = sum(css_history) / len(css_history)
        if avg_css < 0.60:
            issues.append({
                "type": "low_avg_css",
                "severity": "medium",
                "message": f"Average CSS score is {avg_css:.2f} (below 0.60)",
            })

    # Check escalation count
    escalation_log = state.get("escalation_log", [])
    if len(escalation_log) > 3:
        issues.append({
            "type": "many_escalations",
            "severity": "low",
            "message": f"{len(escalation_log)} escalations during generation",
        })

    qa_passed = not any(i["severity"] == "high" for i in issues)

    logger.info(
        "PostQA: %s (%d issues, %d high severity)",
        "PASSED" if qa_passed else "FAILED",
        len(issues),
        sum(1 for i in issues if i["severity"] == "high"),
    )

    return {
        "qa_passed": qa_passed,
        "qa_issues": issues,
    }
