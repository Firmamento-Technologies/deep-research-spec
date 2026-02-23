"""Planner agent (§5.1) — outline generation.

Takes a topic + target word count and produces a structured outline
(list of ``OutlineSection`` dicts).  Uses the LLM to generate the
outline as JSON, with a deterministic fallback if parsing fails.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


def planner_node(state: dict) -> dict:
    """Generate section outline from topic.

    Reads ``config.topic``, ``config.target_words``, ``style_profile``,
    ``quality_preset`` from state.

    Returns:
        Partial state update with ``outline``, ``total_sections``,
        ``outline_approved``.
    """
    config = state.get("config", {})
    topic = config.get("topic", state.get("topic", ""))
    target_words = config.get("target_words", state.get("target_words", 3000))
    style_profile = state.get("style_profile", {})
    quality_preset = state.get("quality_preset", "Balanced")

    style_name = (
        style_profile if isinstance(style_profile, str)
        else style_profile.get("name", "academic")
    )

    prompt = f"""\
Create a detailed outline for a {style_name} document on: {topic}

Total target: {target_words} words

Generate 5-10 sections with:
- Title (concise)
- Scope (2-3 sentence description of what this section covers)
- Target word count (distribute {target_words} proportionally, min 200 words/section)
- Dependencies (section indices that must come before, if any)

Return ONLY valid JSON (no markdown fences, no commentary):
{{
  "sections": [
    {{"idx": 0, "title": "...", "scope": "...", "target_words": 500, "dependencies": []}},
    ...
  ],
  "document_type": "survey|tutorial|review|report|spec|essay|blog"
}}"""

    try:
        response = llm_client.call(
            model=route_model("planner", quality_preset),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
            agent="planner",
            preset=quality_preset,
        )

        outline_data = _parse_json_response(response["text"])
        outline = outline_data.get("sections", [])
        document_type = outline_data.get("document_type", "report")

        # Validate outline structure
        validated = _validate_outline(outline, target_words)

        logger.info(
            "Planner generated %d sections for '%s' (type=%s, cost=$%.4f)",
            len(validated), topic[:50], document_type, response["cost_usd"],
        )

    except Exception as exc:
        logger.warning("Planner LLM call failed (%s) — using fallback outline", exc)
        validated = _fallback_outline(topic, target_words)
        document_type = "report"

    return {
        "outline": validated,
        "total_sections": len(validated),
        "outline_approved": False,  # Needs human approval (skip for MVP)
    }


# ── JSON parsing ─────────────────────────────────────────────────────────────

def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    # Strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


def _validate_outline(sections: list[dict], target_words: int) -> list[dict]:
    """Validate and normalise outline sections."""
    if not sections:
        return _fallback_outline("", target_words)

    validated = []
    for i, s in enumerate(sections):
        validated.append({
            "idx": i,
            "title": s.get("title", f"Section {i + 1}"),
            "scope": s.get("scope", ""),
            "target_words": max(200, s.get("target_words", target_words // len(sections))),
            "dependencies": s.get("dependencies", []),
        })
    return validated


def _fallback_outline(topic: str, target_words: int) -> list[dict]:
    """Deterministic fallback when LLM parsing fails."""
    n_sections = max(3, min(8, target_words // 500))
    words_per = target_words // n_sections

    titles = [
        "Introduction",
        "Background and Context",
        "Core Analysis",
        "Key Findings",
        "Discussion",
        "Implications",
        "Future Directions",
        "Conclusion",
    ][:n_sections]

    return [
        {
            "idx": i,
            "title": title,
            "scope": f"{title} for topic: {topic}" if topic else title,
            "target_words": words_per,
            "dependencies": [i - 1] if i > 0 else [],
        }
        for i, title in enumerate(titles)
    ]
