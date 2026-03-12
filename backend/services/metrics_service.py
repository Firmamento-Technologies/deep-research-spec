"""Real-time metrics tracking service using Prometheus."""

from prometheus_client import Counter, Histogram, Gauge, Summary

# Counters
run_started_counter = Counter(
    'drs_runs_started_total',
    'Total runs started'
)

run_completed_counter = Counter(
    'drs_runs_completed_total',
    'Total runs completed',
    ['preset', 'status']  # success, failed
)

section_processed_counter = Counter(
    'drs_sections_processed_total',
    'Total sections processed',
    ['agent', 'status']  # planner, researcher, writer, critic
)

llm_calls_counter = Counter(
    'drs_llm_calls_total',
    'Total LLM API calls',
    ['model', 'agent', 'status']  # model name, agent name, success/error
)

# Histograms
run_duration_histogram = Histogram(
    'drs_run_duration_seconds',
    'Run duration in seconds',
    ['preset'],
    buckets=[60, 120, 300, 600, 1800, 3600, 7200]
)

section_duration_histogram = Histogram(
    'drs_section_duration_seconds',
    'Section processing duration',
    ['agent'],
    buckets=[5, 10, 30, 60, 120, 300, 600]
)

llm_latency_histogram = Histogram(
    'drs_llm_latency_seconds',
    'LLM API call latency',
    ['model', 'agent'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Gauges
active_runs_gauge = Gauge(
    'drs_active_runs',
    'Currently active runs'
)

total_cost_gauge = Gauge(
    'drs_total_cost_dollars',
    'Total cost spent (USD)'
)

avg_quality_gauge = Gauge(
    'drs_avg_quality_score',
    'Average quality score (CSS composite)'
)

budget_utilization_gauge = Gauge(
    'drs_budget_utilization_ratio',
    'Budget utilization ratio (used/allocated)',
    ['preset']
)

# Summary
token_usage_summary = Summary(
    'drs_token_usage',
    'Token usage statistics',
    ['model', 'type']  # input, output
)


class MetricsService:
    """Service for tracking real-time metrics."""
    
    @staticmethod
    def record_run_started():
        """Record a new run started."""
        run_started_counter.inc()
        active_runs_gauge.inc()
    
    @staticmethod
    def record_run_completed(
        preset: str,
        duration_seconds: float,
        cost: float,
        quality: float,
        success: bool = True,
    ):
        """Record a run completion."""
        status = 'success' if success else 'failed'
        run_completed_counter.labels(preset=preset, status=status).inc()
        active_runs_gauge.dec()
        run_duration_histogram.labels(preset=preset).observe(duration_seconds)
        total_cost_gauge.set(cost)  # Would need aggregation
        avg_quality_gauge.set(quality)
    
    @staticmethod
    def record_section_processed(
        agent: str,
        duration_seconds: float,
        success: bool = True,
    ):
        """Record section processing."""
        status = 'success' if success else 'failed'
        section_processed_counter.labels(agent=agent, status=status).inc()
        section_duration_histogram.labels(agent=agent).observe(duration_seconds)
    
    @staticmethod
    def record_llm_call(
        model: str,
        agent: str,
        latency_seconds: float,
        input_tokens: int,
        output_tokens: int,
        success: bool = True,
    ):
        """Record LLM API call."""
        status = 'success' if success else 'error'
        llm_calls_counter.labels(model=model, agent=agent, status=status).inc()
        llm_latency_histogram.labels(model=model, agent=agent).observe(latency_seconds)
        token_usage_summary.labels(model=model, type='input').observe(input_tokens)
        token_usage_summary.labels(model=model, type='output').observe(output_tokens)
    
    @staticmethod
    def update_budget_utilization(preset: str, used: float, allocated: float):
        """Update budget utilization gauge."""
        ratio = used / allocated if allocated > 0 else 0
        budget_utilization_gauge.labels(preset=preset).set(ratio)
