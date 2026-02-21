# §23 — Observability Stack

## §23.0 Module Contracts

```python
from typing import Literal, Optional
from dataclasses import dataclass

RunId = str  # UUID4
SectionIdx = int  # 0-based
Iteration = int  # 1-based

AgentName = Literal[
    "planner","researcher","citation_manager","citation_verifier",
    "source_sanitizer","source_synthesizer","writer","fusor",
    "jury_r","jury_f","jury_s","aggregator","reflector",
    "span_editor","diff_merger","style_linter","style_fixer",
    "context_compressor","coherence_guard","post_draft_analyzer",
    "oscillation_detector","publisher","run_companion","budget_controller"
]

Outcome = Literal["success","fail","veto","timeout","fallback","degraded"]
Severity = Literal["critical","high","warning","info"]
```

---

## §23.1 OpenTelemetry — Distributed Tracing

Every LLM call and agent node emits one span. Spans attach to the run-level trace via `run_id`.

### §23.1.1 Mandatory Span Attributes

| Attribute | Type | Source |
|-----------|------|--------|
| `drs.run_id` | `str` | `DocumentState.run_id` |
| `drs.section_idx` | `int` | `DocumentState.current_section_idx` |
| `drs.iteration` | `int` | `SectionState.iteration` |
| `drs.agent` | `AgentName` | hardcoded per node file |
| `drs.model` | `str` | `model_used` from LLM response |
| `drs.tokens_in` | `int` | `response.usage.prompt_tokens` |
| `drs.tokens_out` | `int` | `response.usage.completion_tokens` |
| `drs.cost_usd` | `float` | see §28.4 `MODEL_PRICING` |
| `drs.latency_ms` | `int` | `int((t1 - t0) * 1000)` |
| `drs.outcome` | `Outcome` | set before span end |

```python
# src/observability/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def get_tracer() -> trace.Tracer:
    return trace.get_tracer("drs.agents", "1.0.0")

def instrument_llm_call(
    tracer: trace.Tracer,
    run_id: RunId,
    section_idx: SectionIdx,
    iteration: Iteration,
    agent: AgentName,
) -> trace.Span:
    return tracer.start_as_current_span(
        f"drs.{agent}",
        attributes={
            "drs.run_id": run_id,
            "drs.section_idx": section_idx,
            "drs.iteration": iteration,
            "drs.agent": agent,
        }
    )
```

Span hierarchy per run:
```
Trace: drs.run.<run_id>
├── drs.planner
├── drs.researcher           [section_idx=0, iteration=1]
│   └── drs.tavily_search
├── drs.writer               [section_idx=0, iteration=1]
│   └── drs.llm_call
├── drs.jury_f               [section_idx=0, iteration=1]
│   └── drs.micro_search
└── drs.publisher
```

---

## §23.2 Prometheus — Metrics

Port: `9090`. Scrape interval: `15s`.

### §23.2.1 Metrics Table

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `drs_runs_total` | Counter | `status` | Runs by terminal status |
| `drs_runs_active` | Gauge | — | Currently executing runs |
| `drs_queue_length` | Gauge | — | Celery Redis queue depth |
| `drs_sections_approved_total` | Counter | `profile` | Sections passing Content Gate + Style Pass |
| `drs_sections_failed_total` | Counter | `profile`,`fail_reason` | Sections returning to Writer/Reflector |
| `drs_escalations_total` | Counter | `type` | Oscillation/coherence/veto escalations |
| `drs_run_duration_seconds` | Histogram | `profile`,`quality_preset` | Buckets: 60,300,600,1800,3600,7200 |
| `drs_section_duration_seconds` | Histogram | `iteration` | Per-section wall time |
| `drs_section_iterations_count` | Histogram | `profile` | Buckets: 1,2,3,4,5,8 |
| `drs_agent_latency_seconds` | Histogram | `agent`,`model` | Buckets: 0.5,1,2,5,10,30,60 |
| `drs_agent_errors_total` | Counter | `agent`,`error_type` | `timeout`,`parse_fail`,`api_429`,`api_500` |
| `drs_agent_cost_usd_total` | Counter | `agent`,`model` | Cumulative spend |
| `drs_tokens_total` | Counter | `agent`,`model`,`direction` | `direction`: `in`\|`out` |
| `drs_css_score` | Histogram | `profile`,`section_position` | Buckets: 0.3,0.5,0.65,0.7,0.8,0.85,0.9,1.0 |
| `drs_style_linter_violations_total` | Counter | `rule_id`,`preset`,`level` | L1/L2 violations pre-jury |
| `drs_circuit_breaker_state` | Gauge | `slot`,`model` | 0=CLOSED,1=HALF_OPEN,2=OPEN |
| `drs_budget_utilization_ratio` | Gauge | `run_id` | `spent / max_budget` at checkpoint |
| `drs_hallucination_rate` | Gauge | `model` | Rolling ghost-citation rate (see §18.5) |
| `drs_panel_discussion_total` | Counter | `outcome` | `approved`\|`escalated` |
| `drs_mow_first_attempt_approval_total` | Counter | `approved` | MoW first-draft approval tracking |

