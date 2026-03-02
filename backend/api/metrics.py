from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date, text
from database.connection import get_db
from database.models import Run
from typing import Optional
from datetime import date
import json

router = APIRouter()


@router.get("/analytics")
async def get_analytics(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
    preset:    Optional[str] = Query(None),
    keyword:   Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/analytics
    Returns KPIs + chart data for the Analytics page.
    """
    # ---------------------------------------------------------------- #
    # Base filter
    # ---------------------------------------------------------------- #
    filters = [Run.status == "completed"]

    if from_date:
        filters.append(Run.created_at >= from_date)
    if to_date:
        # include the full to_date day
        filters.append(Run.created_at <= f"{to_date} 23:59:59")
    if preset:
        preset_list = [p.strip() for p in preset.split(",") if p.strip()]
        if preset_list:
            filters.append(Run.quality_preset.in_(preset_list))
    if keyword:
        filters.append(Run.topic.ilike(f"%{keyword}%"))

    # ---------------------------------------------------------------- #
    # KPIs
    # ---------------------------------------------------------------- #
    kpi_q = await db.execute(
        select(
            func.count(Run.doc_id).label("total_runs"),
            func.coalesce(func.avg(Run.total_cost), 0).label("avg_cost"),
            func.coalesce(func.sum(Run.total_words), 0).label("total_words"),
            func.coalesce(
                func.avg((Run.css_content + Run.css_style + Run.css_source) / 3.0), 0
            ).label("avg_css"),
        ).where(*filters)
    )
    kpi_row = kpi_q.one()

    # First-iteration success rate: runs where current_iteration == 1 at completion
    first_iter_q = await db.execute(
        select(func.count(Run.doc_id)).where(
            *filters,
            Run.current_iteration == 1,
        )
    )
    first_iter_count = first_iter_q.scalar() or 0
    total_runs = int(kpi_row.total_runs)
    first_iter_rate = (first_iter_count / total_runs) if total_runs > 0 else 0.0

    # ---------------------------------------------------------------- #
    # CSS over time (one row per completed run)
    # ---------------------------------------------------------------- #
    css_time_q = await db.execute(
        select(
            cast(Run.created_at, Date).label("date"),
            ((Run.css_content + Run.css_style + Run.css_source) / 3.0).label("value"),
            Run.doc_id,
            Run.topic,
        )
        .where(*filters)
        .order_by(Run.created_at)
        .limit(200)
    )
    css_over_time = [
        {
            "date": str(row.date),
            "value": round(float(row.value or 0), 4),
            "doc_id": row.doc_id,
            "topic": row.topic,
        }
        for row in css_time_q
    ]

    # ---------------------------------------------------------------- #
    # Cost by preset (grouped bar)
    # ---------------------------------------------------------------- #
    cost_preset_q = await db.execute(
        select(
            Run.quality_preset.label("preset"),
            func.avg(Run.total_cost).label("avg_cost"),
            func.count(Run.doc_id).label("count"),
        )
        .where(*filters)
        .group_by(Run.quality_preset)
    )
    cost_by_preset = [
        {
            "preset": row.preset or "Unknown",
            "avg_cost": round(float(row.avg_cost or 0), 4),
            "count": int(row.count),
        }
        for row in cost_preset_q
    ]

    # ---------------------------------------------------------------- #
    # CSS vs cost scatter
    # ---------------------------------------------------------------- #
    scatter_q = await db.execute(
        select(
            ((Run.css_content + Run.css_style + Run.css_source) / 3.0).label("css"),
            Run.total_cost.label("cost"),
            Run.quality_preset.label("preset"),
            Run.topic,
        )
        .where(*filters)
        .limit(500)
    )
    css_vs_cost = [
        {
            "css":    round(float(row.css or 0), 4),
            "cost":   round(float(row.cost or 0), 4),
            "preset": row.preset or "Unknown",
            "topic":  row.topic,
        }
        for row in scatter_q
    ]

    # ---------------------------------------------------------------- #
    # Iterations heatmap: sections x iteration counts
    # ---------------------------------------------------------------- #
    # Stored in JSON column output_paths as { "iterations_per_section": [int, ...] }
    # Aggregate across all runs
    heatmap_q = await db.execute(
        select(Run.output_paths).where(
            *filters,
            Run.output_paths.isnot(None),
        )
    )
    iter_counter: dict[tuple, int] = {}
    for row in heatmap_q:
        paths = row.output_paths or {}
        iterations_per_section = paths.get("iterations_per_section", [])
        for sec_idx, iters in enumerate(iterations_per_section):
            key = (sec_idx, int(iters))
            iter_counter[key] = iter_counter.get(key, 0) + 1

    iterations_heatmap = [
        {"section": sec, "iterations": itr, "count": cnt}
        for (sec, itr), cnt in sorted(iter_counter.items())
    ]

    # ---------------------------------------------------------------- #
    # Response
    # ---------------------------------------------------------------- #
    return {
        "kpis": {
            "total_runs":                    total_runs,
            "avg_cost_per_doc":              round(float(kpi_row.avg_cost or 0), 4),
            "total_words":                   int(kpi_row.total_words or 0),
            "avg_css_composite":             round(float(kpi_row.avg_css or 0), 4),
            "first_iteration_success_rate":  round(first_iter_rate, 4),
        },
        "css_over_time":       css_over_time,
        "cost_by_preset":      cost_by_preset,
        "css_vs_cost":         css_vs_cost,
        "iterations_heatmap":  iterations_heatmap,
    }
