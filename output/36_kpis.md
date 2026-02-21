# §36 — KPI AND SUCCESS METRICS

## §36.0 Measurement Infrastructure

```python
from typing import Literal
from dataclasses import dataclass

MetricCategory = Literal["quality", "economy", "reliability", "convergence", "mow", "run_companion", "style_gate"]
MeasurementFrequency = Literal["per_run", "per_section", "per_iteration", "weekly", "continuous"]
GrafanaPanel = str  # panel ID in Grafana dashboard
```

## §36.1 Quality Metrics

| Metric | Definition | Target | Measurement Method | Frequency | Grafana Panel |
|--------|-----------|--------|-------------------|-----------|---------------|
| `human_acceptance_rate` | % runs accepted without post-delivery revision | ≥ 0.90 | Feedback Collector rating ≥ 4/5 per all sections | `per_run` | `quality.human_acceptance` |
| `citation_accuracy` | % citations with HTTP 200 + NLI entailment ≥ 0.80 | ≥ 0.98 | Citation Verifier pass rate; see §18.2–18.3 | `per_run` | `quality.citation_accuracy` |
| `l1_violation_rate` | % sections with ≥ 1 L1 forbidden pattern surviving Style Fixer | ≤ 0.01 | Style Linter post-Style Fixer scan; see §26.1 | `per_section` | `quality.l1_violations` |
| `error_density` | Factual errors per 1000 words confirmed by human review | ≤ 1.0 | Feedback Collector error highlights / (word_count / 1000) | `per_run` | `quality.error_density` |

```python
@dataclass
class QualityKPIs:
    human_acceptance_rate: float      # target >= 0.90
    citation_accuracy: float          # target >= 0.98
    l1_violation_rate: float          # target <= 0.01
    error_density: float              # target <= 1.0 errors/1000w
```

## §36.2 Economic Efficiency Metrics

| Metric | Definition | Target | Measurement Method | Frequency | Grafana Panel |
|--------|-----------|--------|-------------------|-----------|---------------|
| `cost_per_doc` | Total USD for 10k-word document (all agents, all iterations) | $20–$50 | Cost Tracker sum; see §19.3 | `per_run` | `economy.cost_per_doc` |
| `cost_per_word` | `total_cost_usd / actual_word_count` | ≤ $0.004 | Cost Tracker / Publisher word count | `per_run` | `economy.cost_per_word` |
| `first_approval_rate` | % sections approved on iteration 1 (no Reflector invoked) | ≥ 0.60 | `iterations_used == 1` in `sections` table | `per_section` | `economy.first_approval` |
| `avg_iterations` | Mean iterations per section across run | ≤ 2.5 | `AVG(iterations_used)` from `sections` table | `per_run` | `economy.avg_iterations` |

```python
@dataclass
class EconomyKPIs:
    cost_per_doc_usd: float           # target 20.0 <= x <= 50.0
    cost_per_word_usd: float          # target <= 0.004
    first_approval_rate: float        # target >= 0.60
    avg_iterations_per_section: float # target <= 2.5
```

## §36.3 Reliability Metrics

| Metric | Definition | Target | Measurement Method | Frequency | Grafana Panel |
|--------|-----------|--------|-------------------|-----------|---------------|
| `uptime` | % time API returns 2xx within 200ms P95 | ≥ 0.995 | Prometheus `drs_api_availability`; see §23.2 | `continuous` | `reliability.uptime` |
| `recovery_rate` | % runs resumed correctly after worker crash | 1.00 | Chaos tests: kill worker → verify checkpoint resume; see §25.6 | `weekly` | `reliability.recovery` |
| `mttr` | Mean time from failure detection to service restoration (minutes) | ≤ 5.0 | AlertManager trigger timestamp → service restored timestamp | `per_incident` | `reliability.mttr` |

```python
@dataclass
class ReliabilityKPIs:
    uptime: float                     # target >= 0.995
    recovery_rate: float              # target == 1.00
    mttr_minutes: float               # target <= 5.0
```

