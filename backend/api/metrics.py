from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date, text
from database.connection import get_db
from database.models import Run, Section
from api.dependencies import require_viewer
from typing import Optional, List
from datetime import date, datetime, timedelta
import json

router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_viewer)],
)


@router.get("")
async def get_analytics(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
    preset:    Optional[str] = Query(None),
    keyword:   Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """GET /api/analytics - Returns KPIs + chart data"""
    filters = [Run.status == "completed"]

    if from_date:
        filters.append(Run.created_at >= from_date)
    if to_date:
        filters.append(Run.created_at <= f"{to_date} 23:59:59")
    if preset:
        preset_list = [p.strip() for p in preset.split(",") if p.strip()]
        if preset_list:
            filters.append(Run.quality_preset.in_(preset_list))
    if keyword:
        filters.append(Run.topic.ilike(f"%{keyword}%"))

    # KPIs
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

    first_iter_q = await db.execute(
        select(func.count(Run.doc_id)).where(
            *filters,
            Run.current_iteration == 1,
        )
    )
    first_iter_count = first_iter_q.scalar() or 0
    total_runs = int(kpi_row.total_runs)
    first_iter_rate = (first_iter_count / total_runs) if total_runs > 0 else 0.0

    # CSS over time
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

    # Cost by preset
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

    # CSS vs cost scatter
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

    # Iterations heatmap
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


@router.get("/cost-breakdown/{doc_id}")
async def get_cost_breakdown(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Detailed cost breakdown per section and agent"""
    result = await db.execute(select(Run).where(Run.doc_id == doc_id))
    run = result.scalar_one_or_none()
    if not run:
        return {"error": "Run not found"}

    sections_result = await db.execute(
        select(Section).where(Section.doc_id == doc_id).order_by(Section.section_idx)
    )
    sections = sections_result.scalars().all()

    section_breakdown = []
    for section in sections:
        costs = section.metadata.get("costs", {}) if section.metadata else {}
        section_breakdown.append({
            "section_idx": section.section_idx,
            "title": section.title,
            "costs": costs,
            "iterations": section.metadata.get("iterations", 1) if section.metadata else 1,
            "tokens": section.metadata.get("tokens", {}) if section.metadata else {},
        })

    return {
        "sections": section_breakdown,
        "total_cost": run.total_cost or 0,
        "budget_remaining": (run.max_budget_dollars or 15) - (run.total_cost or 0),
    }


@router.get("/performance")
async def get_performance_metrics(
    time_range: str = Query("7d"),
    db: AsyncSession = Depends(get_db),
):
    """Performance trends over time"""
    # Parse time range
    days = int(time_range.rstrip('d'))
    start_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(
            cast(Run.created_at, Date).label("date"),
            func.avg(Run.total_cost).label("avg_cost"),
            func.count(Run.doc_id).label("run_count"),
        )
        .where(
            Run.status == "completed",
            Run.created_at >= start_date,
        )
        .group_by(cast(Run.created_at, Date))
        .order_by(cast(Run.created_at, Date))
    )

    trends = [
        {
            "date": str(row.date),
            "avg_cost": round(float(row.avg_cost or 0), 4),
            "run_count": int(row.run_count),
        }
        for row in result
    ]

    return {
        "trends": trends,
        "throughput": {
            "runs_per_day": sum(t["run_count"] for t in trends) / max(days, 1),
        },
    }


@router.get("/quality-trends")
async def get_quality_trends(
    time_range: str = Query("7d"),
    db: AsyncSession = Depends(get_db),
):
    """Quality metrics over time"""
    days = int(time_range.rstrip('d'))
    start_date = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(
            cast(Run.created_at, Date).label("date"),
            func.avg(Run.css_content).label("content"),
            func.avg(Run.css_style).label("style"),
            func.avg(Run.css_source).label("source"),
        )
        .where(
            Run.status == "completed",
            Run.created_at >= start_date,
        )
        .group_by(cast(Run.created_at, Date))
        .order_by(cast(Run.created_at, Date))
    )

    css_trends = [
        {
            "date": str(row.date),
            "content": round(float(row.content or 0), 4),
            "style": round(float(row.style or 0), 4),
            "source": round(float(row.source or 0), 4),
        }
        for row in result
    ]

    # First iteration success rate
    total_q = await db.execute(
        select(func.count(Run.doc_id)).where(
            Run.status == "completed",
            Run.created_at >= start_date,
        )
    )
    total = total_q.scalar() or 0

    first_iter_q = await db.execute(
        select(func.count(Run.doc_id)).where(
            Run.status == "completed",
            Run.created_at >= start_date,
            Run.current_iteration == 1,
        )
    )
    first_iter = first_iter_q.scalar() or 0

    return {
        "css_trends": css_trends,
        "first_iteration_success": (first_iter / total) if total > 0 else 0,
    }


@router.get("/budget-efficiency")
async def get_budget_efficiency(
    db: AsyncSession = Depends(get_db),
):
    """Budget utilization analysis"""
    result = await db.execute(
        select(
            Run.quality_preset.label("preset"),
            func.avg(Run.total_cost).label("avg_cost"),
            func.avg((Run.css_content + Run.css_style + Run.css_source) / 3.0).label("avg_quality"),
            func.count(Run.doc_id).label("count"),
        )
        .where(Run.status == "completed")
        .group_by(Run.quality_preset)
    )

    by_preset = [
        {
            "preset": row.preset or "Unknown",
            "avg_cost": round(float(row.avg_cost or 0), 4),
            "avg_quality": round(float(row.avg_quality or 0), 4),
            "efficiency": round((float(row.avg_quality or 0) / float(row.avg_cost or 1)), 4),
            "count": int(row.count),
        }
        for row in result
    ]

    return {
        "by_preset": by_preset,
        "efficiency_formula": "quality_score / cost",
    }
