"""Span Editor node (§5.12) — surgical text edits on draft.

Takes reflector feedback items with scope=SURGICAL and applies
targeted edits to specific spans of the draft, rather than
rewriting the entire section through the Writer.
"""
from __future__ import annotations

import logging

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


def span_editor_node(state: dict) -> dict:
    """Apply surgical edits to specific spans of the draft.

    Args:
        state: DocumentState with ``current_draft``,
               ``reflector_output`` containing feedback items.

    Returns:
        Partial state with ``span_edits`` (list of edit operations)
        for ``diff_merger`` to apply.
    """
    draft = state.get("current_draft", "")
    reflector = state.get("reflector_output", {})
    feedback_items = reflector.get("feedback_items", [])

    if not draft or not feedback_items:
        return {"span_edits": []}

    # Filter to high-priority, surgically fixable items
    surgical_items = [
        item for item in feedback_items
        if item.get("priority") in ("high", "medium")
    ][:5]  # Cap at 5 edits per pass

    preset = state.get("quality_preset", "balanced")
    edits = _generate_edits(draft, surgical_items, preset)

    logger.info(
        "SpanEditor: generated %d edits from %d feedback items",
        len(edits), len(surgical_items),
    )

    return {"span_edits": edits}


def _generate_edits(draft: str, items: list[dict], quality_preset: str = "balanced") -> list[dict]:
    """Use LLM to generate specific edit operations."""
    try:
        feedback_text = "\n".join(
            f"- [{item.get('type', '?')}] {item.get('description', '')}"
            + (f" → {item.get('fix_hint', '')}" if item.get('fix_hint') else "")
            for item in items
        )

        response = llm_client.call(
            model=route_model("span_editor", quality_preset),
            messages=[{
                "role": "user",
                "content": f"""\
Apply surgical fixes to this draft based on the feedback below.
Make MINIMAL changes — only fix what's listed.

Feedback:
{feedback_text}

Draft:
{draft[:4000]}

For each edit, return in this format:
EDIT:
FIND: [exact text to find in draft]
REPLACE: [replacement text]
REASON: [why this fix is needed]

Only return EDIT blocks, nothing else.""",
            }],
            temperature=0.1,
            max_tokens=4096,
            agent="span_editor",
            preset=quality_preset,
        )

        return _parse_edits(response["text"])

    except Exception as exc:
        logger.warning("SpanEditor LLM call failed: %s", exc)
        return []


def _parse_edits(text: str) -> list[dict]:
    """Parse EDIT blocks from LLM response."""
    edits = []
    current_edit = {}
    current_field = None

    for line in text.split("\n"):
        line_stripped = line.strip()

        if line_stripped == "EDIT:":
            if current_edit.get("find") and current_edit.get("replace"):
                edits.append(current_edit)
            current_edit = {}
            current_field = None
        elif line_stripped.startswith("FIND:"):
            current_edit["find"] = line_stripped[len("FIND:"):].strip()
            current_field = "find"
        elif line_stripped.startswith("REPLACE:"):
            current_edit["replace"] = line_stripped[len("REPLACE:"):].strip()
            current_field = "replace"
        elif line_stripped.startswith("REASON:"):
            current_edit["reason"] = line_stripped[len("REASON:"):].strip()
            current_field = "reason"
        elif current_field and line_stripped:
            # Multi-line content
            current_edit[current_field] = current_edit.get(current_field, "") + "\n" + line_stripped

    # Don't forget the last edit
    if current_edit.get("find") and current_edit.get("replace"):
        edits.append(current_edit)

    return edits[:10]
