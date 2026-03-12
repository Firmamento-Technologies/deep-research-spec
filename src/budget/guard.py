"""Budget Guard — §19.6 pervasive budget enforcement.

Provides check_budget() guard that MUST be called before every expensive
operation (LLM calls, research rounds). When budget is exhausted, raises
BudgetExhaustedError which the graph catches and converts to FORCE_APPROVE.

This guard is the single source of truth for budget enforcement before
any cost-incurring operation.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BudgetExhaustedError(Exception):
    """Raised when budget is exhausted before an expensive operation.
    
    The graph router catches this and sets force_approve=True to skip
    remaining iterations and approve the current section as-is.
    """
    
    def __init__(
        self,
        spent: float,
        max_dollars: float,
        agent: str,
        section_idx: int,
    ):
        self.spent = spent
        self.max_dollars = max_dollars
        self.agent = agent
        self.section_idx = section_idx
        super().__init__(
            f"Budget exhausted: ${spent:.4f} >= ${max_dollars:.2f} "
            f"(agent={agent}, section={section_idx})"
        )


def check_budget(
    state: dict,
    agent: str,
    estimated_cost: float = 0.0,
) -> None:
    """Check if budget allows for an upcoming expensive operation.
    
    MUST be called before:
    - Every llm_client.call() in writer, jury, reflector, panel
    - Every research round in researcher_targeted
    - Any other operation that incurs API costs
    
    Args:
        state: DocumentState dict with budget field.
        agent: Agent name for logging (e.g. "writer", "jury_r1").
        estimated_cost: Optional estimated cost for this operation.
                       If spent + estimated > max, raises immediately.
    
    Raises:
        BudgetExhaustedError: If hard_stop_fired=True OR spent >= max_dollars
                             OR spent + estimated_cost > max_dollars.
    
    Example:
        from src.budget.guard import check_budget, BudgetExhaustedError
        
        try:
            check_budget(state, agent="writer", estimated_cost=0.50)
            response = llm_client.call(...)
        except BudgetExhaustedError:
            logger.warning("Budget exhausted — forcing approval")
            return {"force_approve": True}
    """
    budget = state.get("budget", {})
    spent = budget.get("spent_dollars", 0.0)
    max_dollars = budget.get("max_dollars", 0.0)
    hard_stop = budget.get("hard_stop_fired", False)
    section_idx = state.get("current_section_idx", 0)
    
    # Guard 1: hard_stop_fired flag (set by tracker.py at 100%)
    if hard_stop:
        logger.warning(
            "BudgetGuard: hard_stop_fired=True — blocking %s call "
            "(spent=$%.4f, max=$%.2f, section=%d)",
            agent, spent, max_dollars, section_idx,
        )
        raise BudgetExhaustedError(spent, max_dollars, agent, section_idx)
    
    # Guard 2: current spend >= max
    if spent >= max_dollars:
        logger.warning(
            "BudgetGuard: spent >= max — blocking %s call "
            "(spent=$%.4f, max=$%.2f, section=%d)",
            agent, spent, max_dollars, section_idx,
        )
        raise BudgetExhaustedError(spent, max_dollars, agent, section_idx)
    
    # Guard 3: estimated overage (soft warning, still raises)
    if estimated_cost > 0 and (spent + estimated_cost) > max_dollars:
        logger.warning(
            "BudgetGuard: estimated overage — blocking %s call "
            "(spent=$%.4f + estimated=$%.4f > max=$%.2f, section=%d)",
            agent, spent, estimated_cost, max_dollars, section_idx,
        )
        raise BudgetExhaustedError(spent, max_dollars, agent, section_idx)
    
    # All checks passed
    logger.debug(
        "BudgetGuard: OK for %s (spent=$%.4f / $%.2f, remaining=$%.4f)",
        agent, spent, max_dollars, max_dollars - spent,
    )


# Alias used by panel_discussion and other callers
check_budget_before_call = check_budget
