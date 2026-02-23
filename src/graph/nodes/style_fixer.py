"""Style fixer (§5.10) — apply fixes for lint violations.

Takes the current draft + list of ``StyleLintViolation`` dicts and
produces a revised draft with violations fixed.  Uses LLM for
nuanced fixes (L2 rules) and regex for simple fixes (L1 rules).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


def style_fixer_node(state: dict) -> dict:
    """Fix style violations in the current draft.

    Args:
        state: DocumentState dict with ``current_draft`` and
               ``style_lint_violations``.

    Returns:
        Partial state update with revised ``current_draft`` and
        cleared ``style_lint_violations``.
    """
    draft = state.get("current_draft", "")
    violations = state.get("style_lint_violations", [])

    if not violations or not draft:
        return {}

    l1_violations = [v for v in violations if v.get("level") == "L1"]
    l2_violations = [v for v in violations if v.get("level") == "L2"]

    fixed_draft = draft

    # 1. L1 fixes — deterministic regex replacements
    if l1_violations:
        fixed_draft = _apply_l1_fixes(fixed_draft, l1_violations)

    # 2. L2 fixes — LLM-powered revision
    if l2_violations:
        fixed_draft = _apply_l2_fixes(fixed_draft, l2_violations)

    changes = len(violations)
    logger.info("StyleFixer: applied %d fixes (%d L1, %d L2)",
                changes, len(l1_violations), len(l2_violations))

    return {
        "current_draft": fixed_draft,
        "style_lint_violations": [],  # Clear after fixing
    }


def _apply_l1_fixes(draft: str, violations: list[dict]) -> str:
    """Apply simple regex-based L1 fixes."""
    fixed = draft

    # Expand contractions
    contractions = {
        "don't": "do not", "won't": "will not", "can't": "cannot",
        "isn't": "is not", "aren't": "are not", "wasn't": "was not",
        "weren't": "were not", "hasn't": "has not", "haven't": "have not",
        "hadn't": "had not", "shouldn't": "should not",
        "wouldn't": "would not", "couldn't": "could not",
        "Don't": "Do not", "Won't": "Will not", "Can't": "Cannot",
        "Isn't": "Is not", "Aren't": "Are not",
    }

    for contraction, expansion in contractions.items():
        fixed = fixed.replace(contraction, expansion)

    return fixed


def _apply_l2_fixes(draft: str, violations: list[dict]) -> str:
    """Use LLM to fix L2 style violations."""
    try:
        violation_text = "\n".join(
            f"- {v['message']}: \"{v.get('matched_text', '')}\" → {v.get('fix_hint', 'fix')}"
            for v in violations[:10]
        )

        response = llm_client.call(
            model=route_model("style_fixer", state.get("quality_preset", "balanced")),
            messages=[{
                "role": "user",
                "content": f"""\
Fix these style violations in the draft. Make minimal changes — only fix the
violations listed below. Do not change content, meaning, or citations.

Violations to fix:
{violation_text}

Draft:
{draft[:6000]}

Return the COMPLETE revised draft with violations fixed.""",
            }],
            temperature=0.1,
            max_tokens=8192,
        )

        revised = response["text"].strip()
        # Sanity check: LLM response should be similar length
        if len(revised) > len(draft) * 0.5:
            return revised
        else:
            logger.warning("StyleFixer L2: LLM response too short, keeping original")
            return draft

    except Exception as exc:
        logger.warning("StyleFixer L2 failed: %s", exc)
        return draft
