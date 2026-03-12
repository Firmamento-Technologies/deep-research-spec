"""Budget subsystem — §19 canonical.

Public API for budget estimation, cost tracking, threshold management,
and dynamic savings strategies.
"""
from src.budget.regime import (
    THRESHOLD_TABLE,
    REGIME_PARAMS,
    JURY_WEIGHTS,
    derive_quality_preset,
    populate_budget_thresholds,
)
from src.budget.estimator import (
    BudgetEstimate,
    estimate_run_cost,
    budget_estimator_node,
)
from src.budget.tracker import (
    CostEntryData,
    apply_dynamic_savings,
    record_cost_entry,
    check_section_anomaly,
    format_alarm_70,
    format_alarm_90,
    format_alarm_hard_stop,
    format_alarm_section_anomaly,
)
from src.budget.thresholds import (
    get_thresholds_for_regime,
    validate_threshold_invariants,
)

__all__ = [
    # regime.py
    "THRESHOLD_TABLE",
    "REGIME_PARAMS",
    "JURY_WEIGHTS",
    "derive_quality_preset",
    "populate_budget_thresholds",
    # estimator.py
    "BudgetEstimate",
    "estimate_run_cost",
    "budget_estimator_node",
    # tracker.py
    "CostEntryData",
    "apply_dynamic_savings",
    "record_cost_entry",
    "check_section_anomaly",
    "format_alarm_70",
    "format_alarm_90",
    "format_alarm_hard_stop",
    "format_alarm_section_anomaly",
    # thresholds.py
    "get_thresholds_for_regime",
    "validate_threshold_invariants",
]
