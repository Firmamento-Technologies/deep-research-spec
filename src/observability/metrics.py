"""Prometheus metrics for Deep Research System — §20 Observability.

Provides counters, histograms, and gauges for LLM calls, costs,
latency, pipeline progress, and quality scores.

Usage::

    from src.observability.metrics import DRS_LLM_CALLS, observe_llm_call

    # Automatic: integrated into LLMClient._build_result()
    # Manual: for custom pipeline events
    DRS_SECTIONS_COMPLETED.inc()
"""
from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ── Optional import — degrade gracefully ────────────────────────────────────

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        start_http_server,
    )
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False
    logger.debug("prometheus-client not installed — metrics disabled")


# ── Stub classes for when prometheus-client is absent ────────────────────────

class _StubMetric:
    """No-op metric that silently discards all calls."""
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass
    def inc(self, *args: Any, **kwargs: Any) -> None:
        pass
    def observe(self, *args: Any, **kwargs: Any) -> None:
        pass
    def set(self, *args: Any, **kwargs: Any) -> None:
        pass
    def labels(self, *args: Any, **kwargs: Any) -> "_StubMetric":
        return self


# ── Metric definitions ──────────────────────────────────────────────────────

if _HAS_PROMETHEUS:
    # LLM call count by agent/model/preset
    DRS_LLM_CALLS = Counter(
        "drs_llm_calls_total",
        "Total LLM API calls",
        ["agent", "model", "preset"],
    )

    # Cumulative cost in USD by agent
    DRS_LLM_COST = Counter(
        "drs_llm_cost_dollars_total",
        "Cumulative LLM cost in USD",
        ["agent", "model"],
    )

    # LLM call latency (seconds)
    DRS_LLM_LATENCY = Histogram(
        "drs_llm_latency_seconds",
        "LLM call latency in seconds",
        ["agent"],
        buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
    )

    # Token counts per call
    DRS_TOKENS_IN = Counter(
        "drs_tokens_in_total",
        "Total input tokens processed",
        ["model"],
    )

    DRS_TOKENS_OUT = Counter(
        "drs_tokens_out_total",
        "Total output tokens generated",
        ["model"],
    )

    # Pipeline progress
    DRS_SECTIONS_COMPLETED = Counter(
        "drs_sections_completed_total",
        "Number of sections that passed QA",
    )

    DRS_ITERATIONS = Counter(
        "drs_iterations_total",
        "Total write-judge-reflect iterations",
    )

    # Quality gauges
    DRS_CSS_SCORE = Gauge(
        "drs_jury_css_score",
        "Current CSS quality score",
        ["dimension"],  # content, style, source
    )

    DRS_BUDGET_SPENT = Gauge(
        "drs_budget_spent_dollars",
        "Current budget spent in dollars",
        ["doc_id"],
    )

    DRS_BUDGET_REMAINING_PCT = Gauge(
        "drs_budget_remaining_pct",
        "Budget remaining percentage",
        ["doc_id"],
    )

    DRS_PIPELINE_DURATION = Histogram(
        "drs_pipeline_duration_seconds",
        "Full pipeline execution time",
        buckets=(30, 60, 120, 300, 600, 1200, 1800, 3600),
    )

    DRS_JURY_QUALITY = Gauge(
        "drs_jury_pass_rate",
        "Jury approval rate (0.0-1.0)",
        ["preset"],
    )

else:
    DRS_LLM_CALLS = _StubMetric()  # type: ignore[assignment]
    DRS_LLM_COST = _StubMetric()  # type: ignore[assignment]
    DRS_LLM_LATENCY = _StubMetric()  # type: ignore[assignment]
    DRS_TOKENS_IN = _StubMetric()  # type: ignore[assignment]
    DRS_TOKENS_OUT = _StubMetric()  # type: ignore[assignment]
    DRS_SECTIONS_COMPLETED = _StubMetric()  # type: ignore[assignment]
    DRS_ITERATIONS = _StubMetric()  # type: ignore[assignment]
    DRS_CSS_SCORE = _StubMetric()  # type: ignore[assignment]
    DRS_BUDGET_SPENT = _StubMetric()  # type: ignore[assignment]
    DRS_BUDGET_REMAINING_PCT = _StubMetric()  # type: ignore[assignment]
    DRS_PIPELINE_DURATION = _StubMetric()  # type: ignore[assignment]
    DRS_JURY_QUALITY = _StubMetric()  # type: ignore[assignment]


# ── Helper functions ────────────────────────────────────────────────────────

def observe_llm_call(
    agent: str,
    model: str,
    preset: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_s: float | None = None,
) -> None:
    """Record a single LLM call across all relevant metrics."""
    DRS_LLM_CALLS.labels(agent=agent, model=model, preset=preset).inc()
    DRS_LLM_COST.labels(agent=agent, model=model).inc(cost_usd)
    DRS_TOKENS_IN.labels(model=model).inc(tokens_in)
    DRS_TOKENS_OUT.labels(model=model).inc(tokens_out)
    if latency_s is not None:
        DRS_LLM_LATENCY.labels(agent=agent).observe(latency_s)


def update_budget_gauge(doc_id: str, spent: float, max_dollars: float) -> None:
    """Update budget gauges for a run."""
    DRS_BUDGET_SPENT.labels(doc_id=doc_id).set(spent)
    remaining = max(0, (1 - spent / max_dollars) * 100) if max_dollars > 0 else 0
    DRS_BUDGET_REMAINING_PCT.labels(doc_id=doc_id).set(remaining)


def update_css_scores(css_content: float, css_style: float, css_source: float) -> None:
    """Update CSS quality score gauges."""
    DRS_CSS_SCORE.labels(dimension="content").set(css_content)
    DRS_CSS_SCORE.labels(dimension="style").set(css_style)
    DRS_CSS_SCORE.labels(dimension="source").set(css_source)


# ── Metrics server ──────────────────────────────────────────────────────────

_server_started = False
_server_lock = threading.Lock()


def start_metrics_server(port: int = 9090) -> bool:
    """Start Prometheus HTTP metrics endpoint on /metrics.

    Thread-safe, idempotent — calling multiple times is safe.
    Returns True if server started, False if already running or unavailable.
    """
    global _server_started
    if not _HAS_PROMETHEUS:
        logger.info("Prometheus metrics server not available (prometheus-client not installed)")
        return False

    with _server_lock:
        if _server_started:
            return False
        try:
            start_http_server(port)
            _server_started = True
            logger.info("Prometheus metrics server started on :%d/metrics", port)
            return True
        except Exception as exc:
            logger.warning("Failed to start metrics server: %s", exc)
            return False
