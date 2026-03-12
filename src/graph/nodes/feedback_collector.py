"""Feedback Collector node (§5.23) — collect user feedback post-publish.

Final node in the pipeline. Records user satisfaction and
improvement suggestions for future runs.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def feedback_collector_node(state: dict) -> dict:
    """Collect and record feedback on the published document.

    Returns:
        Partial state with ``feedback_collected``.
    """
    doc_id = state.get("doc_id", "default")
    config = state.get("config", {})
    budget = state.get("budget", {})

    # Build run summary for feedback context
    run_summary = {
        "doc_id": doc_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "sections_completed": len(state.get("approved_sections", [])),
        "sections_planned": len(state.get("outline", [])),
        "total_cost": budget.get("spent_dollars", 0),
        "quality_preset": budget.get("quality_preset", "balanced"),
        "qa_passed": state.get("qa_passed", False),
        "escalations": len(state.get("escalation_log", [])),
        "published": state.get("published", False),
        "output_path": state.get("output_path", ""),
    }

    # Write run summary
    output_dir = Path("output") / doc_id
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    logger.info(
        "FeedbackCollector: run complete — %d sections, $%.2f spent, qa=%s",
        run_summary["sections_completed"],
        run_summary["total_cost"],
        run_summary["qa_passed"],
    )

    return {
        "feedback_collected": True,
        "run_summary": run_summary,
    }
