"""RLM adapter for CoherenceGuard §5.17.

Instead of feeding all approved sections into a single Gemini Flash prompt,
RLM navigates the approved corpus selectively: the root model scans section
titles first, then reads only thematically relevant sections before checking
for SOFT/HARD contradictions — reducing false negatives on long documents.

DocumentState contract:
  CONSUMES: current_draft, approved_sections, current_section_idx, outline
  PRODUCES: coherence_conflicts (list[dict]), conflict_detected (bool)

Feature flag: config.features.rlm_coherence_guard
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.rlm.runtime import get_rlm_runtime
from src.rlm.budget_bridge import emit_cost_entries

logger = logging.getLogger(__name__)


async def coherence_guard_rlm_node(state: dict) -> dict:
    """Selective contradiction detection using RLM.

    Falls back to original coherence_guard_node when:
    - Feature flag is off
    - len(approved_sections) < 3 (standard node is faster for small sets)
    """
    features = state.get("config", {}).get("features", {})
    if not features.get("rlm_coherence_guard", False):
        return await _fallback(state)

    approved = state.get("approved_sections", [])
    if len(approved) < 3:
        return await _fallback(state)

    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])
    if section_idx >= len(outline):
        return await _fallback(state)

    section = outline[section_idx]

    context = {
        "new_section_title": section.get("title", ""),
        "new_section_scope": section.get("scope", ""),
        "new_section_text": state.get("current_draft", "")[:12000],
        "approved_metadata": [
            {
                "id": s.get("idx", i),
                "title": s.get("title", ""),
                "word_count": len(s.get("content", "").split()),
            }
            for i, s in enumerate(approved)
        ],
        "approved_texts": {
            str(s.get("idx", i)): s.get("content", "")[:6000]
            for i, s in enumerate(approved)
        },
        "total_approved": len(approved),
    }

    task = (
        "Detect factual contradictions between a new document section "
        "and previously approved sections.\n\n"
        "Strategy:\n"
        "  1. Read new_section_text — extract all factual claims "
        "     (numbers, dates, causal statements, quantitative assertions).\n"
        "  2. Scan approved_metadata titles to identify thematically related sections.\n"
        "  3. For each related section use llm_query() to check for contradictions.\n\n"
        "Conflict types:\n"
        "  - SOFT: numerical inconsistency, phrasing ambiguity\n"
        "  - HARD: direct logical contradiction of a factual claim\n\n"
        "IMPORTANT: Only flag FACTUAL claims. Ignore opinion or style differences.\n\n"
        'Set final_answer = {"conflicts": [{"type": "SOFT"|"HARD", '
        '"claim_new": str, "claim_existing": str, '
        '"existing_section_idx": int, "description": str}], '
        '"conflict_detected": bool, "sections_checked": [int]}'
    )

    rlm = get_rlm_runtime(
        max_subcalls=15,
        cost_hard_limit=0.15,
        timeout_seconds=60,
    )

    result = await rlm.run(context=context, task_instruction=task)
    await emit_cost_entries(state=state, agent="coherence_guard_rlm", rlm_result=result)

    raw = result.output
    if not isinstance(raw, dict):
        # Conservative fallback: no conflict (do not block approval)
        logger.warning(
            "CoherenceGuardRLM: unexpected output type %s, returning no conflicts.",
            type(raw).__name__,
        )
        return {"coherence_conflicts": [], "conflict_detected": False}

    conflicts = raw.get("conflicts", [])
    normalized: list[dict] = []
    for c in conflicts:
        if c.get("type") not in ("SOFT", "HARD"):
            continue
        normalized.append(
            {
                "level": c["type"],
                "section_a_idx": section_idx,
                "section_b_idx": c.get("existing_section_idx", -1),
                "claim_a": c.get("claim_new", ""),
                "claim_b": c.get("claim_existing", ""),
                "description": c.get("description", ""),
            }
        )

    return {
        "coherence_conflicts": normalized,
        "conflict_detected": bool(normalized),
    }


async def _fallback(state: dict) -> dict:
    try:
        from src.nodes.coherence_guard import coherence_guard_node
        return await coherence_guard_node(state)
    except ImportError:
        logger.error("src.nodes.coherence_guard not found — returning no conflicts.")
        return {"coherence_conflicts": [], "conflict_detected": False}
