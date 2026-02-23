"""Style linter (§5.9) — detect style rule violations in draft.

Checks the current draft against style profile rules and produces
a list of ``StyleLintViolation`` dicts.  The router
(``route_style_lint``) sends to ``style_fixer`` if violations exist,
otherwise passes to ``metrics_collector``.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)

# ── Built-in L1 rules (always enforced) ──────────────────────────────────────

_L1_RULES: list[dict] = [
    {
        "rule_id": "L1_NO_FIRST_PERSON",
        "pattern": r"\b(I |my |we |our )\b",
        "category": "voice",
        "message": "Avoid first-person pronouns in academic writing",
        "fix_hint": "Rephrase using passive voice or third person",
    },
    {
        "rule_id": "L1_NO_CONTRACTIONS",
        "pattern": r"\b(don't|won't|can't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|shouldn't|wouldn't|couldn't)\b",
        "category": "formality",
        "message": "Avoid contractions in formal writing",
        "fix_hint": "Expand the contraction",
    },
    {
        "rule_id": "L1_NO_VERY",
        "pattern": r"\bvery\b",
        "category": "precision",
        "message": "'Very' is imprecise — use a stronger adjective",
        "fix_hint": "Replace 'very X' with a more precise word",
    },
]


def style_linter_node(state: dict) -> dict:
    """Lint the current draft against style rules.

    Args:
        state: DocumentState dict with ``current_draft`` and
               ``style_profile``.

    Returns:
        Partial state update with ``style_lint_violations``.
    """
    draft = state.get("current_draft", "")
    style_profile = state.get("style_profile", {})

    violations: list[dict] = []

    # 1. Regex-based L1 rules (fast, deterministic)
    profile_name = (
        style_profile if isinstance(style_profile, str)
        else style_profile.get("name", "academic")
    )

    if profile_name in ("academic", "formal", "scientific"):
        for rule in _L1_RULES:
            matches = list(re.finditer(rule["pattern"], draft, re.IGNORECASE))
            for m in matches[:3]:  # cap at 3 per rule
                violations.append({
                    "rule_id": rule["rule_id"],
                    "level": "L1",
                    "category": rule["category"],
                    "position": m.start(),
                    "matched_text": m.group()[:50],
                    "message": rule["message"],
                    "fix_hint": rule["fix_hint"],
                })

    # 2. LLM-based L2 rules (style profile specific)
    custom_rules = []
    if isinstance(style_profile, dict):
        custom_rules = style_profile.get("rules", [])

    if custom_rules and draft:
        preset = state.get("quality_preset", "balanced")
        l2_violations = _check_l2_rules(draft, custom_rules, preset)
        violations.extend(l2_violations)

    logger.info(
        "StyleLinter: %d violations (%d L1, %d L2)",
        len(violations),
        sum(1 for v in violations if v.get("level") == "L1"),
        sum(1 for v in violations if v.get("level") == "L2"),
    )

    return {
        "style_lint_violations": violations,
    }


def _check_l2_rules(draft: str, rules: list[str], quality_preset: str = "balanced") -> list[dict]:
    """Use LLM to check custom style rules (L2)."""
    try:
        rules_text = "\n".join(f"- {r}" for r in rules)
        response = llm_client.call(
            model=route_model("style_fixer", quality_preset),
            messages=[{
                "role": "user",
                "content": f"""\
Check this draft against these style rules. Report violations only.

Rules:
{rules_text}

Draft (first 3000 chars):
{draft[:3000]}

For each violation, return one line in format:
VIOLATION: [rule] | [matched text excerpt] | [fix suggestion]

If no violations, return: NO_VIOLATIONS""",
            }],
            temperature=0.1,
            max_tokens=1024,
            agent="style_linter",
            preset=quality_preset,
        )

        violations = []
        for line in response["text"].split("\n"):
            line = line.strip()
            if line.startswith("VIOLATION:"):
                parts = line[len("VIOLATION:"):].split("|")
                if len(parts) >= 2:
                    violations.append({
                        "rule_id": "L2_CUSTOM",
                        "level": "L2",
                        "category": "custom_rule",
                        "position": 0,
                        "matched_text": parts[1].strip()[:50],
                        "message": parts[0].strip(),
                        "fix_hint": parts[2].strip() if len(parts) >= 3 else "Fix the violation",
                    })
        return violations[:10]

    except Exception as exc:
        logger.warning("StyleLinter L2 check failed: %s", exc)
        return []
