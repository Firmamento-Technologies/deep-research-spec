"""Await Outline node (§5.3) — human review gate for outline.

Pauses execution to allow human review/edit of the generated outline.
In automated mode, auto-approves after validation checks.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def await_outline_node(state: dict) -> dict:
    """Gate for human outline review.

    In automated/CI mode, validates outline structure and auto-approves.
    In interactive mode, sets flag for external polling.

    Returns:
        Partial state with ``outline_approved``.
    """
    outline = state.get("outline", [])
    config = state.get("config", {})
    auto_approve = config.get("auto_approve_outline", True)

    if not outline:
        logger.warning("AwaitOutline: no outline to review")
        return {"outline_approved": False}

    # Validate outline structure
    valid = True
    for i, section in enumerate(outline):
        if not isinstance(section, dict):
            logger.warning("AwaitOutline: section %d is not a dict", i)
            valid = False
            break
        if not section.get("title"):
            logger.warning("AwaitOutline: section %d missing title", i)
            valid = False
            break

    if auto_approve and valid:
        logger.info(
            "AwaitOutline: auto-approved outline with %d sections",
            len(outline),
        )
        return {"outline_approved": True}

    # In interactive mode, set pending flag
    logger.info(
        "AwaitOutline: %d sections pending human review (valid=%s)",
        len(outline), valid,
    )
    return {
        "outline_approved": valid and auto_approve,
        "human_review_pending": "outline",
    }
