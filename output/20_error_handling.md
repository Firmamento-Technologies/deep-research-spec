# 20. Error Handling Matrix and Resilience

## 20.1 ErrorHandlingMatrix

```python
from typing import TypedDict, Literal

ErrorScenario = Literal[
    "api_429",
    "api_500_timeout",
    "llm_malformed_output",
    "ghost_citation",
    "context_overflow",
    "mid_section_crash",
    "mid_jury_crash"
]

class ErrorHandlingMatrix(TypedDict):
    trigger: str                  # condition that activates this row
    first_response: str           # immediate automated action
    second_response: str          # action after first_response fails
    fallback: str                 # degraded-mode continuation
    escalation: str               # human or hard-stop action
```

| `trigger` | `first_response` | `second_response` | `fallback` | `escalation` |
|---|---|---|---|---|
| `api_429` | exponential backoff 2s→4s→8s + jitter; honor `Retry-After` header | rotate to next model in fallback chain (see §20.4) | continue with fallback model; emit `JURY_DEGRADED` if jury slot | alert + pause 60s; log `RATE_LIMIT_PERSISTENT` |
| `api_500_timeout` | retry ×2 with backoff (see §20.2); trip circuit breaker on 3rd failure | switch to fallback model; mark primary CB `OPEN` | proceed with available models; `JURY_DEGRADED` if jury | log `PROVIDER_FAILURE`; emit SSE `ESCALATION_REQUIRED` |
| `llm_malformed_output` | retry with simplified prompt (temperature −0.1, explicit format reminder) | re-parse with lenient JSON extractor; treat missing fields as `None` | default `verdict=FAIL`; `pass_fail=false`; `confidence="low"` | skip agent output; set `section.status="parse_error"`; human review |
| `ghost_citation` | Researcher targeted re-query on failed DOIs (max 2 retries) | mark claim as `UNVERIFIED`; instruct Writer to hedge ("evidence suggests") | label section `citation_limited`; reduce reliability contribution | alert user via Run Companion; include in Run Report §30.4 |
| `context_overflow` | invoke Context Compressor §14 aggressively (abstractive all sections) | switch to selective retrieval (RAG on approved sections only) | Writer receives outline + last 1 section verbatim only | downgrade to models with larger MECW; log `CONTEXT_DEGRADED` |
| `mid_section_crash` | resume from last LangGraph checkpoint via `thread_id` (see §21.2) | replay from last completed node in section subgraph | re-run current section from `researcher` node; prior approved sections intact | if 3 crash-resume cycles fail: emit `RUN_FAILED`; return partial document |
| `mid_jury_crash` | restart crashed jury slot only (not all 3 mini-juries) | substitute crashed slot with fallback model (see §20.4) | compute CSS on available judges; emit `JURY_DEGRADED` | if <2 judges operational: suspend section; escalate human |

## 20.2 Retry Policy

```python
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random

RETRY_BASE_SECONDS: int = 2
RETRY_MAX_SECONDS: int = 8
RETRY_MAX_ATTEMPTS: int = 3
RETRY_JITTER_SECONDS: float = 0.5   # uniform random [0, 0.5]

@retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_BASE_SECONDS, max=RETRY_MAX_SECONDS)
        + wait_random(0, RETRY_JITTER_SECONDS),
    reraise=True
)
async def call_llm_with_retry(...): ...
```

Sequence on first error: wait 2s±jitter → retry; wait 4s±jitter → retry; wait 8s±jitter → retry; raise `MaxRetryError` → circuit breaker (§20.3).

## 20.3 Circuit Breaker

```python
CircuitBreakerState = Literal["CLOSED", "OPEN", "HALF_OPEN"]

class CircuitBreaker(TypedDict):
    slot: str           # e.g. "jury_reasoning_tier1", "writer_primary"
    model: str          # OpenRouter model id
    state: CircuitBreakerState
    failure_count: int
    last_failure_ts: float   # unix timestamp
    open_until_ts: float     # unix timestamp; 0 if CLOSED

# Transition rules (checked before every LLM call):
FAILURE_THRESHOLD: int = 3          # failures within WINDOW_SECONDS trip to OPEN
WINDOW_SECONDS: int = 60
OPEN_DURATION_SECONDS: int = 300    # 5 min before HALF_OPEN probe
HALF_OPEN_PROBE_CALLS: int = 1      # single call to test recovery
```

