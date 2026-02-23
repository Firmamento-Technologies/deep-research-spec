"""Jury orchestrator — parallel execution of judges (§8.4).

Runs up to 9 judges (R1-R3, F1-F3, S1-S3) in parallel via
``asyncio.gather``.  The number of judges per mini-jury scales
with ``budget.jury_size`` (1/2/3 depending on quality preset).

Model assignments per §28:
- Judge R: ``openai/o3`` (strong reasoning)
- Judge F: ``google/gemini-2.5-pro`` (grounding + micro-search)
- Judge S: ``google/gemini-2.5-flash`` (fast, good at style)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.graph.nodes.judge_r import JudgeR
from src.graph.nodes.judge_f import JudgeF
from src.graph.nodes.judge_s import JudgeS

logger = logging.getLogger(__name__)


# ── Model assignments (§28) ─────────────────────────────────────────────────
_MODEL_R = "openai/o3"
_MODEL_F = "google/gemini-2.5-pro"
_MODEL_S = "google/gemini-2.5-flash"


def jury_node(state: dict) -> dict:
    """Run 3 mini-juries (R/F/S) in parallel.

    Args:
        state: DocumentState dict.

    Returns:
        Partial state update with ``jury_verdicts`` and
        ``all_verdicts_history``.
    """
    draft = state.get("current_draft", "")
    sources = state.get("current_sources", [])
    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])
    section_scope = (
        outline[section_idx]["scope"]
        if section_idx < len(outline)
        else ""
    )

    # Jury size from budget (1/2/3 based on preset)
    budget = state.get("budget", {})
    jury_size = budget.get("jury_size", 1)

    # Style rules for JudgeS
    style_profile = state.get("style_profile", {})
    style_rules = ""
    if isinstance(style_profile, dict):
        rules = style_profile.get("rules", [])
        if rules:
            style_rules = "\n".join(f"- {r}" for r in rules)

    # Initialize judges
    judges_r = [JudgeR(f"R{i+1}", _MODEL_R) for i in range(jury_size)]
    judges_f = [JudgeF(f"F{i+1}", _MODEL_F) for i in range(jury_size)]
    judges_s = [JudgeS(f"S{i+1}", _MODEL_S, style_rules=style_rules) for i in range(jury_size)]

    all_judges = judges_r + judges_f + judges_s

    logger.info(
        "Jury: %d judges (%d R + %d F + %d S) evaluating section %d",
        len(all_judges), jury_size, jury_size, jury_size, section_idx,
    )

    # §29.6: Parallel execution
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in async context — use thread pool
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_judges)) as pool:
            futures = [
                pool.submit(judge.evaluate, draft, sources, section_scope)
                for judge in all_judges
            ]
            verdicts = [f.result() for f in futures]
    else:
        # No running loop — create one
        async def _evaluate_all():
            tasks = [
                asyncio.to_thread(judge.evaluate, draft, sources, section_scope)
                for judge in all_judges
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)

        results = asyncio.run(_evaluate_all())
        verdicts = []
        for r in results:
            if isinstance(r, Exception):
                logger.error("Judge evaluation failed: %s", r)
                verdicts.append({
                    "judge_slot": "??",
                    "model": "error",
                    "dimension_scores": {},
                    "pass_fail": True,
                    "veto_category": None,
                    "confidence": "low",
                    "motivation": f"[ERROR] {r}",
                    "failed_claims": [],
                    "missing_evidence": [],
                    "external_sources_consulted": [],
                    "css_contribution": 0.70,
                })
            else:
                verdicts.append(r)

    logger.info(
        "Jury complete: %d verdicts, %d pass, %d veto",
        len(verdicts),
        sum(1 for v in verdicts if v.get("pass_fail")),
        sum(1 for v in verdicts if v.get("veto_category")),
    )

    history = list(state.get("all_verdicts_history", []))
    history.append(verdicts)

    return {
        "jury_verdicts": verdicts,
        "all_verdicts_history": history,
    }
