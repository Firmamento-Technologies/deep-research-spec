"""Aggregator — CSS computation + routing (§9).

Computes the Composite Scoring System (CSS) from jury verdicts
and determines the routing decision (APPROVED, VETO, FAIL_*, PANEL).

CSS Formula (§9.3):
    css_content = (Σ R_scores × 0.35 + Σ F_scores × 0.50 + Σ S_scores × 0.15) / jury_size
    css_style   = Σ S_scores / jury_size
    css_composite = css_content × 0.70 + css_style × 0.30

Routing (§9.4):
    force_approve → APPROVED (§19.5: max iterations reached)
    css ≥ thresholds + no veto → APPROVED
    veto → VETO
    css_content < 0.50 → PANEL
    css_style < style_threshold → FAIL_STYLE
    missing_evidence → FAIL_MISSING_EV
    else → FAIL_CONTENT (→ reflector)
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def aggregator_node(state: dict) -> dict:
    """Compute CSS and produce aggregator verdict.

    Args:
        state: DocumentState dict with ``jury_verdicts`` and ``budget``.

    Returns:
        Partial state update with ``aggregator_verdict``,
        ``css_content_current``, ``css_style_current``,
        ``css_composite_current``, and ``css_history``.
    """
    verdicts = state.get("jury_verdicts", [])
    budget = state.get("budget", {})

    # Thresholds from budget (§19 preset-dependent)
    css_content_threshold = budget.get("css_content_threshold", 0.70)
    css_style_threshold = budget.get("css_style_threshold", 0.80)

    # Separate by jury type
    r_scores = [v["css_contribution"] for v in verdicts if v.get("judge_slot", "").startswith("R")]
    f_scores = [v["css_contribution"] for v in verdicts if v.get("judge_slot", "").startswith("F")]
    s_scores = [v["css_contribution"] for v in verdicts if v.get("judge_slot", "").startswith("S")]

    jury_size = max(len(r_scores), 1)  # prevent division by zero

    # §9.3 CSS Formula
    css_content = (
        sum(r_scores) * 0.35 + sum(f_scores) * 0.50 + sum(s_scores) * 0.15
    ) / jury_size
    css_style = sum(s_scores) / max(len(s_scores), 1)
    css_composite = css_content * 0.70 + css_style * 0.30

    # §10 Minority Veto check
    veto_verdicts = [v for v in verdicts if v.get("veto_category")]
    veto_triggered = len(veto_verdicts) > 0

    # Missing evidence check
    missing_ev = any(v.get("missing_evidence") for v in verdicts)

    # Dissenting reasons
    dissenting = [
        f"[{v['judge_slot']}] {v.get('motivation', '')}"
        for v in verdicts
        if not v.get("pass_fail", True)
    ]

    # Best elements from passing judges
    best = [
        {"judge": v["judge_slot"], "motivation": v.get("motivation", "")}
        for v in verdicts
        if v.get("pass_fail", False) and v.get("css_contribution", 0) >= 0.80
    ]

    # §9.4 Routing logic
    force_approve = state.get("force_approve", False)

    if force_approve:
        verdict_type = "APPROVED"
    elif veto_triggered:
        verdict_type = "VETO"
    elif css_content >= css_content_threshold and css_style >= css_style_threshold:
        verdict_type = "APPROVED"
    elif css_content < 0.50:
        verdict_type = "PANEL_REQUIRED"
    elif missing_ev and css_content < css_content_threshold:
        verdict_type = "MISSING_EVIDENCE"
    elif css_style < css_style_threshold:
        verdict_type = "FAIL_STYLE"
    elif css_content < css_content_threshold:
        verdict_type = "FAIL_CONTENT"
    else:
        verdict_type = "APPROVED"  # edge case: all pass but individual checks missed

    logger.info(
        "Aggregator: verdict=%s css_content=%.3f css_style=%.3f composite=%.3f veto=%s",
        verdict_type, css_content, css_style, css_composite, veto_triggered,
    )

    # Update css_history (bounded by §29.5 reducer)
    css_history = list(state.get("css_history", []))
    css_history.append(css_composite)

    return {
        "aggregator_verdict": {
            "verdict_type": verdict_type,
            "css_content": round(css_content, 4),
            "css_style": round(css_style, 4),
            "css_composite": round(css_composite, 4),
            "dissenting_reasons": dissenting,
            "best_elements": best,
        },
        "css_content_current": round(css_content, 4),
        "css_style_current": round(css_style, 4),
        "css_composite_current": round(css_composite, 4),
        "css_history": css_history,
    }