State machine:

```
CLOSED --[failures >= 3 in 60s]--> OPEN
OPEN   --[300s elapsed]--> HALF_OPEN
HALF_OPEN --[probe succeeds]--> CLOSED
HALF_OPEN --[probe fails]---> OPEN (reset timer)
```

One `CircuitBreaker` object per `(slot, model)` tuple. Stored in `DocumentState.circuit_breaker_states: dict[str, CircuitBreaker]`.

## 20.4 Fallback Chain

```yaml
# config/fallback_chains.yaml
# Each slot has an independent circuit breaker (see §20.3).
# On OPEN, skip to next model. On all OPEN: emit JURY_DEGRADED / WRITER_DEGRADED.

writer:
  - model: "anthropic/claude-opus-4-5"
  - model: "anthropic/claude-sonnet-4"
  - model: "google/gemini-2.5-pro"

reflector:
  - model: "openai/o3"
  - model: "openai/o3-mini"
  - model: "anthropic/claude-opus-4-5"

jury_reasoning:
  tier1:
    - model: "qwen/qwq-32b"
    - model: "openai/o3-mini"
    - model: "deepseek/deepseek-r1"
  tier2:
    - model: "openai/o3-mini"
    - model: "deepseek/deepseek-r1"
  tier3:
    - model: "deepseek/deepseek-r1"
    - model: "anthropic/claude-opus-4-5"

jury_factual:
  tier1:
    - model: "perplexity/sonar"
    - model: "google/gemini-2.5-flash"
    - model: "perplexity/sonar-pro"
  tier2:
    - model: "google/gemini-2.5-flash"
    - model: "perplexity/sonar-pro"
  tier3:
    - model: "perplexity/sonar-pro"
    - model: "openai/gpt-4o-search-preview"

jury_style:
  tier1:
    - model: "meta/llama-3.3-70b-instruct"
    - model: "mistral/mistral-large-2411"
    - model: "openai/gpt-4.5"
  tier2:
    - model: "mistral/mistral-large-2411"
    - model: "openai/gpt-4.5"
  tier3:
    - model: "openai/gpt-4.5"
    - model: "anthropic/claude-sonnet-4"

planner:
  - model: "google/gemini-2.5-pro"
  - model: "anthropic/claude-opus-4-5"

researcher:
  - model: "perplexity/sonar-pro"
  - model: "perplexity/sonar"
  - model: "tavily-fallback"        # triggers BeautifulSoup scraper §17.5

span_editor:
  - model: "anthropic/claude-sonnet-4"
  - model: "google/gemini-2.5-flash"

context_compressor:
  - model: "qwen/qwen3-7b"
  - model: "meta/llama-3.3-70b-instruct"

run_companion:
  - model: "google/gemini-2.5-pro"
  - model: "anthropic/claude-sonnet-4"
```

## 20.5 Graceful Degradation

```python
JURY_MIN_OPERATIONAL_JUDGES: int = 2   # below this: suspend section
JURY_DEGRADED_CSS_RECALC: bool = True  # CSS computed on available judges only

class DegradedModeWarning(TypedDict):
    slot: str
    operational_judges: int
    total_judges: int
    css_adjustment_note: Literal["css_recalculated_on_subset", "full_jury"]
    warning_code: Literal["JURY_DEGRADED", "WRITER_DEGRADED", "CONTEXT_DEGRADED"]
```

Rules:

| Condition | Action |
|---|---|
| 2/3 judges operational | recalculate CSS on 2 judges; emit `JURY_DEGRADED`; continue |
| 1/3 judges operational | suspend section; escalate human |
| 0/3 judges operational | `RUN_FAILED` for that slot; return partial document |
| Writer primary + fallback 1 both OPEN | use fallback 2; emit `WRITER_DEGRADED` |
| All writer chain OPEN | hard stop; save checkpoint; return partial |
| Context overflow after aggressive compression | see §20.1 `context_overflow` row |

`DegradedModeWarning` objects appended to `DocumentState.run_metrics["degradation_events"]` and included in Run Report §30.4.

<!-- SPEC_COMPLETE -->