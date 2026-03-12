"""Diff Merger node (§5.13) — apply span edits to draft.

Takes ``span_edits`` from SpanEditor and applies them to
``current_draft``, producing the revised draft.
Deterministic string replacement — no LLM call.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def diff_merger_node(state: dict) -> dict:
    """Apply span edits to the current draft.

    Args:
        state: DocumentState with ``current_draft`` and ``span_edits``.

    Returns:
        Partial state with revised ``current_draft`` and
        ``applied_edits`` count.
    """
    draft = state.get("current_draft", "")
    edits = state.get("span_edits", [])

    if not edits or not draft:
        return {"applied_edits": 0}

    revised = draft
    applied = 0

    for edit in edits:
        find_text = edit.get("find", "")
        replace_text = edit.get("replace", "")

        if not find_text:
            continue

        if find_text in revised:
            revised = revised.replace(find_text, replace_text, 1)
            applied += 1
            logger.debug(
                "DiffMerger: applied edit — '%s' → '%s'",
                find_text[:50], replace_text[:50],
            )
        else:
            logger.warning(
                "DiffMerger: edit target not found in draft — '%s'",
                find_text[:50],
            )

    logger.info(
        "DiffMerger: applied %d/%d edits",
        applied, len(edits),
    )

    result = {"applied_edits": applied}
    if applied > 0:
        result["current_draft"] = revised
        result["span_edits"] = []  # Clear after applying

    return result