```python
# src/observability/metrics.py
from prometheus_client import Counter, Gauge, Histogram, start_http_server

RUNS_TOTAL = Counter("drs_runs_total", "Runs by status", ["status"])
CSS_SCORE = Histogram(
    "drs_css_score", "CSS distribution",
    ["profile", "section_position"],
    buckets=[0.3, 0.5, 0.65, 0.7, 0.8, 0.85, 0.9, 1.0]
)
AGENT_COST = Counter(
    "drs_agent_cost_usd_total", "Cumulative cost",
    ["agent", "model"]
)
```

---

## §23.3 Grafana — Dashboards

Four dashboards. All use datasource `prometheus` (default) and `tempo` for trace drill-down.

### Dashboard 1 — Operations Overview
| Panel | PromQL |
|-------|--------|
| Active runs | `drs_runs_active` |
| Run completion rate 24h | `rate(drs_runs_total{status="completed"}[24h]) / rate(drs_runs_total[24h])` |
| Error rate by agent | `rate(drs_agent_errors_total[5m])` |
| Queue depth | `drs_queue_length` |
| Hourly cost | `rate(drs_agent_cost_usd_total[1h]) * 3600` |

### Dashboard 2 — Quality Monitor
| Panel | PromQL |
|-------|--------|
| CSS distribution heatmap | `histogram_quantile(0.5, drs_css_score)` |
| Avg iterations per section | `histogram_quantile(0.5, drs_section_iterations_count)` |
| Escalation rate | `rate(drs_escalations_total[1h])` |
| Hallucination rate by model | `drs_hallucination_rate` |
| Style violations by rule | `rate(drs_style_linter_violations_total[1h])` |

### Dashboard 3 — Cost Tracker
| Panel | PromQL |
|-------|--------|
| Cost by agent (pie) | `increase(drs_agent_cost_usd_total[24h])` |
| Tokens in/out by model | `increase(drs_tokens_total[1h])` |
| Budget utilization gauge | `drs_budget_utilization_ratio` |
| Top 10 most expensive runs | topk(10, `drs_budget_utilization_ratio`) |

### Dashboard 4 — Infrastructure
| Panel | PromQL |
|-------|--------|
| API latency P50/P95/P99 | `histogram_quantile(0.95, rate(drs_agent_latency_seconds_bucket[5m]))` |
| Circuit breaker states | `drs_circuit_breaker_state == 2` |
| Section duration P95 | `histogram_quantile(0.95, rate(drs_section_duration_seconds_bucket[5m]))` |
| Panel discussion rate | `rate(drs_panel_discussion_total[1h])` |

---

## §23.4 Sentry — Error Schema

Every unhandled exception and `COMPROMISED` agent output goes to Sentry.

```python
@dataclass
class SentryErrorContext:
    doc_id: str
    run_id: RunId
    section_idx: SectionIdx
    iteration: Iteration
    agent: AgentName
    model: str
    error_type: Literal[
        "parse_fail","api_timeout","api_429","api_500",
        "context_overflow","injection_detected","circuit_open",
        "budget_exceeded","schema_violation"
    ]
    trace_id: str          # correlates to §23.1 span
    span_id: str
    payload_hash: str      # SHA256 of agent input, never raw content
    fallback_attempted: bool
    fallback_model: Optional[str]
```

```python
# src/observability/sentry_setup.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    integrations=[FastApiIntegration(), CeleryIntegration()],
    traces_sample_rate=0.1,
    before_send=scrub_pii,          # strip PII before transmission
)

def capture_agent_error(ctx: SentryErrorContext, exc: Exception) -> None:
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("agent", ctx.agent)
        scope.set_tag("error_type", ctx.error_type)
        scope.set_context("drs", {
            "run_id": ctx.run_id,
            "doc_id": ctx.doc_id,
            "section_idx": ctx.section_idx,
            "iteration": ctx.iteration,
            "model": ctx.model,
            "trace_id": ctx.trace_id,
        })
        sentry_sdk.capture_exception(exc)
```

---

## §23.5 SSE — Async Progress (Frontend)

Endpoint: `GET /v1/runs/{run_id}/stream` — see §24.2.

```python
EventType = Literal[
    "SECTION_APPROVED","JURY_VERDICT","REFLECTOR_FEEDBACK",
    "ESCALATION_REQUIRED","BUDGET_WARNING","STYLE_VIOLATION",
    "RUN_COMPLETED","RUN_FAILED","OSCILLATION_DETECTED"
]

@dataclass
class SSEEvent:
    event: EventType
    run_id: RunId
    section_idx: SectionIdx
    iteration: int
    data: dict              # event-specific payload, typed per EventType
    timestamp_iso: str
    trace_id: str
```

