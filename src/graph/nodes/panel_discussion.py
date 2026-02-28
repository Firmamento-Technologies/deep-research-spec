"""Panel Discussion node (§11) — structured multi-agent debate.

Triggers when CSS < panel_threshold (typically 0.50).
Multiple judge perspectives debate the draft quality to reach
consensus or identify the core issue blocking approval.

The panel self-loops (via ``route_after_panel_internal``) until
max rounds reached, then routes back to aggregator with
updated verdicts.

ALTA-07 — Escape guarantee:
  ``get_max_panel_rounds(state)`` è la FONTE DI VERITÀ UNICA per il
  limite di round. Importata da panel_loop.py per garantire che nodo
  e router usino sempre lo stesso valore.

  Quando ``new_round_num >= max_rounds``, il nodo imposta
  ``force_approve=True`` nel return. Il router lo intercetta e
  indirizza verso aggregator senza ulteriori round.
"""
from __future__ import annotations

import logging
from typing import Any

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ALTA-07 — MAX_PANEL_ROUNDS: costante esportata (fonte di verità)
# ---------------------------------------------------------------------------
# Valore di default usato quando né budget["max_iterations"] né
# config.convergence.panel_max_rounds sono configurati.
#
# NON usare questo valore direttamente: usa get_max_panel_rounds(state)
# che implementa la priority chain completa.
#
# Importata da panel_loop.py — non rinominare senza aggiornare quel file.
MAX_PANEL_ROUNDS: int = 3


def get_max_panel_rounds(state: dict) -> int:
    """Return the effective max panel rounds for this run.

    Priority order (first valid int > 0 wins):

    1. ``state["budget"]["max_iterations"]`` — impostato da budget_estimator
       in base al regime (Economy/Balanced/Premium). Fonte autorevole
       per tutti i limiti di iterazione del sistema.

    2. ``state["config"]["convergence"]["panel_max_rounds"]`` — override
       esplicito per operatori che vogliono un limite panel diverso
       dal max_iterations globale.

    3. ``MAX_PANEL_ROUNDS`` (3) — fallback se nessuna configurazione
       è disponibile (test, run manuali, ambienti di sviluppo).

    Questa funzione è importata da panel_loop.py per garantire che
    nodo e router usino SEMPRE lo stesso valore.
    """
    # Priority 1: budget-derived max_iterations (fonte autorevole)
    budget_max = state.get("budget", {}).get("max_iterations")
    if isinstance(budget_max, int) and budget_max > 0:
        return budget_max

    # Priority 2: config override esplicito
    config_max = (
        state.get("config", {})
        .get("convergence", {})
        .get("panel_max_rounds")
    )
    if isinstance(config_max, int) and config_max > 0:
        return config_max

    return MAX_PANEL_ROUNDS


def panel_discussion_node(state: dict) -> dict:
    """Run one round of panel discussion.

    Args:
        state: DocumentState dict with ``current_draft``,
               ``jury_verdicts``, ``panel_round``, ``panel_anonymized_log``.

    Returns:
        Partial state update with incremented ``panel_round``,
        updated ``panel_anonymized_log``, potentially revised
        ``jury_verdicts``, and ``force_approve=True`` when
        max rounds are exhausted (ALTA-07 escape guarantee).
    """
    draft: str = state.get("current_draft", "")
    verdicts: list[dict] = state.get("jury_verdicts", [])
    panel_round: int = state.get("panel_round", 0)
    panel_log: list[dict] = list(state.get("panel_anonymized_log", []))
    # ALTA-07 fix: quality_preset estratto qui nel scope corretto
    # e passato esplicitamente a _run_panel_round() (fix NameError)
    quality_preset: str = state.get("quality_preset", "balanced")

    section_idx: int = state.get("current_section_idx", 0)
    outline: list[dict] = state.get("outline", [])
    section_scope: str = (
        outline[section_idx]["scope"]
        if section_idx < len(outline)
        else ""
    )

    max_rounds: int = get_max_panel_rounds(state)
    new_round_num: int = panel_round + 1

    # Build context from previous verdicts
    verdict_summary = _summarize_verdicts(verdicts)

    # Previous panel rounds (last 3 only, per context budget)
    prior_discussion = ""
    if panel_log:
        prior_discussion = "\n\n".join(
            f"Round {entry['round']}: {entry['summary']}"
            for entry in panel_log[-3:]
        )

    logger.info(
        "Panel Discussion round %d/%d for section %d",
        new_round_num, max_rounds, section_idx,
    )

    # Run panel debate via LLM
    discussion_result = _run_panel_round(
        draft=draft,
        section_scope=section_scope,
        verdict_summary=verdict_summary,
        prior_discussion=prior_discussion,
        round_num=new_round_num,
        quality_preset=quality_preset,  # fix NameError: ora nel scope
    )

    # Log the round
    panel_log.append({
        "round": new_round_num,
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

    # ------------------------------------------------------------------
    # ALTA-07 — Escape guarantee
    #
    # Quando max_rounds è raggiunto, force_approve=True viene impostato
    # PRIMA che il router venga chiamato. Il router (panel_loop.py)
    # intercetta force_approve=True e indirizza verso aggregator
    # immediatamente, senza ulteriori round.
    #
    # Questo è un override one-shot: section_checkpoint.py resetta
    # force_approve=False all'inizio di ogni nuova sezione (ALTA-05).
    # ------------------------------------------------------------------
    force_approve = False
    if new_round_num >= max_rounds:
        logger.warning(
            "[panel] MAX_PANEL_ROUNDS (%d) reached for section %d — "
            "force_approve=True to prevent infinite loop. "
            "Unresolved issues: %s",
            max_rounds,
            section_idx,
            discussion_result.get("key_issues", []),
        )
        force_approve = True

    return {
        "panel_round": new_round_num,
        "panel_active": True,
        "panel_anonymized_log": panel_log,
        "jury_verdicts": updated_verdicts,
        "force_approve": force_approve,
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
    quality_preset: str = "balanced",  # ALTA-07 fix: era acceduto come
                                        # state.get() dentro questo scope
                                        # → NameError silenzioso
) -> dict:
    """Run one round of panel discussion via LLM.

    Args:
        draft: Current section draft text.
        section_scope: Expected scope/requirements for this section.
        verdict_summary: Formatted string of current jury verdicts.
        prior_discussion: Summary of previous panel rounds (last 3).
        round_num: Current round number (1-based).
        quality_preset: LLM preset for model routing (default 'balanced').
    """
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
            model=route_model("panel_discussion", quality_preset),
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
            agent="panel_discussion",
            preset=quality_preset,
        )

        return _parse_panel_response(response["text"])

    except Exception as exc:  # noqa: BLE001
        logger.warning("Panel discussion LLM call failed: %s", exc)
        return {
            "summary": f"Panel round {round_num} failed: {exc}",
            "consensus": None,
            "key_issues": [],
            "revised_scores": {},
        }


def _parse_panel_response(text: str) -> dict:
    """Parse structured panel discussion response."""
    result: dict[str, Any] = {
        "summary": "",
        "consensus": None,
        "key_issues": [],
        "revised_scores": {},
    }

    lines = text.split("\n")
    current_section: str | None = None

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
