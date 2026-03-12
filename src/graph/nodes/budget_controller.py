"""BudgetController graph node — §19.5 canonical.

Deterministic node that adjusts BudgetState levers after each section
based on actual spend. Re-projects final cost, applies dynamic savings,
and refreshes thresholds after any regime change.
"""
from __future__ import annotations

import logging
from typing import Any

from src.budget.regime import (
    REGIME_PARAMS,
    derive_quality_preset,
    populate_budget_thresholds,
)
from src.budget.tracker import apply_dynamic_savings, check_section_anomaly

logger = logging.getLogger(__name__)


async def budget_controller_node(state: dict) -> dict:
    """Adjust BudgetState levers after each section. §19.5.

    Deterministic node (no LLM call). Called after each section completes
    to update the budget, re-project costs, and apply savings strategies.

    Constraints (§19.5):
        MUST call apply_dynamic_savings() from §19.4
        MUST re-project final cost: projected_final = (spent / sections_done) * total_sections
        MUST call populate_budget_thresholds() after any regime change
        MUST emit SSE event BUDGET_UPDATE after every section (§23.5)
        NEVER reduce css_content_threshold below 0.45
        NEVER reduce css_style_threshold below 0.60
        NEVER reduce jury_size below 1

    Error handling (§19.5):
        sections_done == 0 → skip projection → return budget unchanged
        max_dollars == 0 → raise ValueError → halt preflight

    Args:
        state: DocumentState dict.

    Returns:
        Dict with updated ``budget`` (and optionally ``human_intervention_required``
        and ``active_escalation``) for state merge.
    """
    budget = dict(state.get("budget", {}))
    current_section_idx: int = state.get("current_section_idx", 0)
    total_sections: int = state.get("total_sections", 0)

    # ── Preflight guard ──────────────────────────────────────────────────
    max_dollars = budget.get("max_dollars", 0.0)
    if max_dollars <= 0:
        raise ValueError(
            f"BudgetController: max_dollars must be > 0, got {max_dollars}"
        )

    # ── Compute sections_done ────────────────────────────────────────────
    # current_section_idx is 0-based; sections_done = idx + 1 after completion
    sections_done = current_section_idx + 1
    spent = budget.get("spent_dollars", 0.0)

    result: dict = {}

    # ── Re-project final cost §19.5 ─────────────────────────────────────
    if sections_done > 0 and total_sections > 0:
        projected_final = (spent / sections_done) * total_sections
        budget["projected_final"] = round(projected_final, 4)
    # else: skip projection, keep existing projected_final

    # ── Check section anomaly §19.4 ──────────────────────────────────────
    # Calculate section cost from approved_sections if available
    approved_sections = state.get("approved_sections", [])
    section_cost_usd = 0.0
    if approved_sections:
        latest = approved_sections[-1]
        section_cost_usd = latest.get("cost_usd", 0.0)

    anomaly = check_section_anomaly(current_section_idx, section_cost_usd)
    if anomaly is not None:
        result["human_intervention_required"] = True
        result["active_escalation"] = anomaly

    # ── Save previous regime for change detection ────────────────────────
    previous_regime = budget.get("regime", "Balanced")

    # ── Apply dynamic savings §19.4 ──────────────────────────────────────
    budget = apply_dynamic_savings(budget)

    # ── Check if regime should be re-derived ─────────────────────────────
    # If spending pattern significantly changed, re-derive regime from
    # projected budget_per_word
    if total_sections > 0 and sections_done > 0:
        config = state.get("config", {})
        user_cfg = config.get("user", config)
        target_words = user_cfg.get("target_words", 5000)
        remaining_budget = max_dollars - spent
        remaining_words = target_words * (total_sections - sections_done) / total_sections
        if remaining_words > 0:
            effective_bpw = remaining_budget / remaining_words
            new_regime = derive_quality_preset(effective_bpw)

            if new_regime != previous_regime:
                logger.info(
                    "BudgetController: regime change %s → %s "
                    "(effective_bpw=%.6f, spent=%.4f, remaining_budget=%.4f)",
                    previous_regime, new_regime,
                    effective_bpw, spent, remaining_budget,
                )
                budget["regime"] = new_regime

                # Update regime-dependent params
                rp = REGIME_PARAMS[new_regime]
                # Only downgrade, never upgrade after savings applied
                budget["max_iterations"] = min(
                    budget.get("max_iterations", rp["max_iterations"]),
                    rp["max_iterations"],
                )
                budget["jury_size"] = min(
                    budget.get("jury_size", rp["jury_size"]),
                    rp["jury_size"],
                )
                budget["mow_enabled"] = budget.get("mow_enabled", True) and rp["mow_enabled"]

                # Re-populate thresholds from THRESHOLD_TABLE §9.3
                threshold_config = dict(state.get("config", {}))
                threshold_config["_budget_regime_override"] = new_regime
                budget = populate_budget_thresholds(budget, threshold_config)

    # ── Apply floor guards §19.5 ─────────────────────────────────────────
    budget["css_content_threshold"] = max(0.45, budget.get("css_content_threshold", 0.65))
    budget["css_style_threshold"] = max(0.60, budget.get("css_style_threshold", 0.75))
    budget["jury_size"] = max(1, budget.get("jury_size", 1))

    # ── Force-approve check §19.5 ────────────────────────────────────────
    current_iteration = state.get("current_iteration", 0)
    max_iterations = budget.get("max_iterations", 4)
    if current_iteration >= max_iterations:
        logger.warning(
            "FORCE_APPROVE: section_idx=%s reached max_iterations=%s "
            "without CSS convergence. Forcing approval via force_approve flag.",
            current_section_idx, max_iterations,
        )
        result["force_approve"] = True

    # ── Emit SSE event §23.5 ────────────────────────────────────────────
    # SSE push is best-effort; uses redis from state if available
    sse_event = {
        "type": "BUDGET_UPDATE",
        "section_idx": current_section_idx,
        "spent_dollars": round(budget.get("spent_dollars", 0.0), 4),
        "projected_final": round(budget.get("projected_final", 0.0), 4),
        "max_dollars": max_dollars,
        "regime": budget.get("regime", "Balanced"),
        "alarm_70_fired": budget.get("alarm_70_fired", False),
        "alarm_90_fired": budget.get("alarm_90_fired", False),
        "hard_stop_fired": budget.get("hard_stop_fired", False),
    }

    try:
        from src.storage.redis_cache import push_sse_event
        redis = state.get("_redis")  # injected at runtime
        if redis is not None:
            # Fire-and-forget; errors logged inside push_sse_event
            import asyncio
            asyncio.ensure_future(
                push_sse_event(state.get("doc_id", ""), sse_event, redis)
            )
    except Exception:
        logger.debug("SSE push skipped — redis not available", exc_info=True)

    logger.info(
        "BudgetController: section=%d/%d spent=%.4f projected=%.4f "
        "regime=%s alarm_70=%s alarm_90=%s hard_stop=%s",
        sections_done, total_sections,
        budget.get("spent_dollars", 0.0),
        budget.get("projected_final", 0.0),
        budget.get("regime", "?"),
        budget.get("alarm_70_fired", False),
        budget.get("alarm_90_fired", False),
        budget.get("hard_stop_fired", False),
    )

    result["budget"] = budget
    return result
