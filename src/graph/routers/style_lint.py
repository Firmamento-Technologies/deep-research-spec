"""Route after style linter — §4.5.

Fonte di verità per MAX_STYLE_ITERATIONS.
Importata da style_linter_node per logging coerente.
"""
from __future__ import annotations
from typing import Literal

# Numero massimo di iterazioni del ciclo style_fixer → style_linter.
#
# MOTIVAZIONE: 3 iterazioni coprono il 95% dei casi reali:
#   Iter 1: rimozione contrazioni + first-person (L1, deterministico)
#   Iter 2: fix residui da riscrittura dell'iter 1 + regole L2
#   Iter 3: ultimo pass su violazioni introdotte dal fixer stesso
# Oltre la terza iterazione, il fixer sta quasi certamente oscillando
# su una regola che non riesce a soddisfare stabilmente.
#
# POSIZIONE: il constant deve stare nel router perché è il router
# a prendere la decisione di uscita. style_linter_node importa questa
# costante solo per log coerenti. Non duplicare.
MAX_STYLE_ITERATIONS: int = 3


def route_style_lint(
    state: dict,
) -> Literal["violation", "clean", "max_style_iter"]:
    """Routing post style_linter_node — unico punto decisionale del loop.

    Priorità di valutazione (ordine importante):
      1. ``max_style_iter`` — style_iterations >= MAX_STYLE_ITERATIONS.
         Uscita garantita verso metrics_collector indipendentemente dalle
         violazioni. Le violazioni residue vengono accettate e loggiate
         da metrics_collector_node come warning nei run_metrics.
      2. ``violation``   — violazioni esistono, iter nel budget.
         Loop: route → style_fixer → style_linter.
      3. ``clean``       — nessuna violazione. Uscita verso metrics_collector.

    Args:
        state: DocumentState dict. Legge ``style_iterations`` e
               ``style_lint_violations``.

    Returns:
        Stringa route per add_conditional_edges in graph.py.
        Mappatura: 'violation'      → style_fixer
                   'clean'         → metrics_collector
                   'max_style_iter'→ metrics_collector
    """
    style_iterations: int = state.get("style_iterations", 0)

    # Guardia di terminazione — SEMPRE controllata per prima.
    # Impedisce loop infiniti anche se il fixer introduce nuove violazioni
    # a ogni iterazione (whack-a-mole pattern su regole L1 ambigue).
    if style_iterations >= MAX_STYLE_ITERATIONS:
        return "max_style_iter"

    return "violation" if state.get("style_lint_violations") else "clean"
