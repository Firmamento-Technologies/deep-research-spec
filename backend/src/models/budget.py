"""Budget types for DRS cost estimation and tracking.

Matches spec definitions in §19.0 (BudgetEstimate) and §19.3 (BudgetState).
"""

from dataclasses import dataclass
from typing import Literal, Optional

Regime = Literal["Economy", "Balanced", "Premium"]


@dataclass
class BudgetEstimate:
    """Pre-run cost estimate with SHINE/RLM awareness.
    
    Produced by budget_estimator_node (§19.1) before any LLM calls.
    """
    # Core estimate
    estimated_total_usd: float
    cost_per_section: float
    regime: Regime
    budget_per_word: float
    
    # Blocking logic
    blocked: bool  # True if estimated_total > max_budget * 0.80
    block_reason: Optional[str]
    
    # --- NEW: SHINE/RLM-aware breakdown ---
    planner_cost: float  # Fixed overhead (Gemini 2.5 Pro)
    researcher_cost_per_section: float
    writer_cost_per_iter: float
    jury_t1_cost_per_iter: float
    jury_t2_cost_per_iter: float  # Only Balanced/Premium
    reflector_cost_per_iter: float
    
    # RLM pattern costs
    recursive_call_factor: float  # 1.0-2.5x for Reflector whack-a-mole
    panel_contingency: float  # Panel Discussion overhead (40% cases)
    compression_savings: float  # Savings from Context/Source Compressor
    
    # Regime parameters derived
    css_threshold: float
    max_iterations: int
    jury_size: int
    mow_enabled: bool


@dataclass
class BudgetState:
    """Real-time budget tracking during run execution.
    
    Updated by RealTimeCostTracker (§19.3) after every LLM call.
    Read by BudgetController (§19.5) to apply dynamic savings strategies.
    """
    # Caps
    max_dollars: float
    spent_dollars: float
    projected_final: float  # Re-projected after each section
    
    # Active regime
    regime: Regime
    
    # Adaptive parameters (mutated by BudgetController)
    css_threshold: float
    max_iterations: int
    jury_size: int
    mow_enabled: bool
    
    # Alarm state (fire once per run)
    alarm_70_fired: bool  # spent >= 70% → downgrade models
    alarm_90_fired: bool  # spent >= 90% → force Economy params
    hard_stop_fired: bool  # spent >= 100% → halt, return partial doc
    
    # Thresholds (for reference, not mutated)
    warn_pct: float = 0.70
    alert_pct: float = 0.90


def derive_regime(budget_per_word: float) -> Regime:
    """Map budget-per-word to regime tier.
    
    Thresholds from §19.2:
    - Economy: < $0.002/word
    - Balanced: $0.002-$0.005/word
    - Premium: > $0.005/word
    """
    if budget_per_word < 0.002:
        return "Economy"
    if budget_per_word <= 0.005:
        return "Balanced"
    return "Premium"


# Regime parameter table (§19.2)
REGIME_PARAMS = {
    "Economy": {
        "css_threshold": 0.65,
        "max_iterations": 2,
        "jury_size": 1,
        "mow_enabled": False,
        "tier1_only": True,
    },
    "Balanced": {
        "css_threshold": 0.70,
        "max_iterations": 4,
        "jury_size": 2,
        "mow_enabled": True,
        "tier1_only": False,
    },
    "Premium": {
        "css_threshold": 0.78,
        "max_iterations": 8,
        "jury_size": 3,
        "mow_enabled": True,
        "tier1_only": False,
    },
}
