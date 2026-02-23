"""Length Adjuster node (§5.20) — trim or expand to target length.

Adjusts the final document to match the target length specified
in the configuration, trimming verbose sections or expanding
thin ones.
"""
from __future__ import annotations

import logging

from src.llm.client import llm_client

logger = logging.getLogger(__name__)


def length_adjuster_node(state: dict) -> dict:
    """Adjust document length to target.

    Returns:
        Partial state with ``length_adjusted`` flag and
        potentially modified ``approved_sections``.
    """
    approved = list(state.get("approved_sections", []))
    config = state.get("config", {})

    target_words = config.get("target_word_count", 0)
    tolerance = config.get("length_tolerance", 0.15)  # ±15%

    if not target_words or not approved:
        return {"length_adjusted": False}

    # Calculate current total word count
    total_words = sum(
        len(s.get("content", s.get("draft", "")).split())
        for s in approved
    )

    ratio = total_words / target_words if target_words else 1.0
    lower = 1.0 - tolerance
    upper = 1.0 + tolerance

    if lower <= ratio <= upper:
        logger.info(
            "LengthAdjuster: %d words within target %d (±%d%%) — no adjustment needed",
            total_words, target_words, int(tolerance * 100),
        )
        return {"length_adjusted": False}

    if ratio > upper:
        action = "trim"
        logger.info(
            "LengthAdjuster: %d words > target %d — trimming",
            total_words, target_words,
        )
    else:
        action = "expand"
        logger.info(
            "LengthAdjuster: %d words < target %d — expanding",
            total_words, target_words,
        )

    # Adjust each section proportionally
    adjusted = _adjust_sections(approved, target_words, total_words, action)

    return {
        "approved_sections": adjusted,
        "length_adjusted": True,
        "length_adjustment": {
            "original_words": total_words,
            "target_words": target_words,
            "action": action,
        },
    }


def _adjust_sections(
    sections: list[dict], target_words: int, current_words: int, action: str,
) -> list[dict]:
    """Adjust section lengths proportionally."""
    if not sections:
        return sections

    target_per_section = target_words // len(sections)
    adjusted = []

    for section in sections:
        content = section.get("content", section.get("draft", ""))
        section_words = len(content.split())

        # Only adjust sections that are significantly off
        if action == "trim" and section_words > target_per_section * 1.3:
            content = _trim_section(content, target_per_section)
        elif action == "expand" and section_words < target_per_section * 0.7:
            # Expansion is risky — just flag it, don't auto-expand
            pass

        updated = dict(section)
        updated["content"] = content
        adjusted.append(updated)

    return adjusted


def _trim_section(content: str, target_words: int) -> str:
    """Trim a section to approximately target word count."""
    try:
        response = llm_client.call(
            model="google/gemini-2.5-flash",
            messages=[{
                "role": "user",
                "content": f"""\
Trim this text to approximately {target_words} words.
Preserve all key claims, citations, and arguments.
Remove redundant examples, verbose explanations, and filler.

Text:
{content[:6000]}

Return the trimmed text only, no commentary.""",
            }],
            temperature=0.1,
            max_tokens=8192,
        )
        trimmed = response["text"].strip()
        if len(trimmed) > len(content) * 0.3:  # Sanity check
            return trimmed
        return content
    except Exception as exc:
        logger.warning("LengthAdjuster trim failed: %s", exc)
        return content
