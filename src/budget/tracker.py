"""Real-Time Cost Tracker — §19.3, §19.4 canonical.

Records every LLM call cost to PostgreSQL + Redis, checks budget thresholds,
and applies dynamic savings strategies (model downgrade, threshold relaxation,
hard stop).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from src.budget.regime import THRESHOLD_TABLE

logger = logging.getLogger(__name__)


# ── §19.3 CostEntryData TypedDict ───────────────────────────────────────────

AgentSlot = Literal[
    "planner", "researcher", "writer", "fusor",
    "jury_r", "jury_f", "jury_s", "reflector",
    "span_editor", "compressor", "post_draft",
]


class CostEntryData(TypedDict):
    """Schema for a single LLM call cost entry. §19.3."""
    doc_id: str
    section_idx: int
    iteration: int
    agent: AgentSlot
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    timestamp: str  # ISO-8601


# ── §19.3 Alarm text templates ──────────────────────────────────────────────

ALARM_70_TEMPLATE = (
    "BUDGET_WARN_70: ${spent:.4f} of ${max:.2f} used ({pct:.1f}%). "
    "Downgrading models for remaining {remaining} sections."
)

ALARM_90_TEMPLATE = (
    "BUDGET_ALERT_90: ${spent:.4f} of ${max:.2f} used ({pct:.1f}%). "
    "Forcing jury_size=1, css_threshold=0.65, max_iterations=1."
)

ALARM_HARD_STOP_TEMPLATE = (
    "BUDGET_HARD_STOP: ${spent:.4f} exceeds cap ${max:.2f}. "
    "Saving checkpoint. Returning partial document ({n_approved} sections approved)."
)

ALARM_SECTION_ANOMALY_TEMPLATE = (
    "BUDGET_SECTION_ANOMALY: Section {section_idx} cost ${cost:.2f} exceeds $15.00 threshold. "
    "Pausing run for human review."
)


def format_alarm_70(spent: float, max_dollars: float, remaining: int) -> str:
    """Format BUDGET_WARN_70 alarm text. §19.3."""
    pct = (spent / max_dollars) * 100 if max_dollars > 0 else 100.0
    return ALARM_70_TEMPLATE.format(
        spent=spent, max=max_dollars, pct=pct, remaining=remaining,
    )


def format_alarm_90(spent: float, max_dollars: float) -> str:
    """Format BUDGET_ALERT_90 alarm text. §19.3."""
    pct = (spent / max_dollars) * 100 if max_dollars > 0 else 100.0
    return ALARM_90_TEMPLATE.format(spent=spent, max=max_dollars, pct=pct)


def format_alarm_hard_stop(spent: float, max_dollars: float, n_approved: int) -> str:
    """Format BUDGET_HARD_STOP alarm text. §19.3."""
    return ALARM_HARD_STOP_TEMPLATE.format(
        spent=spent, max=max_dollars, n_approved=n_approved,
    )


def format_alarm_section_anomaly(section_idx: int, cost: float) -> str:
    """Format BUDGET_SECTION_ANOMALY alarm text. §19.4."""
    return ALARM_SECTION_ANOMALY_TEMPLATE.format(
        section_idx=section_idx, cost=cost,
    )


# ── §19.3 record_cost_entry ─────────────────────────────────────────────────

async def record_cost_entry(
    entry: CostEntryData,
    budget: dict,
    db_session: Any | None = None,
    redis: Any | None = None,
) -> dict:
    """Record a cost entry and update BudgetState. §19.3.

    Writes CostEntry to PostgreSQL costs table atomically, then updates
    the Redis cost accumulator. If Redis is unavailable, falls back to
    PostgreSQL-only tracking.

    Args:
        entry: Cost entry data for a single LLM call.
        budget: Current BudgetState dict.
        db_session: AsyncSession for PostgreSQL (optional for testing).
        redis: redis.asyncio.Redis client (optional, graceful degradation).

    Returns:
        Updated BudgetState dict with new spent_dollars.
    """
    cost_usd = entry["cost_usd"]

    # Guard: negative cost → clamp to 0
    if cost_usd < 0:
        logger.error(
            "negative_cost: agent=%s model=%s cost_usd=%.6f — clamping to 0.0",
            entry["agent"], entry["model"], cost_usd,
        )
        cost_usd = 0.0
        entry = {**entry, "cost_usd": cost_usd}

    # Write to PostgreSQL atomically
    if db_session is not None:
        try:
            from src.storage.postgres import CostRepository
            repo = CostRepository(db_session)
            await repo.record_cost({
                "document_id": entry["doc_id"],
                "run_id": entry.get("run_id", entry["doc_id"]),
                "section_index": entry["section_idx"],
                "iteration": entry["iteration"],
                "agent": entry["agent"],
                "model": entry["model"],
                "tokens_in": entry["tokens_in"],
                "tokens_out": entry["tokens_out"],
                "cost_usd": cost_usd,
                "latency_ms": entry["latency_ms"],
            })
        except Exception:
            logger.error(
                "PostgreSQL cost write failed for doc_id=%s agent=%s",
                entry["doc_id"], entry["agent"], exc_info=True,
            )

    # Update Redis cost accumulator atomically
    new_total = budget["spent_dollars"] + cost_usd
    if redis is not None:
        try:
            from src.storage.redis_cache import record_cost_redis
            new_total = await record_cost_redis(
                run_id=entry["doc_id"],
                delta_usd=cost_usd,
                redis=redis,
            )
        except Exception:
            logger.warning(
                "redis_fallback: Redis cost update failed for doc_id=%s — "
                "using local accumulation",
                entry["doc_id"], exc_info=True,
            )
            new_total = budget["spent_dollars"] + cost_usd
    else:
        new_total = budget["spent_dollars"] + cost_usd

    # Update budget
    updated = dict(budget)
    updated["spent_dollars"] = new_total

    return updated


# ── §19.4 apply_dynamic_savings ──────────────────────────────────────────────

def apply_dynamic_savings(budget: dict) -> dict:
    """Apply dynamic savings strategies based on spend percentage. §19.4.

    Pure function (no I/O). Checks thresholds in order: 100% first,
    then 90%, then 70%. Each alarm fires exactly once per run.

    Args:
        budget: Current BudgetState dict.

    Returns:
        Updated BudgetState dict with any savings applied.

    Floor guards (§19.5):
        - css_content_threshold >= 0.45
        - css_style_threshold >= 0.60
        - jury_size >= 1
    """
    max_dollars = budget["max_dollars"]
    if max_dollars <= 0:
        return budget

    pct = budget["spent_dollars"] / max_dollars
    b = dict(budget)

    # ── 100% → Hard Stop ─────────────────────────────────────────────────
    if pct >= 1.00 and not b.get("hard_stop_fired", False):
        b["hard_stop_fired"] = True
        logger.critical(
            "BUDGET_HARD_STOP: spent=%.4f exceeds cap=%.2f",
            b["spent_dollars"], max_dollars,
        )
        # graph router reads this flag → routes to publisher immediately

    # ── 90% → Economy Floor ──────────────────────────────────────────────
    elif pct >= 0.90 and not b.get("alarm_90_fired", False):
        b["alarm_90_fired"] = True
        # Force Economy floor from §9.3 THRESHOLD_TABLE
        b["css_content_threshold"] = max(0.45, THRESHOLD_TABLE["economy"]["css_content_threshold"])  # 0.65
        b["css_style_threshold"] = max(0.60, THRESHOLD_TABLE["economy"]["css_style_threshold"])      # 0.75
        b["max_iterations"] = 1
        b["jury_size"] = 1
        b["mow_enabled"] = False
        logger.warning(
            format_alarm_90(b["spent_dollars"], max_dollars),
        )

    # ── 70% → Downgrade ─────────────────────────────────────────────────
    elif pct >= 0.70 and not b.get("alarm_70_fired", False):
        b["alarm_70_fired"] = True
        b["jury_size"] = max(1, b.get("jury_size", 1) - 1)
        # model downgrade applied by llm/client.py fallback chain
        logger.warning(
            format_alarm_70(
                b["spent_dollars"], max_dollars,
                remaining=0,  # caller should fill this
            ),
        )

    # Apply floor guards §19.5
    b["css_content_threshold"] = max(0.45, b.get("css_content_threshold", 0.65))
    b["css_style_threshold"] = max(0.60, b.get("css_style_threshold", 0.75))
    b["jury_size"] = max(1, b.get("jury_size", 1))

    return b


# ── §19.4 Section anomaly check ─────────────────────────────────────────────

SECTION_COST_ANOMALY_THRESHOLD = 15.00  # USD


def check_section_anomaly(
    section_idx: int,
    section_cost_usd: float,
) -> dict | None:
    """Check if a single section cost exceeds $15.00 threshold. §19.4.

    Returns an escalation dict for await_human if anomaly detected,
    or None if normal.
    """
    if section_cost_usd > SECTION_COST_ANOMALY_THRESHOLD:
        alarm_text = format_alarm_section_anomaly(section_idx, section_cost_usd)
        logger.warning(alarm_text)
        return {
            "type": "budget_section_anomaly",
            "section_idx": section_idx,
            "cost_usd": section_cost_usd,
            "threshold": SECTION_COST_ANOMALY_THRESHOLD,
            "message": alarm_text,
            "requires_human": True,
        }
    return None
