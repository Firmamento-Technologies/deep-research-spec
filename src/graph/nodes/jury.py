"""Jury orchestrator — parallel execution of judges (§8.4).

Runs up to 9 judges (R1-R3, F1-F3, S1-S3) in parallel via
``asyncio.gather``.  The number of judges per mini-jury scales
with ``budget.jury_size`` (1/2/3 depending on quality preset).

Model assignments dynamically resolved via ``route_model()`` — respects
economy/balanced/premium presets for cost optimization.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.graph.nodes.judge_r import JudgeR
from src.graph.nodes.judge_f import JudgeF
from src.graph.nodes.judge_s import JudgeS
from src.llm.routing import route_model
from src.observability.metrics import DRS_JURY_QUALITY

logger = logging.getLogger(__name__)


def _error_verdict(exc: Exception) -> dict:
    """Fail-closed verdict: reject on infrastructure error (§Task 1.4)."""
    return {
        "judge_slot": "error",
        "model": "error",
        "dimension_scores": {},
        "pass_fail": False,              # FAIL CLOSED ✓
        "veto_category": "technical_failure",
        "confidence": "error",
        "motivation": f"[SYSTEM ERROR] Judge crashed: {str(exc)[:200]}",
        "failed_claims": [],
        "missing_evidence": [],
        "external_sources_consulted": [],
        "css_contribution": 0.0,
    }


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

    # Dynamic model routing (§Task 1.2) — replaces hardcoded tier3 models
    preset = state.get("quality_preset", "balanced")
    model_r = route_model("jury_r", preset)
    model_f = route_model("jury_f", preset)
    model_s = route_model("jury_s", preset)

    # Style rules for JudgeS
    style_profile = state.get("style_profile", {})
    style_rules = ""
    if isinstance(style_profile, dict):
        rules = style_profile.get("rules", [])
        if rules:
            style_rules = "\n".join(f"- {r}" for r in rules)

    # Initialize judges with routed models
    judges_r = [JudgeR(f"R{i+1}", model_r) for i in range(jury_size)]
    judges_f = [JudgeF(f"F{i+1}", model_f) for i in range(jury_size)]
    judges_s = [JudgeS(f"S{i+1}", model_s, style_rules=style_rules) for i in range(jury_size)]

    all_judges = judges_r + judges_f + judges_s

    logger.info(
        "Jury: %d judges (%d R + %d F + %d S) evaluating section %d "
        "[preset=%s, models=%s/%s/%s]",
        len(all_judges), jury_size, jury_size, jury_size, section_idx,
        preset, model_r, model_f, model_s,
    )

    # §29.6: Parallel execution — always use ThreadPoolExecutor
    # (avoids event loop contamination from asyncio.run())
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_judges)) as pool:
        futures = [
            pool.submit(judge.evaluate, draft, sources, section_scope)
            for judge in all_judges
        ]
        verdicts = []
        for f in futures:
            try:
                verdicts.append(f.result())
            except Exception as exc:
                logger.error("Judge evaluation failed: %s", exc)
                verdicts.append(_error_verdict(exc))

    pass_count = sum(1 for v in verdicts if v.get("pass_fail"))
    veto_count = sum(1 for v in verdicts if v.get("veto_category"))
    pass_rate = pass_count / len(verdicts) if verdicts else 0.0

    logger.info(
        "Jury complete: %d verdicts, %d pass, %d veto (rate=%.2f)",
        len(verdicts), pass_count, veto_count, pass_rate,
    )

    # Record pass rate metric
    DRS_JURY_QUALITY.labels(preset=preset).set(pass_rate)

    history = list(state.get("all_verdicts_history", []))
    history.append(verdicts)

    return {
        "jury_verdicts": verdicts,
        "all_verdicts_history": history,
    }

