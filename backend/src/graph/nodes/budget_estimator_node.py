"""LangGraph Node: Budget Estimator (Phase A - Preflight)

Integrates budget_estimator_v2 into the DRS graph workflow per §4.1.

This node:
1. Reads outline from Planner output (DocumentState.outline)
2. Estimates total run cost using budget_estimator_v2
3. Blocks if estimate > 80% of max_budget_dollars
4. Derives regime (Economy/Balanced/Premium) or respects user override
5. Writes BudgetState to DocumentState.budget
6. Emits SSE events for UI progress tracking

Author: DRS Implementation Team
Spec: §4.1 Preflight, §19 Budget Controller
"""

import logging
from typing import Any

from services.budget_estimator_v2 import (
    estimate_run_cost,
    BudgetEstimate,
    Regime,
)
from graph.state import DocumentState, BudgetState
from core.sse import emit_event


logger = logging.getLogger(__name__)


def budget_estimator_node(state: DocumentState) -> dict[str, Any]:
    """LangGraph node: Estimate run cost and set budget constraints.
    
    Input (from DocumentState):
        - outline: List[OutlineSection] from Planner
        - config.target_words: int
        - config.max_budget_dollars: float
        - config.quality_preset: Regime | None (optional override)
    
    Output (updates DocumentState):
        - budget: BudgetState with regime, thresholds, blocked flag
    
    Raises:
        ValueError: If outline is empty or config invalid
    
    SSE Events:
        - BUDGET_ESTIMATING: Start
        - BUDGET_ESTIMATED: Success with breakdown
        - BUDGET_BLOCKED: Estimate exceeds 80% cap
    """
    logger.info("[budget_estimator_node] Starting cost estimation")
    
    # Extract config
    config = state.get("config", {})
    outline = state.get("outline", [])
    doc_id = state.get("doc_id", "unknown")
    
    # Validation
    if not outline:
        raise ValueError(
            "Outline is empty. Planner must run before BudgetEstimator."
        )
    
    target_words = config.get("target_words")
    max_budget = config.get("max_budget_dollars")
    quality_preset = config.get("quality_preset")  # Optional override
    
    if not target_words or target_words < 1000:
        raise ValueError(
            f"Invalid target_words={target_words}. Must be >= 1000."
        )
    
    if not max_budget or max_budget <= 0:
        raise ValueError(
            f"Invalid max_budget_dollars={max_budget}. Must be > 0."
        )
    
    n_sections = len(outline)
    
    # Emit start event
    emit_event(
        doc_id,
        "BUDGET_ESTIMATING",
        {
            "n_sections": n_sections,
            "target_words": target_words,
            "max_budget": max_budget,
        },
    )
    
    # Run estimation
    try:
        estimate: BudgetEstimate = estimate_run_cost(
            n_sections=n_sections,
            target_words=target_words,
            max_budget_usd=max_budget,
            quality_preset=quality_preset,  # None = auto-derive
            avg_iter=None,  # Use regime defaults
            enable_rlm_offload=False,  # TODO: Feature flag from config
        )
    except Exception as e:
        logger.error(f"[budget_estimator_node] Estimation failed: {e}")
        emit_event(
            doc_id,
            "BUDGET_ERROR",
            {"error": str(e), "phase": "estimation"},
        )
        raise
    
    # Log estimate
    logger.info(
        f"[budget_estimator_node] Estimate complete: "
        f"${estimate.estimated_total_usd:.2f} ({estimate.regime} regime)"
    )
    
    # Check blocking condition
    if estimate.blocked:
        logger.warning(
            f"[budget_estimator_node] BLOCKED: {estimate.block_reason}"
        )
        emit_event(
            doc_id,
            "BUDGET_BLOCKED",
            {
                "estimated_usd": estimate.estimated_total_usd,
                "max_budget": max_budget,
                "threshold_pct": 80,
                "reason": estimate.block_reason,
                "regime": estimate.regime,
            },
        )
        
        # Set blocked flag in state
        return {
            "budget": _estimate_to_budget_state(estimate, max_budget, blocked=True),
            "status": "failed",
        }
    
    # Success: emit detailed breakdown
    emit_event(
        doc_id,
        "BUDGET_ESTIMATED",
        {
            "estimated_usd": estimate.estimated_total_usd,
            "cost_per_section": estimate.cost_per_section,
            "regime": estimate.regime,
            "budget_per_word": estimate.budget_per_word,
            "utilization_pct": (estimate.estimated_total_usd / max_budget) * 100,
            "breakdown": {
                "writer": estimate.writer_cost_per_iter,
                "jury": estimate.jury_cost_per_iter,
                "reflector": estimate.reflector_cost_per_iter,
                "researcher": estimate.researcher_cost_per_iter,
                "planner": estimate.planner_cost,
                "panel_contingency": estimate.panel_contingency,
            },
        },
    )
    
    # Return BudgetState for DocumentState
    budget_state = _estimate_to_budget_state(estimate, max_budget, blocked=False)
    
    logger.info(
        f"[budget_estimator_node] Budget approved: "
        f"regime={budget_state['regime']}, "
        f"css_threshold={budget_state['css_threshold']}, "
        f"max_iterations={budget_state['max_iterations']}, "
        f"jury_size={budget_state['jury_size']}"
    )
    
    return {"budget": budget_state}