## §36.4 Convergence Metrics

| Metric | Definition | Target | Measurement Method | Frequency | Grafana Panel |
|--------|-----------|--------|-------------------|-----------|---------------|
| `oscillation_rate` | % sections triggering Oscillation Detector escalation; see §13 | ≤ 0.05 | `oscillation_detected == True` count / total sections | `per_run` | `convergence.oscillation_rate` |
| `panel_discussion_rate` | % sections triggering Panel Discussion; see §11.1 | ≤ 0.15 | `panel_active == True` count / total sections | `per_run` | `convergence.panel_rate` |
| `budget_overrun_rate` | % runs where `total_cost_usd > max_budget_dollars` | 0.00 | Hard stop enforcement; see §19.3 | `per_run` | `convergence.budget_overrun` |
| `style_drift_index` | Cosine distance between Style Exemplar embedding and mean section embedding | < 0.05 | sentence-transformers similarity; see §16.2 | `per_run` | `convergence.style_drift` |

```python
@dataclass
class ConvergenceKPIs:
    oscillation_rate: float           # target <= 0.05
    panel_discussion_rate: float      # target <= 0.15
    budget_overrun_rate: float        # target == 0.00
    style_drift_index: float          # target < 0.05
```

## §36.5 Mixture-of-Writers Metrics

| Metric | Definition | Target | Measurement Method | Frequency | Grafana Panel |
|--------|-----------|--------|-------------------|-----------|---------------|
| `mow_first_approval_rate` | % MoW-enabled sections approved after Fusor draft (iteration 1) | ≥ 0.55 | `mow_enabled == True AND iterations_used == 1` | `per_section` | `mow.first_approval` |
| `mow_delta_vs_single` | Approval-rate delta: MoW sections minus single-Writer sections | ≥ 0.15 | `mow_first_approval_rate - baseline_first_approval_rate`; see §36.2 | `weekly` | `mow.delta_vs_single` |
| `fusor_integration_rate` | % Fusor drafts incorporating best elements from ≥ 2 proposers | ≥ 0.60 | Fusor output field `sources_integrated_count >= 2` | `per_section` | `mow.fusor_integration` |
| `mow_break_even` | Avg iterations saved vs single-Writer baseline | ≥ 1.5 | `single_writer_avg_iter - mow_avg_iter` per matched topic pairs | `weekly` | `mow.break_even` |

```python
@dataclass
class MoWKPIs:
    first_approval_rate: float        # target >= 0.55
    delta_vs_single_writer: float     # target >= 0.15 (percentage points)
    fusor_integration_rate: float     # target >= 0.60
    break_even_iterations_saved: float # target >= 1.5
```

## §36.6 Run Companion Metrics

| Metric | Definition | Target | Measurement Method | Frequency | Grafana Panel |
|--------|-----------|--------|-------------------|-----------|---------------|
| `companion_response_time` | P95 latency from user message to Companion response (seconds) | ≤ 3.0 | OpenTelemetry span `run_companion` latency_ms P95; see §6.6 | `continuous` | `companion.response_time` |
| `proactive_alert_relevance` | % proactive alerts rated useful by user (thumbs up in UI) | ≥ 0.70 | Feedback Collector alert rating; see §6.5 | `per_run` | `companion.alert_relevance` |

```python
@dataclass
class RunCompanionKPIs:
    response_time_p95_seconds: float  # target <= 3.0
    proactive_alert_relevance: float  # target >= 0.70
```

## §36.7 Style Gate Metrics

| Metric | Definition | Target | Measurement Method | Frequency | Grafana Panel |
|--------|-----------|--------|-------------------|-----------|---------------|
| `style_gate_pass_rate` | % sections passing Style Pass (CSS_style ≥ 0.80) on first attempt | ≥ 0.70 | `style_approved == True AND style_iterations == 1` | `per_section` | `style_gate.pass_rate` |
| `style_fixer_convergence` | % Style Fixer invocations resolving all L1/L2 violations within 2 iterations | ≥ 0.90 | Style Linter post-fixer scan: zero violations within iter ≤ 2; see §5.10 | `per_section` | `style_gate.fixer_convergence` |

