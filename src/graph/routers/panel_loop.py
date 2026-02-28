"""Route after panel discussion — §9.5.

ALTA-07 — Escape guarantee:
  Il router esce verso 'aggregator' in due casi:

  1. ``force_approve=True`` nel state (impostato da panel_discussion_node
     quando max_rounds è raggiunto). Questo è il percorso primario.

  2. ``panel_round >= get_max_panel_rounds(state)`` come guard
     belt-and-suspenders nel caso force_approve non sia stato impostato
     correttamente (difesa in profondità).

Usa ``get_max_panel_rounds()`` da panel_discussion.py come FONTE DI
VERITÀ UNICA per il limite — nodo e router usano sempre lo stesso valore.
"""
from __future__ import annotations

from typing import Literal

from src.graph.nodes.panel_discussion import get_max_panel_rounds


def route_after_panel_internal(
    state: dict,
) -> Literal["panel_discussion", "aggregator"]:
    """Self-loop or return to aggregator after panel round. §9.5.

    Decision tree:
      1. force_approve=True  → aggregator (escape, max rounds reached)
      2. panel_round >= max  → aggregator (belt-and-suspenders guard)
      3. otherwise           → panel_discussion (continua il loop)

    Returns:
        'aggregator' to re-evaluate CSS with updated verdicts, or
        'panel_discussion' if additional rounds remain.
    """
    # ------------------------------------------------------------------
    # Guard 1 (primario): force_approve impostato da panel_discussion_node
    # Questo è il percorso normale quando max_rounds è raggiunto.
    # ------------------------------------------------------------------
    if state.get("force_approve", False):
        return "aggregator"

    # ------------------------------------------------------------------
    # Guard 2 (belt-and-suspenders): check numerico diretto.
    # Usa get_max_panel_rounds() — stessa fonte di verità del nodo.
    # Difende da edge case in cui force_approve non fosse stato impostato
    # (es. crash parziale del nodo, resume da checkpoint stale).
    # ------------------------------------------------------------------
    max_rounds: int = get_max_panel_rounds(state)
    if state.get("panel_round", 0) >= max_rounds:
        return "aggregator"

    return "panel_discussion"