Reconnection: client sends `Last-Event-ID` header; server replays from that event via Redis pub/sub log (TTL 2h).

---

## §23.6 Structured Logs — JSON Schema

Free text is `FORBIDDEN` in production. Every log line is exactly one JSON object.

```python
@dataclass
class DRSLogRecord:
    timestamp_iso: str          # ISO 8601 UTC
    level: Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]
    service: str                # e.g. "drs.jury_f"
    run_id: RunId
    section_idx: SectionIdx
    iteration: Iteration
    agent: AgentName
    model: str
    event: str                  # snake_case verb phrase, e.g. "llm_call_complete"
    outcome: Outcome
    css: Optional[float]        # null if not applicable
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    cost_usd: Optional[float]
    latency_ms: Optional[int]
    trace_id: str               # OpenTelemetry trace ID
    span_id: str                # OpenTelemetry span ID
    extra: dict                 # typed per event; never raw LLM content
```

Example valid record:
```json
{
  "timestamp_iso": "2026-02-15T14:32:01.412Z",
  "level": "INFO",
  "service": "drs.jury_f",
  "run_id": "d4f1a2b3-...",
  "section_idx": 2,
  "iteration": 1,
  "agent": "jury_f",
  "model": "perplexity/sonar-pro",
  "event": "verdict_emitted",
  "outcome": "fail",
  "css": 0.44,
  "tokens_in": 1820,
  "tokens_out": 312,
  "cost_usd": 0.0031,
  "latency_ms": 2140,
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "extra": {"veto_category": null, "confidence": "low", "missing_evidence_count": 2}
}
```

Log aggregation: Loki. Correlation: `trace_id` + `span_id` link log record → Tempo span (click-through in Grafana).

---

## §23.7 Alerting

All alerts route via AlertManager. Recipients: `Literal["pagerduty","slack_ops","slack_quality","github_issue"]`.

| Alert Name | Condition | Severity | Recipient | Action |
|------------|-----------|----------|-----------|--------|
| `HighRunFailureRate` | `rate(drs_runs_total{status="failed"}[15m]) / rate(drs_runs_total[15m]) > 0.05` | `critical` | `pagerduty` | Page on-call |
| `CircuitBreakerOpen` | `drs_circuit_breaker_state{} == 2` for 2m | `critical` | `pagerduty` | Immediate notify |
| `BudgetBurnAlert` | `rate(drs_agent_cost_usd_total[1h]) > 2 * avg_over_time(rate(drs_agent_cost_usd_total[1h])[7d:1h])` | `warning` | `slack_ops` | Review model usage |
| `QueueBacklog` | `drs_queue_length > 20` for 5m | `warning` | `slack_ops` | KEDA scale-up |
| `CSSQualityDrift` | `avg(drs_css_score) < avg_over_time(avg(drs_css_score)[7d:1h]) - 0.05` | `warning` | `slack_quality` | Prompt review |
| `HallucinationRateHigh` | `drs_hallucination_rate > 0.05` for 30m | `high` | `slack_quality` + `github_issue` | Evaluate model replacement |
| `HighAgentLatency` | `histogram_quantile(0.95, rate(drs_agent_latency_seconds_bucket[10m])) > 2 * <baseline>` | `high` | `slack_ops` | Check provider status |
| `PromptDriftDetected` | Weekly Golden Set job: `hard_pass_rate < baseline - 0.05` | `high` | `slack_quality` + `github_issue` | Block non-urgent deploys |
| `BudgetUtilizationCritical` | `drs_budget_utilization_ratio > 0.90` | `warning` | `slack_ops` | Trigger §19.2 fallback |
| `OscillationDetected` | `rate(drs_escalations_total{type="oscillation"}[10m]) > 0` | `info` | `slack_ops` | Monitor |
| `RunCompleted` | `increase(drs_runs_total{status="completed"}[1m]) > 0` | `info` | webhook (see §24) | Notify run owner |

```yaml
# alertmanager/rules.yaml
groups:
  - name: drs.critical
    interval: 30s
    rules:
      - alert: HighRunFailureRate
        expr: >
          rate(drs_runs_total{status="failed"}[15m])
          / rate(drs_runs_total[15m]) > 0.05
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Run failure rate >5% in 15m"
      - alert: CircuitBreakerOpen
        expr: drs_circuit_breaker_state == 2
        for: 2m
        labels:
          severity: critical
```

---

## §23.8 SLO Definitions

| SLO | Target | Error Budget (30d) |
|-----|--------|--------------------|
| Run completion rate | 99.0% | 7.2h downtime |
| API availability (sync endpoints) | 99.5% | 3.6h |
| Sync endpoint P95 latency < 200ms | 99.0% | — |
| SSE delivery latency < 2s | 99.0% | — |
| Webhook delivery success | 99.0% | — |

Error budget < 20% remaining → auto-block non-urgent deploys via CI gate.

<!-- SPEC_COMPLETE -->