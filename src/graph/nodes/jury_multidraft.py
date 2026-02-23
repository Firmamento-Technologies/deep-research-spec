"""JuryMultiDraft node (§7.5) — lightweight jury for MoW drafts.

Evaluates 3 MoW drafts to determine CSS per draft and extract
best elements for the Fusor. Uses a single judge per dimension
(not the full 9-judge jury) for cost efficiency.

Does NOT register scores in ``css_history`` — only post-fusion
scores count.
"""
from __future__ import annotations

import json
import logging
import re

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


def jury_multidraft_node(state: dict) -> dict:
    """Evaluate 3 MoW drafts and extract best elements.

    Returns:
        Partial state with ``mow_css_individual``, ``mow_best_elements``,
        and ``mow_best_draft_idx``.
    """
    drafts = state.get("mow_drafts", [])
    if not drafts or len(drafts) < 2:
        logger.warning("JuryMultiDraft: insufficient drafts (%d)", len(drafts))
        return {"mow_css_individual": [], "mow_best_elements": [], "mow_best_draft_idx": 0}

    # Filter out failed drafts
    valid_drafts = [d for d in drafts if d.get("draft") and d.get("word_count", 0) > 50]
    if not valid_drafts:
        return {"mow_css_individual": [], "mow_best_elements": [], "mow_best_draft_idx": 0}

    outline = state.get("outline", [])
    idx = state.get("current_section_idx", 0)
    section = outline[idx] if idx < len(outline) else {}
    section_scope = section.get("scope", section.get("title", ""))

    # Evaluate via single LLM call (cost-efficient)
    css_scores, best_elements = _evaluate_drafts(valid_drafts, section_scope)

    # Find best draft index
    best_idx = 0
    if css_scores:
        best_idx = css_scores.index(max(css_scores))

    logger.info(
        "JuryMultiDraft: scores=%s, best=%s (idx=%d)",
        [f"{s:.2f}" for s in css_scores],
        valid_drafts[best_idx]["angle"] if best_idx < len(valid_drafts) else "?",
        best_idx,
    )

    return {
        "mow_css_individual": css_scores,
        "mow_best_elements": best_elements,
        "mow_best_draft_idx": best_idx,
    }


def _evaluate_drafts(drafts: list[dict], section_scope: str) -> tuple[list[float], list[dict]]:
    """Evaluate multiple drafts in a single LLM call."""
    try:
        drafts_text = ""
        for i, d in enumerate(drafts):
            drafts_text += f"\n--- DRAFT {d['angle']} ({d['label']}) ---\n"
            drafts_text += d["draft"][:3000]  # Cap for context budget
            drafts_text += "\n"

        response = llm_client.call(
            model=route_model("coherence_guard", state.get("quality_preset", "balanced")),
            messages=[{
                "role": "user",
                "content": f"""\
Evaluate these {len(drafts)} drafts for the section: "{section_scope}"

{drafts_text}

For each draft, provide:
1. A quality score from 0.0 to 1.0 (considering reasoning, factual accuracy, and style)
2. The best 1-2 elements (specific paragraphs, arguments, or phrasings) worth preserving

Return JSON:
{{
  "scores": [
    {{"angle": "W-A", "css": 0.75, "strengths": "good coverage"}},
    ...
  ],
  "best_elements": [
    {{"from_angle": "W-B", "element": "The argument about X is particularly strong because...", "type": "argument"}},
    ...
  ]
}}""",
            }],
            temperature=0.1,
            max_tokens=2048,
        )

        return _parse_evaluation(response["text"], len(drafts))

    except Exception as exc:
        logger.warning("JuryMultiDraft evaluation failed: %s", exc)
        # Fallback: equal scores
        return [0.70] * len(drafts), []


def _parse_evaluation(text: str, n_drafts: int) -> tuple[list[float], list[dict]]:
    """Parse evaluation JSON from LLM response."""
    scores = []
    best_elements = []

    # Try JSON parse
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            for s in data.get("scores", []):
                css = float(s.get("css", 0.70))
                scores.append(max(0.0, min(1.0, css)))

            for elem in data.get("best_elements", []):
                best_elements.append({
                    "from_angle": elem.get("from_angle", ""),
                    "element": elem.get("element", "")[:500],
                    "type": elem.get("type", "general"),
                })
        except (json.JSONDecodeError, ValueError):
            pass

    # Pad scores if needed
    while len(scores) < n_drafts:
        scores.append(0.70)

    return scores[:n_drafts], best_elements[:6]
