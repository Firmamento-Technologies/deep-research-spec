"""RLM adapter for PostDraftAnalyzer §5.11.

Upgrade over the single-prompt Gemini Flash analysis: RLM performs a
multi-pass coverage check — first decomposing section_scope into subtopics,
then verifying coverage for each individually before flagging real gaps.

DocumentState contract:
  CONSUMES: current_draft, current_sources, current_section_idx,
             current_iteration, config.quality_preset, outline
  PRODUCES: post_draft_gaps (list[dict]), gap_found (bool)

Preconditions (§5.11 — all must hold or node returns empty gaps):
  - current_iteration == 1
  - quality_preset != 'Economy'
  - len(current_sources) < 20
  - section target_words >= 400

Feature flag: config.features.rlm_post_draft_analyzer
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.rlm.runtime import get_rlm_runtime
from src.rlm.budget_bridge import emit_cost_entries

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = frozenset(
    {"missing_evidence", "emerging_subtopic", "forward_looking"}
)


async def post_draft_analyzer_rlm_node(state: dict) -> dict:
    """Multi-pass coverage gap detection using RLM."""
    # §5.11 preconditions — must all hold
    iteration = state.get("current_iteration", 1)
    preset = state.get("config", {}).get("quality_preset", "Balanced")
    sources = state.get("current_sources", [])
    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])

    if section_idx >= len(outline):
        return _empty()

    target_words = outline[section_idx].get("target_words", 0)

    if iteration != 1 or preset == "Economy" or len(sources) >= 20 or target_words < 400:
        return _empty()

    features = state.get("config", {}).get("features", {})
    if not features.get("rlm_post_draft_analyzer", False):
        return await _fallback(state)

    section = outline[section_idx]
    section_scope = section.get("scope", "")
    draft = state.get("current_draft", "")

    context = {
        "draft": draft[:10000],
        "section_scope": section_scope,
        "section_title": section.get("title", ""),
        "target_words": target_words,
        "sources_available": [
            {
                "id": i,
                "title": s.get("title", ""),
                "source_type": s.get("source_type", ""),
                "snippet": s.get("abstract", "")[:300],
            }
            for i, s in enumerate(sources[:20])
        ],
        "n_sources": len(sources),
    }

    task = (
        f'Analyze this research section draft to identify information gaps.\n'
        f'Section covers: "{section_scope}"\n'
        f'Target length: {target_words} words\n\n'
        f'Strategy:\n'
        f'  1. Use llm_query() on the draft to extract main subtopics ACTUALLY covered.\n'
        f'  2. Decompose "{section_scope}" into subtopics a complete treatment should cover.\n'
        f'  3. Compare: find subtopics missing from the draft.\n'
        f'  4. Check if sources_available already contain evidence for missing subtopics.\n'
        f'     If yes → "missing_evidence" (Writer did not use it).\n'
        f'     If no  → "emerging_subtopic" or "forward_looking".\n\n'
        f'CONSTRAINTS:\n'
        f'  - Max 3 gaps — prioritise by severity\n'
        f'  - NEVER flag gaps already answered by sources_available\n'
        f'  - Each gap needs 1-2 suggested_queries for the Researcher\n\n'
        f'Set final_answer = {{"gaps": ['
        f'{{"category": str, "description": str, "suggested_queries": [str]}}], '
        f'"gap_found": bool}}'
    )

    rlm = get_rlm_runtime(
        max_subcalls=10,
        cost_hard_limit=0.10,
        timeout_seconds=45,
    )

    result = await rlm.run(context=context, task_instruction=task)
    await emit_cost_entries(state=state, agent="post_draft_analyzer_rlm", rlm_result=result)

    # §5.11: timeout → gap_found=False
    if result.method == "fallback" and result.output is None:
        return _empty()

    raw = result.output if isinstance(result.output, dict) else {}
    gaps = raw.get("gaps", [])

    clean_gaps: list[dict] = []
    for g in gaps[:3]:
        category = g.get("category", "")
        if category not in _VALID_CATEGORIES:
            continue
        clean_gaps.append(
            {
                "category": category,
                "description": str(g.get("description", ""))[:300],
                "suggested_queries": g.get("suggested_queries", [])[:2],
            }
        )

    return {"post_draft_gaps": clean_gaps, "gap_found": bool(clean_gaps)}


def _empty() -> dict:
    return {"post_draft_gaps": [], "gap_found": False}


async def _fallback(state: dict) -> dict:
    try:
        from src.nodes.post_draft_analyzer import post_draft_analyzer_node
        return await post_draft_analyzer_node(state)
    except ImportError:
        logger.error("src.nodes.post_draft_analyzer not found — returning empty gaps.")
        return _empty()
