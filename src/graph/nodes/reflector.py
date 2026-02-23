"""Reflector agent (§5.14) — analyse jury feedback and produce fix plan.

Takes jury verdicts + aggregator verdict and produces a
``ReflectorOutput`` with:
- ``dominant_scope``: SURGICAL / PARTIAL / FULL
- ``feedback_items``: actionable fix instructions for Writer

Routing (via ``route_after_reflector``):
- FULL → await_human (argument structurally broken)
- SURGICAL/PARTIAL → oscillation_check → writer/span_editor
"""
from __future__ import annotations

import logging
from typing import Any

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


def reflector_node(state: dict) -> dict:
    """Analyse jury feedback and produce improvement plan.

    Args:
        state: DocumentState dict with ``jury_verdicts``,
               ``aggregator_verdict``, ``current_draft``.

    Returns:
        Partial state update with ``reflector_output``.
    """
    verdicts = state.get("jury_verdicts", [])
    agg = state.get("aggregator_verdict", {})
    draft = state.get("current_draft", "")
    section_idx = state.get("current_section_idx", 0)

    # Collect failing verdicts
    failures = [v for v in verdicts if not v.get("pass_fail", True)]
    failed_claims = []
    missing_evidence = []
    for v in verdicts:
        failed_claims.extend(v.get("failed_claims", []))
        missing_evidence.extend(v.get("missing_evidence", []))

    # Determine scope based on failure severity
    scope = _classify_scope(agg, failures, failed_claims)

    # Build feedback items
    if failures:
        feedback_items = _build_feedback_from_verdicts(failures, failed_claims, missing_evidence)
    else:
        # Aggregator failed but individual judges didn't flag specifics
        feedback_items = _build_generic_feedback(agg)

    # Optional: use LLM for detailed analysis if PARTIAL/FULL
    if scope in ("PARTIAL", "FULL") and draft:
        preset = state.get("quality_preset", "balanced")
        llm_feedback = _get_llm_feedback(draft, failures, scope, preset)
        if llm_feedback:
            feedback_items.extend(llm_feedback)

    logger.info(
        "Reflector: scope=%s, %d feedback items for section %d",
        scope, len(feedback_items), section_idx,
    )

    return {
        "reflector_output": {
            "scope": scope,
            "dominant_scope": scope,
            "feedback_items": feedback_items,
        },
    }


def _classify_scope(
    agg: dict, failures: list[dict], failed_claims: list[str],
) -> str:
    """Classify revision scope: SURGICAL, PARTIAL, or FULL.

    SURGICAL: 1-2 specific claims need fixing (<10% of draft)
    PARTIAL:  Multiple issues but structure is sound
    FULL:     Fundamental restructuring needed (rare → await_human)
    """
    verdict_type = agg.get("verdict_type", "")
    css_content = agg.get("css_content", 0.0)

    # FULL: CSS very low or veto on structure
    if css_content < 0.35 or verdict_type == "VETO":
        return "FULL"

    # SURGICAL: few specific claims, CSS close to threshold
    if len(failed_claims) <= 2 and css_content >= 0.55:
        return "SURGICAL"

    # Default: PARTIAL
    return "PARTIAL"


def _build_feedback_from_verdicts(
    failures: list[dict],
    failed_claims: list[str],
    missing_evidence: list[str],
) -> list[dict]:
    """Build actionable feedback items from judge failures."""
    items = []

    for claim in failed_claims:
        items.append({
            "type": "failed_claim",
            "description": claim,
            "action": "revise_or_remove",
            "priority": "high",
        })

    for ev in missing_evidence:
        items.append({
            "type": "missing_evidence",
            "description": ev,
            "action": "add_citation",
            "priority": "medium",
        })

    for v in failures:
        if v.get("motivation"):
            items.append({
                "type": "judge_feedback",
                "judge": v.get("judge_slot", "?"),
                "description": v["motivation"],
                "action": "address_feedback",
                "priority": "medium",
            })

    return items


def _build_generic_feedback(agg: dict) -> list[dict]:
    """Build generic feedback when verdicts lack specifics."""
    items = []
    css_content = agg.get("css_content", 0.0)
    css_style = agg.get("css_style", 0.0)

    if css_content < 0.70:
        items.append({
            "type": "content_quality",
            "description": f"Content CSS={css_content:.2f} below threshold. Improve reasoning and evidence.",
            "action": "improve_content",
            "priority": "high",
        })

    if css_style < 0.80:
        items.append({
            "type": "style_quality",
            "description": f"Style CSS={css_style:.2f} below threshold. Improve writing quality.",
            "action": "improve_style",
            "priority": "medium",
        })

    if not items:
        items.append({
            "type": "general",
            "description": "Improve overall quality to meet threshold.",
            "action": "revise",
            "priority": "medium",
        })

    return items


def _get_llm_feedback(
    draft: str, failures: list[dict], scope: str, quality_preset: str = "balanced",
) -> list[dict]:
    """Use LLM to generate detailed improvement suggestions."""
    try:
        failure_summary = "\n".join(
            f"- [{v.get('judge_slot', '?')}] {v.get('motivation', 'No details')}"
            for v in failures[:5]
        )

        response = llm_client.call(
            model=route_model("reflector", quality_preset),
            messages=[{
                "role": "user",
                "content": f"""\
Analyse these jury failures and suggest specific fixes.
Scope: {scope}

Failures:
{failure_summary}

Draft excerpt (first 2000 chars):
{draft[:2000]}

Return 2-5 concise fix suggestions as a numbered list.
Each suggestion should be actionable (what to change and where).""",
            }],
            temperature=0.2,
            max_tokens=1024,
        )

        # Parse numbered list into feedback items
        items = []
        for line in response["text"].split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                items.append({
                    "type": "llm_suggestion",
                    "description": line.lstrip("0123456789.-) "),
                    "action": "apply_suggestion",
                    "priority": "medium",
                })

        return items[:5]

    except Exception as exc:
        logger.warning("Reflector LLM analysis failed: %s", exc)
        return []
