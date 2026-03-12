#!/usr/bin/env python3
"""Phase 3 validation — Budget & Thresholds.

Verifies all budget subsystem components:
  - THRESHOLD_TABLE values (§9.3)
  - REGIME_PARAMS values (§19.2)
  - estimate_run_cost() returns BudgetEstimate (§19.0)
  - apply_dynamic_savings() logic at 70%/90%/100% (§19.4)
  - populate_budget_thresholds() populates correctly (§9.3)
  - budget_controller_node importable (§19.5)
  - Threshold invariants (§9.3)
  - budget_estimator_node() initializes BudgetState correctly
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

errors: list[str] = []
passed: int = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed
    if condition:
        passed += 1
        print(f"  ✅ {label}")
    else:
        msg = f"  ❌ {label}" + (f" — {detail}" if detail else "")
        print(msg)
        errors.append(msg)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 1. THRESHOLD_TABLE (§9.3) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.regime import THRESHOLD_TABLE, REGIME_PARAMS

check("economy in THRESHOLD_TABLE", "economy" in THRESHOLD_TABLE)
check("balanced in THRESHOLD_TABLE", "balanced" in THRESHOLD_TABLE)
check("premium in THRESHOLD_TABLE", "premium" in THRESHOLD_TABLE)

check(
    "economy css_content_threshold == 0.65",
    THRESHOLD_TABLE["economy"]["css_content_threshold"] == 0.65,
    f"got {THRESHOLD_TABLE['economy']['css_content_threshold']}",
)
check(
    "economy css_style_threshold == 0.75",
    THRESHOLD_TABLE["economy"]["css_style_threshold"] == 0.75,
    f"got {THRESHOLD_TABLE['economy']['css_style_threshold']}",
)
check(
    "economy css_panel_trigger == 0.40",
    THRESHOLD_TABLE["economy"]["css_panel_trigger"] == 0.40,
    f"got {THRESHOLD_TABLE['economy']['css_panel_trigger']}",
)

check(
    "balanced css_content_threshold == 0.70",
    THRESHOLD_TABLE["balanced"]["css_content_threshold"] == 0.70,
)
check(
    "balanced css_style_threshold == 0.80",
    THRESHOLD_TABLE["balanced"]["css_style_threshold"] == 0.80,
)
check(
    "balanced css_panel_trigger == 0.50",
    THRESHOLD_TABLE["balanced"]["css_panel_trigger"] == 0.50,
)

check(
    "premium css_content_threshold == 0.78",
    THRESHOLD_TABLE["premium"]["css_content_threshold"] == 0.78,
)
check(
    "premium css_style_threshold == 0.85",
    THRESHOLD_TABLE["premium"]["css_style_threshold"] == 0.85,
)
check(
    "premium css_panel_trigger == 0.55",
    THRESHOLD_TABLE["premium"]["css_panel_trigger"] == 0.55,
)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 2. REGIME_PARAMS (§19.2) ═══")
# ═══════════════════════════════════════════════════════════════════════════

check("Economy in REGIME_PARAMS", "Economy" in REGIME_PARAMS)
check("Balanced in REGIME_PARAMS", "Balanced" in REGIME_PARAMS)
check("Premium in REGIME_PARAMS", "Premium" in REGIME_PARAMS)

check(
    "Economy max_iterations == 2",
    REGIME_PARAMS["Economy"]["max_iterations"] == 2,
    f"got {REGIME_PARAMS['Economy']['max_iterations']}",
)
check(
    "Economy jury_size == 1",
    REGIME_PARAMS["Economy"]["jury_size"] == 1,
)
check(
    "Economy mow_enabled == False",
    REGIME_PARAMS["Economy"]["mow_enabled"] is False,
)

check(
    "Balanced max_iterations == 4",
    REGIME_PARAMS["Balanced"]["max_iterations"] == 4,
)
check(
    "Balanced jury_size == 2",
    REGIME_PARAMS["Balanced"]["jury_size"] == 2,
)
check(
    "Balanced mow_enabled == True",
    REGIME_PARAMS["Balanced"]["mow_enabled"] is True,
)

check(
    "Premium max_iterations == 8",
    REGIME_PARAMS["Premium"]["max_iterations"] == 8,
)
check(
    "Premium jury_size == 3",
    REGIME_PARAMS["Premium"]["jury_size"] == 3,
)
check(
    "Premium mow_enabled == True",
    REGIME_PARAMS["Premium"]["mow_enabled"] is True,
)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 3. derive_quality_preset (§19.2) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.regime import derive_quality_preset

check("bpw < 0.002 → Economy", derive_quality_preset(0.001) == "Economy")
check("bpw == 0.002 → Balanced", derive_quality_preset(0.002) == "Balanced")
check("bpw == 0.005 → Balanced", derive_quality_preset(0.005) == "Balanced")
check("bpw > 0.005 → Premium", derive_quality_preset(0.006) == "Premium")


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 4. estimate_run_cost (§19.0) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.estimator import estimate_run_cost, BudgetEstimate

est = estimate_run_cost(n_sections=10, target_words=5000, max_budget_usd=50.0)
check("returns BudgetEstimate", isinstance(est, BudgetEstimate))
check("estimated_total_usd > 0", est.estimated_total_usd > 0)
check("cost_per_section > 0", est.cost_per_section > 0)
check("regime is valid", est.regime in ("Economy", "Balanced", "Premium"))
check("budget_per_word > 0", est.budget_per_word > 0)
check("blocked is bool", isinstance(est.blocked, bool))

# Test blocking: very small budget
est_blocked = estimate_run_cost(n_sections=10, target_words=5000, max_budget_usd=0.001)
check("tiny budget → blocked=True", est_blocked.blocked is True)
check("block_reason is set", est_blocked.block_reason is not None)

# Test ValueError on 0 sections
try:
    estimate_run_cost(n_sections=0, target_words=5000, max_budget_usd=50.0)
    check("n_sections=0 raises ValueError", False, "no exception raised")
except ValueError:
    check("n_sections=0 raises ValueError", True)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 5. apply_dynamic_savings (§19.4) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.tracker import apply_dynamic_savings

# Base budget for testing
def _make_budget(**overrides) -> dict:
    base = {
        "max_dollars": 100.0,
        "spent_dollars": 0.0,
        "projected_final": 0.0,
        "regime": "Balanced",
        "css_content_threshold": 0.70,
        "css_style_threshold": 0.80,
        "css_panel_threshold": 0.50,
        "max_iterations": 4,
        "jury_size": 2,
        "mow_enabled": True,
        "alarm_70_fired": False,
        "alarm_90_fired": False,
        "hard_stop_fired": False,
    }
    base.update(overrides)
    return base


# 70% trigger
b70 = _make_budget(spent_dollars=72.0)
r70 = apply_dynamic_savings(b70)
check("70%: alarm_70_fired=True", r70["alarm_70_fired"] is True)
check("70%: jury_size decremented", r70["jury_size"] == 1, f"got {r70['jury_size']}")
check("70%: alarm_90_fired still False", r70["alarm_90_fired"] is False)
check("70%: hard_stop_fired still False", r70["hard_stop_fired"] is False)

# 90% trigger
b90 = _make_budget(spent_dollars=92.0)
r90 = apply_dynamic_savings(b90)
check("90%: alarm_90_fired=True", r90["alarm_90_fired"] is True)
check("90%: css_content_threshold=0.65", r90["css_content_threshold"] == 0.65)
check("90%: css_style_threshold=0.75", r90["css_style_threshold"] == 0.75)
check("90%: max_iterations=1", r90["max_iterations"] == 1)
check("90%: jury_size=1", r90["jury_size"] == 1)
check("90%: mow_enabled=False", r90["mow_enabled"] is False)

# 100% trigger
b100 = _make_budget(spent_dollars=105.0)
r100 = apply_dynamic_savings(b100)
check("100%: hard_stop_fired=True", r100["hard_stop_fired"] is True)

# Idempotency: alarm fires only once
b70_refired = _make_budget(spent_dollars=72.0, alarm_70_fired=True)
r70_re = apply_dynamic_savings(b70_refired)
check("70% already fired: jury_size unchanged", r70_re["jury_size"] == b70_refired["jury_size"])

# Floor guards
b_floor = _make_budget(spent_dollars=0.0, css_content_threshold=0.30, css_style_threshold=0.50, jury_size=0)
r_floor = apply_dynamic_savings(b_floor)
check("floor: css_content >= 0.45", r_floor["css_content_threshold"] >= 0.45)
check("floor: css_style >= 0.60", r_floor["css_style_threshold"] >= 0.60)
check("floor: jury_size >= 1", r_floor["jury_size"] >= 1)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 6. populate_budget_thresholds (§9.3) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.regime import populate_budget_thresholds

budget_econ = _make_budget()
config_econ = {"_budget_regime_override": "Economy"}
result_econ = populate_budget_thresholds(budget_econ, config_econ)

check("populate Economy: css_content=0.65", result_econ["css_content_threshold"] == 0.65)
check("populate Economy: css_style=0.75", result_econ["css_style_threshold"] == 0.75)
check("populate Economy: css_panel=0.40", result_econ["css_panel_threshold"] == 0.40)

budget_prem = _make_budget()
config_prem = {"_budget_regime_override": "Premium"}
result_prem = populate_budget_thresholds(budget_prem, config_prem)

check("populate Premium: css_content=0.78", result_prem["css_content_threshold"] == 0.78)
check("populate Premium: css_style=0.85", result_prem["css_style_threshold"] == 0.85)
check("populate Premium: css_panel=0.55", result_prem["css_panel_threshold"] == 0.55)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 7. Threshold invariants (§9.3) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.thresholds import validate_threshold_invariants, get_thresholds_for_regime

violations = validate_threshold_invariants()
check("all threshold invariants pass", len(violations) == 0, str(violations))

for regime in ("Economy", "Balanced", "Premium"):
    t = get_thresholds_for_regime(regime)
    check(f"get_thresholds_for_regime({regime}) has 3 keys", len(t) == 3)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 8. Section anomaly check (§19.4) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.tracker import check_section_anomaly

check("cost < $15 → None", check_section_anomaly(0, 10.0) is None)
anomaly = check_section_anomaly(3, 20.0)
check("cost > $15 → escalation dict", anomaly is not None)
check("anomaly type=budget_section_anomaly", anomaly["type"] == "budget_section_anomaly")
check("anomaly requires_human=True", anomaly["requires_human"] is True)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 9. budget_estimator_node (§19.1) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.estimator import budget_estimator_node

test_state = {
    "config": {
        "user": {
            "target_words": 5000,
            "max_budget_dollars": 50.0,
            "quality_preset": "balanced",
        }
    },
    "outline": [
        {"idx": i, "title": f"Section {i}", "scope": "test", "target_words": 500, "dependencies": []}
        for i in range(10)
    ],
}

result_node = budget_estimator_node(test_state)
check("budget_estimator_node returns dict", isinstance(result_node, dict))
check("result has 'budget' key", "budget" in result_node)

b = result_node["budget"]
check("budget.regime is set", b.get("regime") in ("Economy", "Balanced", "Premium"))
check("budget.max_dollars == 50.0", b.get("max_dollars") == 50.0)
check("budget.spent_dollars == 0.0", b.get("spent_dollars") == 0.0)
check("budget.css_content_threshold > 0", b.get("css_content_threshold", 0) > 0)
check("budget.css_style_threshold > 0", b.get("css_style_threshold", 0) > 0)
check("budget.css_panel_threshold > 0", b.get("css_panel_threshold", 0) > 0)
check("budget.alarm_70_fired == False", b.get("alarm_70_fired") is False)
check("budget.alarm_90_fired == False", b.get("alarm_90_fired") is False)
check("budget.hard_stop_fired == False", b.get("hard_stop_fired") is False)


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 10. budget_controller_node importable (§19.5) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.graph.nodes.budget_controller import budget_controller_node
import inspect

check("budget_controller_node importable", callable(budget_controller_node))
check("budget_controller_node is async", inspect.iscoroutinefunction(budget_controller_node))


# ═══════════════════════════════════════════════════════════════════════════
print("\n═══ 11. Alarm text formatting (§19.3) ═══")
# ═══════════════════════════════════════════════════════════════════════════

from src.budget.tracker import format_alarm_70, format_alarm_90, format_alarm_hard_stop

a70 = format_alarm_70(spent=70.0, max_dollars=100.0, remaining=3)
check("alarm_70 contains BUDGET_WARN_70", "BUDGET_WARN_70" in a70)
check("alarm_70 contains percentage", "70.0%" in a70)

a90 = format_alarm_90(spent=90.0, max_dollars=100.0)
check("alarm_90 contains BUDGET_ALERT_90", "BUDGET_ALERT_90" in a90)

ahs = format_alarm_hard_stop(spent=105.0, max_dollars=100.0, n_approved=8)
check("hard_stop contains BUDGET_HARD_STOP", "BUDGET_HARD_STOP" in ahs)
check("hard_stop contains n_approved", "8 sections approved" in ahs)


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

total = passed + len(errors)
print(f"\n{'═' * 60}")
print(f"Phase 3 validation: {passed}/{total} passed")

if errors:
    print(f"\n❌ {len(errors)} FAILURES:")
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("✅ All Phase 3 checks passed!")
    sys.exit(0)