```python
@dataclass
class StyleGateKPIs:
    pass_rate_first_attempt: float    # target >= 0.70
    fixer_convergence_rate: float     # target >= 0.90
```

## §36.8 Aggregated KPI Schema

```python
@dataclass
class SystemKPIs:
    quality: QualityKPIs
    economy: EconomyKPIs
    reliability: ReliabilityKPIs
    convergence: ConvergenceKPIs
    mow: MoWKPIs
    run_companion: RunCompanionKPIs
    style_gate: StyleGateKPIs
    measured_at: str                  # ISO 8601
    run_id: str | None                # None for aggregate weekly reports
```

## §36.9 Storage and Alerting

```python
# Prometheus metric names (see §23.2)
PROMETHEUS_METRICS: dict[str, str] = {
    "human_acceptance_rate":    "drs_human_acceptance_ratio",
    "citation_accuracy":        "drs_citation_accuracy_ratio",
    "l1_violation_rate":        "drs_l1_violation_ratio",
    "error_density":            "drs_error_density_per_1000w",
    "cost_per_doc":             "drs_cost_per_doc_usd",
    "cost_per_word":            "drs_cost_per_word_usd",
    "first_approval_rate":      "drs_first_approval_ratio",
    "avg_iterations":           "drs_avg_iterations_per_section",
    "uptime":                   "drs_api_availability_ratio",
    "recovery_rate":            "drs_recovery_ratio",
    "mttr_minutes":             "drs_mttr_minutes",
    "oscillation_rate":         "drs_oscillation_ratio",
    "panel_discussion_rate":    "drs_panel_discussion_ratio",
    "budget_overrun_rate":      "drs_budget_overrun_ratio",
    "style_drift_index":        "drs_style_drift_cosine",
    "mow_first_approval_rate":  "drs_mow_first_approval_ratio",
    "mow_delta_vs_single":      "drs_mow_delta_pp",
    "companion_response_time":  "drs_companion_latency_p95_seconds",
    "style_gate_pass_rate":     "drs_style_gate_pass_ratio",
    "style_fixer_convergence":  "drs_style_fixer_convergence_ratio",
}

# Alert thresholds (see §23.7) — fires when condition breached for 15 min
ALERT_CONDITIONS: dict[str, str] = {
    "human_acceptance_rate":    "< 0.85",   # warn 5pp below target
    "citation_accuracy":        "< 0.95",   # warn 3pp below target
    "l1_violation_rate":        "> 0.02",   # warn 2× target
    "cost_per_doc":             "> 60.0",   # warn $10 above ceiling
    "uptime":                   "< 0.990",  # warn 0.5pp below target
    "oscillation_rate":         "> 0.08",   # warn 3pp above target
    "budget_overrun_rate":      "> 0.00",   # any overrun = immediate alert
    "companion_response_time":  "> 5.0",    # warn 2s above target
    "style_fixer_convergence":  "< 0.85",   # warn 5pp below target
}
```

## §36.10 KPI Evaluation Cadence

| Cadence | Scope | Action on Breach |
|---------|-------|-----------------|
| Per-run (real-time) | `economy`, `convergence`, `style_gate`, `run_companion` | Alert §23.7; log to `run_report.json` |
| Per-section (real-time) | `quality.l1_violation_rate`, `economy.first_approval_rate` | Log; contribute to run aggregate |
| Weekly batch (Sunday 02:00) | All categories vs 30-day rolling baseline | Issue + Slack if any metric degrades ≥ 5pp vs baseline |
| Deploy gate | `quality`, `reliability` on Golden Set; see §25.4 | Block deploy if `DQS < 0.75` or `human_acceptance_rate < 0.85` |

<!-- SPEC_COMPLETE -->