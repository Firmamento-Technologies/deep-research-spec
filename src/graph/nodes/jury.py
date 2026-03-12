"""Jury orchestrator — parallel execution of judges (§8.4).

Runs up to 9 judges (R1-R3, F1-F3, S1-S3) in parallel via a module-level
ThreadPoolExecutor. The number of judges per mini-jury scales with
``budget.jury_size`` (1/2/3 depending on quality preset).

RLM changes vs original:
  - Module-level thread pool (_jury_pool, max_workers=9):
    Avoids pool creation/teardown overhead on every section.
    ThreadPoolExecutor.__init__ acquires GIL locks + spawns OS threads;
    recreating it per section introduces ~2-5ms of unnecessary latency.
  - Heterogeneous jury slots via route_jury_slots():
    Each judge in a panel uses a different provider backbone:
    Slot 1 = OpenAI, Slot 2 = Google, Slot 3 = Anthropic.
    Ensures independent epistemic perspectives per panel
    (ChatEval arXiv:2308.07201: diverse models reduce herding bias).
  - Bounded verdicts history (_MAX_HISTORY_ROUNDS=10):
    Caps all_verdicts_history to prevent unbounded growth across
    iterative refinement rounds (context overflow in downstream agents).
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.graph.nodes.judge_r import JudgeR
from src.graph.nodes.judge_f import JudgeF
from src.graph.nodes.judge_s import JudgeS
from src.llm.routing import route_model, route_jury_slots
from src.observability.metrics import DRS_JURY_QUALITY

logger = logging.getLogger(__name__)

# Module-level thread pool — created ONCE, reused across all sections.
# max_workers=9: maximum judges in premium preset (3R + 3F + 3S).
# Avoids per-section ThreadPoolExecutor.__init__ overhead and GIL contention.
_jury_pool = ThreadPoolExecutor(max_workers=9)

# Maximum verdict history rounds retained in state (prevents context overflow)
_MAX_HISTORY_ROUNDS = 10


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
    """Run 3 mini-juries (R/F/S) in parallel using heterogeneous model slots.

    Args:
        state: DocumentState dict.

    Returns:
        Partial state update with ``jury_verdicts`` and
        ``all_verdicts_history`` (bounded to last 10 rounds).
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

    # Heterogeneous jury slots: R1=OpenAI, R2=Google, R3=Anthropic.
    # route_jury_slots() returns a list of `jury_size` distinct model strings,
    # each from a different provider backbone for epistemic independence.
    preset = state.get("quality_preset", "balanced")
    models_r = route_jury_slots("r", preset, jury_size)
    models_f = route_jury_slots("f", preset, jury_size)
    models_s = route_jury_slots("s", preset, jury_size)

    # Style rules for JudgeS
    style_profile = state.get("style_profile", {})
    style_rules = ""
    if isinstance(style_profile, dict):
        rules = style_profile.get("rules", [])
        if rules:
            style_rules = "\n".join(f"- {r}" for r in rules)

    # Initialize judges — each slot gets its own provider backbone
    judges_r = [JudgeR(f"R{i+1}", models_r[i]) for i in range(jury_size)]
    judges_f = [JudgeF(f"F{i+1}", models_f[i]) for i in range(jury_size)]
    judges_s = [JudgeS(f"S{i+1}", models_s[i], style_rules=style_rules) for i in range(jury_size)]

    all_judges = judges_r + judges_f + judges_s

    logger.info(
        "Jury: %d judges (%dR+%dF+%dS) section=%d preset=%s "
        "models_r=%s models_f=%s models_s=%s",
        len(all_judges), jury_size, jury_size, jury_size, section_idx,
        preset, models_r, models_f, models_s,
    )

    # §29.6: Parallel execution via module-level pool (no per-section pool creation)
    futures = [
        _jury_pool.submit(judge.evaluate, draft, sources, section_scope)
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

    # Bounded history: retain only last _MAX_HISTORY_ROUNDS rounds to prevent
    # unbounded growth across iterative refinement (context overflow protection)
    history = list(state.get("all_verdicts_history", []))
    if len(history) > _MAX_HISTORY_ROUNDS:
        history = history[-_MAX_HISTORY_ROUNDS:]
    history.append(verdicts)

    return {
        "jury_verdicts": verdicts,
        "all_verdicts_history": history,
    }
