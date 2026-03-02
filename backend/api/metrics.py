# Prometheus metrics endpoint + analytics stub (STEP 11).

from fastapi import APIRouter, Response
from prometheus_client import (
    Counter, Gauge, Histogram,
    CONTENT_TYPE_LATEST, generate_latest,
)

router = APIRouter()

# ─ Prometheus counters & gauges ──────────────────────────────────────────────

runs_total = Counter(
    "drs_runs_total", "Total pipeline runs started", ["preset"],
)
runs_completed = Counter(
    "drs_runs_completed_total", "Pipeline runs completed by status", ["status", "preset"],
)
active_runs_gauge = Gauge(
    "drs_active_runs", "Currently running pipelines",
)
run_duration_hist = Histogram(
    "drs_run_duration_seconds", "End-to-end pipeline duration",
    buckets=[30, 60, 120, 300, 600, 1200, 3600],
)
budget_hist = Histogram(
    "drs_budget_spent_usd", "USD spent per completed run",
    buckets=[0.1, 0.5, 1, 5, 10, 25, 50, 100, 500],
)
css_content_hist = Histogram(
    "drs_css_content_score", "Final CSS content score per run",
    buckets=[i / 10 for i in range(11)],
)


@router.get("/metrics")
def prometheus_metrics():
    """Scraped by Prometheus — exposes all registered metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/analytics")
async def analytics(
    from_date: str = "",
    to_date:   str = "",
    preset:    str = "",
    keyword:   str = "",
):
    """
    Returns aggregated run data for the Analytics page charts.
    Full implementation in STEP 11 (queries PostgreSQL).
    """
    return {
        "kpis": {
            "runs_completed":          0,
            "avg_cost_per_doc":        0.0,
            "total_words_generated":   0,
            "avg_css_composite":       0.0,
            "first_iter_success_rate": 0.0,
        },
        "runs":       [],
        "css_over_time": [],
        "cost_by_preset": [],
    }
