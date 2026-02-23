"""Panel Discussion node (§11) — structured multi-agent debate.

Triggers when CSS < panel_threshold (typically 0.50).
Multiple judge perspectives debate the draft quality to reach
consensus or identify the core issue blocking approval.

The panel self-loops (via ``route_after_panel_internal``) until
max rounds reached, then routes back to aggregator with
updated verdicts.
"""
from __future__ import annotations

import logging
from typing import Any

from src.llm.client import llm_client

logger = logging.getLogger(__name__)

# Max rounds before panel exits
_DEFAULT_MAX_ROUNDS = 2


def panel_discussion_node(state: dict) -> dict:
    """Run one round of panel discussion.

    Args:
        state: DocumentState dict with ``current_draft``,
               ``jury_verdicts``, ``panel_round``, ``panel_anonymized_log``.

    Returns:
        Partial state update with incremented ``panel_round``,
        updated ``panel_anonymized_log``, and potentially revised
        ``jury_verdicts``.
    """
    draft = state.get("current_draft", "")
    verdicts = state.get("jury_verdicts", [])
    panel_round = state.get("panel_round", 0)
    panel_log = list(state.get("panel_anonymized_log", []))

    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])
    section_scope = (
        outline[section_idx]["scope"]
        if section_idx < len(outline)
        else ""
    )

    # Build context from previous verdicts
    verdict_summary = _summarize_verdicts(verdicts)

    # Previous panel rounds
    prior_discussion = ""
    if panel_log:
        prior_discussion = "\n\n".join(
            f"Round {entry['round']}: {entry['summary']}"
            for entry in panel_log[-3:]
        )

    logger.info(
        "Panel Discussion round %d for section %d",
        panel_round + 1, section_idx,
    )

    # Run panel debate via LLM
    discussion_result = _run_panel_round(
        draft=draft,
        section_scope=section_scope,
        verdict_summary=verdict_summary,
        prior_discussion=prior_discussion,
        round_num=panel_round + 1,
    )

    # Log the round
    panel_log.append({
        "round": panel_round + 1,
        "summary": discussion_result.get("summary", ""),
        "consensus": discussion_result.get("consensus", None),
        "key_issues": discussion_result.get("key_issues", []),
    })

    # Update verdicts if panel reached consensus on specific issues
    updated_verdicts = verdicts
    if discussion_result.get("revised_scores"):
        updated_verdicts = _apply_panel_revisions(
            verdicts, discussion_result["revised_scores"],
        )

    return {
        "panel_round": panel_round + 1,
        "panel_active": True,
        "panel_anonymized_log": panel_log,
        "jury_verdicts": updated_verdicts,
    }


def _summarize_verdicts(verdicts: list[dict]) -> str:
    """Summarize jury verdicts for panel context."""
    lines = []
    for v in verdicts:
        slot = v.get("judge_slot", "?")
        passed = "PASS" if v.get("pass_fail") else "FAIL"
        css = v.get("css_contribution", 0)
        motivation = v.get("motivation", "")[:100]
        lines.append(f"[{slot}] {passed} (CSS={css:.2f}): {motivation}")
    return "\n".join(lines)


def _run_panel_round(
    draft: str,
    section_scope: str,
    verdict_summary: str,
    prior_discussion: str,
    round_num: int,
) -> dict:
    """Run one round of panel discussion via LLM."""
    try:
        system_blocks = [
            {
                "type": "text",
                "text": """\
You are moderating a panel discussion between multiple judges evaluating
a document section. Your role is to:
1. Identify the core disagreements between judges
2. Facilitate constructive debate
3. Determine if consensus can be reached
4. Identify the single most critical issue blocking approval

Return your analysis as structured text with these sections:
SUMMARY: 1-2 sentence overview of the discussion
CONSENSUS: YES/NO/PARTIAL
KEY_ISSUES: numbered list of unresolved issues
REVISED_SCORES: only if consensus changes scores, format: SLOT=NEW_SCORE""",
                "cache_control": {"type": "ephemeral"},
            },
        ]

        prior_ctx = f"\n\nPrior discussion:\n{prior_discussion}" if prior_discussion else ""

        response = llm_client.call(
            model="google/gemini-2.5-flash",
            system=system_blocks,
            messages=[{
                "role": "user",
                "content": f"""\
Panel Discussion Round {round_num}

Section scope: {section_scope}

Jury verdicts:
{verdict_summary}
{prior_ctx}

Draft excerpt (first 2000 chars):
{draft[:2000]}

Facilitate the panel discussion and provide your structured analysis.""",
            }],
            temperature=0.3,
            max_tokens=2048,
        )

        return _parse_panel_response(response["text"])

    except Exception as exc:
        logger.warning("Panel discussion LLM call failed: %s", exc)
        return {
            "summary": f"Panel round {round_num} failed: {exc}",
            "consensus": None,
            "key_issues": [],
            "revised_scores": {},
        }


def _parse_panel_response(text: str) -> dict:
    """Parse structured panel discussion response."""
    result = {
        "summary": "",
        "consensus": None,
        "key_issues": [],
        "revised_scores": {},
    }

    lines = text.split("\n")
    current_section = None

    for line in lines:
        line = line.strip()
        if line.startswith("SUMMARY:"):
            result["summary"] = line[len("SUMMARY:"):].strip()
            current_section = "summary"
        elif line.startswith("CONSENSUS:"):
            val = line[len("CONSENSUS:"):].strip().upper()
            result["consensus"] = val if val in ("YES", "NO", "PARTIAL") else None
        elif line.startswith("KEY_ISSUES:"):
            current_section = "key_issues"
        elif line.startswith("REVISED_SCORES:"):
            current_section = "revised_scores"
        elif current_section == "key_issues" and line:
            issue = line.lstrip("0123456789.-) ")
            if issue:
                result["key_issues"].append(issue)
        elif current_section == "revised_scores" and "=" in line:
            parts = line.split("=")
            if len(parts) == 2:
                try:
                    result["revised_scores"][parts[0].strip()] = float(parts[1].strip())
                except ValueError:
                    pass

    return result


def _apply_panel_revisions(
    verdicts: list[dict], revised_scores: dict[str, float],
) -> list[dict]:
    """Apply panel-revised scores to verdicts."""
    updated = []
    for v in verdicts:
        v_copy = dict(v)
        slot = v_copy.get("judge_slot", "")
        if slot in revised_scores:
            v_copy["css_contribution"] = revised_scores[slot]
            v_copy["motivation"] = f"[Panel revised] {v_copy.get('motivation', '')}"
            logger.info("Panel revised %s score to %.2f", slot, revised_scores[slot])
        updated.append(v_copy)
    return updated