def _estimate_to_budget_state(
    estimate: BudgetEstimate,
    max_dollars: float,
    blocked: bool,
) -> BudgetState:
    """Convert BudgetEstimate to DocumentState.budget schema per §4.6."""
    from services.budget_estimator_v2 import get_regime_params
    
    regime_params = get_regime_params(estimate.regime)
    
    return {
        # Core budget tracking
        "max_dollars": max_dollars,
        "spent_dollars": 0.0,  # Updated by RealTimeCostTracker
        "projected_final": estimate.estimated_total_usd,
        
        # Regime and adaptive parameters
        "regime": estimate.regime,
        "css_threshold": regime_params["css_threshold"],
        "max_iterations": regime_params["max_iterations"],
        "jury_size": regime_params["jury_size"],
        "mow_enabled": regime_params["mow_enabled"],
        
        # Alarm flags (set by RealTimeCostTracker at runtime)
        "alarm_70_fired": False,
        "alarm_90_fired": False,
        "hardstop_fired": blocked,  # Pre-run block
    }


# Optional: Fallback strategy if budget is too tight
def suggest_budget_fallback(
    target_words: int,
    max_budget: float,
    original_regime: Regime,
) -> dict[str, Any]:
    """Suggest lower regime if budget insufficient.
    
    Returns dict with:
        - fallback_regime: Regime
        - fallback_estimate: BudgetEstimate
        - message: str (human-readable suggestion)
    """
    from services.budget_estimator_v2 import estimate_run_cost
    
    # Try Economy if not already
    if original_regime != "Economy":
        try:
            eco_estimate = estimate_run_cost(
                n_sections=int(target_words / 1000),  # Rough heuristic
                target_words=target_words,
                max_budget_usd=max_budget,
                quality_preset="Economy",
            )
            
            if not eco_estimate.blocked:
                return {
                    "fallback_regime": "Economy",
                    "fallback_estimate": eco_estimate,
                    "message": (
                        f"Budget ${max_budget:.2f} insufficient for {original_regime}. "
                        f"Try Economy regime (${eco_estimate.estimated_total_usd:.2f})."
                    ),
                }
        except Exception as e:
            logger.error(f"Fallback estimation failed: {e}")
    
    # No viable fallback
    return {
        "fallback_regime": None,
        "fallback_estimate": None,
        "message": (
            f"Budget ${max_budget:.2f} insufficient for {target_words} words. "
            f"Minimum recommended: ${max_budget * 1.5:.2f}"
        ),
    }


if __name__ == "__main__":
    # Test node in isolation
    test_state: DocumentState = {
        "doc_id": "test-123",
        "config": {
            "target_words": 8000,
            "max_budget_dollars": 15.0,
            "quality_preset": None,  # Auto-derive
        },
        "outline": [
            {"idx": i, "title": f"Section {i}", "target_words": 1000}
            for i in range(8)
        ],
    }
    
    result = budget_estimator_node(test_state)
    
    print("=" * 80)
    print("Budget Estimator Node Test")
    print("=" * 80)
    print(f"\nBudget State:")
    for key, value in result["budget"].items():
        print(f"  {key}: {value}")
    
    # Test blocking scenario
    print("\n" + "=" * 80)
    print("Testing Blocking Scenario")
    print("=" * 80)
    
    test_state["config"]["max_budget_dollars"] = 5.0  # Too low
    result_blocked = budget_estimator_node(test_state)
    
    if result_blocked.get("status") == "failed":
        print("\n🔴 BLOCKED (expected)")
        print(f"Reason: {result_blocked['budget']['hardstop_fired']}")
    else:
        print("\n⚠️ WARNING: Should have blocked but didn't!")
