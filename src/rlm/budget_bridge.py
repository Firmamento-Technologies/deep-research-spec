"""Budget bridge: translates RLMResult log entries into DRS CostEntry records.

CRITICAL: This module is the ONLY cost-tracking path for RLM nodes.
Do NOT track RLM costs anywhere else — the BudgetController (§19.5) reads
exclusively from RealTimeCostTracker, which this module feeds.

Also provides:
  - estimate_rlm_overhead(): per-run cost estimate for BudgetEstimator §19.1
  - patched_budget_estimator_node(): drop-in LangGraph node replacement
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.rlm.runtime import RLMResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost emission
# ---------------------------------------------------------------------------

async def emit_cost_entries(
    state: dict,
    agent: str,
    rlm_result: "RLMResult",
) -> None:
    """Emit RLM sub-call and root-call costs to RealTimeCostTracker §19.3.

    Each SUBCALL and ROOT_TOKENS entry in rlm_result.log becomes a CostEntry
    that RealTimeCostTracker writes to PostgreSQL + Redis and checks alarms.

    Args:
        state:       Live DocumentState dict (read-only except for budget field).
        agent:       Agent name string (e.g. 'source_synthesizer_rlm').
        rlm_result:  Completed RLMResult from RLMRuntime.run().
    """
    try:
        from src.budget.tracker import CostEntry, RealTimeCostTracker
    except ImportError:
        # Budget tracker not yet implemented — log warning, continue
        logger.warning(
            "RealTimeCostTracker not found. RLM costs for agent '%s' not tracked. "
            "Implement src/budget/tracker.py to enable full budget integration.",
            agent,
        )
        return

    tracker = RealTimeCostTracker()
    section_idx = state.get("current_section_idx", 0)
    iteration = state.get("current_iteration", 1)
    doc_id = state.get("doc_id", "unknown")
    budget = state.get("budget", {})

    for entry in rlm_result.log:
        event = entry.get("event")
        detail = entry.get("detail", {})

        if not isinstance(detail, dict):
            continue

        if event == "SUBCALL":
            cost_entry = CostEntry(
                doc_id=doc_id,
                section_idx=section_idx,
                iteration=iteration,
                agent=agent,
                model=rlm_result.sub_model,
                tokens_in=detail.get("tokens_in", 0),
                tokens_out=detail.get("tokens_out", 0),
                cost_usd=detail.get("cost_usd", 0.0),
                latency_ms=detail.get("latency_ms", 0),
                timestamp=_iso_now(),
            )
            await tracker.record(cost_entry, budget)

        elif event == "ROOT_TOKENS":
            cost_entry = CostEntry(
                doc_id=doc_id,
                section_idx=section_idx,
                iteration=iteration,
                agent=f"{agent}_root",
                model=rlm_result.root_model,
                tokens_in=detail.get("tokens_in", 0),
                tokens_out=detail.get("tokens_out", 0),
                cost_usd=detail.get("cost_usd", 0.0),
                latency_ms=detail.get("latency_ms", 0),
                timestamp=_iso_now(),
            )
            await tracker.record(cost_entry, budget)


# ---------------------------------------------------------------------------
# Pre-run overhead estimate (injected into BudgetEstimator §19.1)
# ---------------------------------------------------------------------------

# Conservative per-section cost specs for each RLM agent.
# Tuned against average observed token counts in testing.
_AGENT_COST_SPECS: dict[str, dict] = {
    "source_synthesizer_rlm": {
        "root_calls": 3,
        "sub_calls": 15,
        "root_tok_in": 3000,
        "root_tok_out": 600,
        "sub_tok_in": 2000,
        "sub_tok_out": 500,
        "iteration_multiplier": 1.0,
    },
    "coherence_guard_rlm": {
        "root_calls": 2,
        "sub_calls": 10,
        "root_tok_in": 2000,
        "root_tok_out": 400,
        "sub_tok_in": 1500,
        "sub_tok_out": 300,
        "iteration_multiplier": 1.0,
    },
    # PostDraftAnalyzer runs only on iteration 1 → multiply by 0.5
    "post_draft_analyzer_rlm": {
        "root_calls": 2,
        "sub_calls": 8,
        "root_tok_in": 2000,
        "root_tok_out": 400,
        "sub_tok_in": 1500,
        "sub_tok_out": 300,
        "iteration_multiplier": 0.5,
    },
}

# Model pricing ($/1M tokens)
_PRICE_ROOT_IN = 3.0    # claude-sonnet-4-5 input
_PRICE_ROOT_OUT = 15.0  # claude-sonnet-4-5 output
_PRICE_SUB_IN = 0.80    # claude-haiku-3-5 input
_PRICE_SUB_OUT = 4.0    # claude-haiku-3-5 output


def estimate_rlm_overhead(
    n_sections: int,
    rlm_agents_enabled: list[str],
) -> float:
    """Estimate total RLM cost overhead for a run.

    Called by patched_budget_estimator_node() before the 80%-cap check.
    Returns USD cost to add to the base DRS estimate.

    Args:
        n_sections:          Total number of document sections.
        rlm_agents_enabled:  List of RLM agent names that are active.

    Returns:
        Estimated overhead in USD, rounded to 4 decimal places.
    """
    total = 0.0
    for agent in rlm_agents_enabled:
        spec = _AGENT_COST_SPECS.get(agent)
        if spec is None:
            logger.warning("Unknown RLM agent '%s' — skipping overhead estimate.", agent)
            continue

        root_cost = (
            spec["root_calls"]
            * (
                spec["root_tok_in"] * _PRICE_ROOT_IN
                + spec["root_tok_out"] * _PRICE_ROOT_OUT
            )
            / 1_000_000
        )
        sub_cost = (
            spec["sub_calls"]
            * (
                spec["sub_tok_in"] * _PRICE_SUB_IN
                + spec["sub_tok_out"] * _PRICE_SUB_OUT
            )
            / 1_000_000
        )
        per_section = (root_cost + sub_cost) * spec["iteration_multiplier"]
        total += per_section * n_sections

    return round(total, 4)


async def patched_budget_estimator_node(state: dict) -> dict:
    """LangGraph node: BudgetEstimator §19.1 with RLM overhead injected.

    Replaces the standard budget_estimator node when features.rlm_enabled=True.
    Calls the original estimator first, then adds RLM overhead before the
    80%-cap check so the run is blocked correctly if RLM pushes it over budget.

    PRODUCES: budget (DocumentState field) — same as standard node.
    """
    try:
        from src.nodes.budget_estimator import budget_estimator_node
    except ImportError:
        logger.error(
            "src.nodes.budget_estimator not found — cannot patch BudgetEstimator."
        )
        return {}

    base_result = await budget_estimator_node(state)
    budget = base_result.get("budget", {})

    features = state.get("config", {}).get("features", {})
    if not features.get("rlm_enabled", False):
        return base_result

    rlm_agents = features.get("rlm_agents", [])
    n_sections = state.get("total_sections", len(state.get("outline", [])))
    overhead = estimate_rlm_overhead(n_sections=n_sections, rlm_agents_enabled=rlm_agents)

    max_budget = state.get("config", {}).get("max_budget_dollars", 0.0)
    new_estimated = round(budget.get("estimated_total_usd", 0.0) + overhead, 4)
    new_blocked = new_estimated > max_budget * 0.80

    logger.info(
        "RLM_BUDGET_OVERHEAD: base=%.4f overhead=%.4f total=%.4f blocked=%s agents=%s",
        budget.get("estimated_total_usd", 0.0),
        overhead,
        new_estimated,
        new_blocked,
        rlm_agents,
    )

    budget["estimated_total_usd"] = new_estimated
    budget["blocked"] = new_blocked
    if new_blocked:
        budget["block_reason"] = (
            f"Estimated ${new_estimated:.2f} (incl. RLM overhead ${overhead:.2f}) "
            f"> 80% cap ${max_budget * 0.80:.2f}"
        )

    return {"budget": budget}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
