"""Fusor node (§5.13 / §7) — fuse best elements from MoW drafts.

Takes the highest-CSS draft as base and integrates best elements
from other drafts into a single fused draft.
"""
from __future__ import annotations

import logging

from src.llm.client import llm_client

logger = logging.getLogger(__name__)


def fusor_node(state: dict) -> dict:
    """Fuse 3 MoW drafts into a single refined draft.

    Strategy:
    1. Use draft with highest CSS as base
    2. Integrate ``best_elements`` from other drafts
    3. Preserve all citations from base draft

    Returns:
        Partial state with ``current_draft`` (fused) and ``fusor_meta``.
    """
    drafts = state.get("mow_drafts", [])
    css_scores = state.get("mow_css_individual", [])
    best_elements = state.get("mow_best_elements", [])
    best_idx = state.get("mow_best_draft_idx", 0)

    if not drafts:
        logger.warning("Fusor: no MoW drafts to fuse")
        return {}

    # Get valid drafts
    valid = [d for d in drafts if d.get("draft")]
    if not valid:
        return {}

    # Select base draft (highest CSS, fallback to first valid)
    if best_idx < len(valid):
        base = valid[best_idx]
    else:
        base = valid[0]
        best_idx = 0

    # If only 1 valid draft, use it directly
    if len(valid) == 1 or not best_elements:
        logger.info("Fusor: using %s draft directly (no fusion needed)", base["angle"])
        return {
            "current_draft": base["draft"],
            "fusor_meta": {"strategy": "single", "base_angle": base["angle"]},
        }

    # Build fusion prompt
    other_drafts = [d for i, d in enumerate(valid) if i != best_idx]

    elements_text = "\n".join(
        f"- [{e.get('from_angle', '?')}] ({e.get('type', 'general')}): {e.get('element', '')}"
        for e in best_elements
    ) if best_elements else "No specific elements identified."

    try:
        response = llm_client.call(
            model="google/gemini-2.5-flash",
            system=[{
                "type": "text",
                "text": (
                    "You are a document editor specializing in draft fusion. "
                    "Integrate the best elements from alternative drafts into "
                    "the base draft. Preserve all citations, facts, and the "
                    "base draft's structure. Make the integration seamless."
                ),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": f"""\
BASE DRAFT ({base['angle']} — {base['label']}, CSS={css_scores[best_idx] if best_idx < len(css_scores) else 'N/A'}):
{base['draft'][:5000]}

BEST ELEMENTS TO INTEGRATE:
{elements_text}

ALTERNATIVE DRAFTS FOR REFERENCE:
{chr(10).join(f'--- {d["angle"]} ---{chr(10)}{d["draft"][:2000]}' for d in other_drafts[:2])}

INSTRUCTIONS:
1. Keep the base draft's structure and flow
2. Genuinely integrate the best elements (don't just append)
3. Preserve ALL citations from the base draft
4. Maintain consistent tone and style
5. Return the fused draft only, no commentary""",
            }],
            temperature=0.2,
            max_tokens=8192,
        )

        fused = response["text"].strip()

        # Sanity check
        if len(fused) < len(base["draft"]) * 0.4:
            logger.warning("Fusor: fused draft too short, using base")
            fused = base["draft"]

        logger.info(
            "Fusor: fused %d drafts → %d words (base=%s)",
            len(valid), len(fused.split()), base["angle"],
        )

        return {
            "current_draft": fused,
            "fusor_meta": {
                "strategy": "fusion",
                "base_angle": base["angle"],
                "elements_integrated": len(best_elements),
                "drafts_considered": len(valid),
            },
            # Clear MoW state
            "mow_drafts": [],
            "mow_css_individual": [],
            "mow_best_elements": [],
        }

    except Exception as exc:
        logger.warning("Fusor LLM call failed: %s — using base draft", exc)
        return {
            "current_draft": base["draft"],
            "fusor_meta": {"strategy": "fallback", "base_angle": base["angle"]},
        }
