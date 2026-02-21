# §25 Testing Framework

## §25.0 Shared Contracts

```python
from typing import Literal, Any
from dataclasses import dataclass

AgentName = Literal[
    "planner","researcher","writer","fusor","span_editor","reflector",
    "style_linter","style_fixer","coherence_guard","context_compressor",
    "citation_manager","citation_verifier","source_sanitizer",
    "source_synthesizer","metrics_collector","aggregator","post_draft_analyzer",
    "publisher","budget_controller","oscillation_detector"
]

TestLayer = Literal["unit_deterministic","unit_llm","integration","e2e","regression","chaos","smoke"]
TestStatus = Literal["pass","fail","skip","error"]
Severity = Literal["CRITICAL","HIGH","MEDIUM","LOW"]

@dataclass
class TestResult:
    layer: TestLayer
    test_id: str
    status: TestStatus
    metric: str
    value: float
    threshold: float
    details: str

@dataclass
class GoldenCase:
    case_id: str          # format: "{agent}_NNN"
    agent: AgentName
    input: dict[str, Any]
    expected_output_structure: dict[str, Any]  # JSON Schema subset
    forbidden_in_output: list[str]             # substrings NEVER in output
    hard_constraints: list[str]                # machine-verifiable assertions
    soft_metrics: dict[str, float]             # metric_name -> min_threshold
    ground_truth: dict[str, Any] | None        # human-approved reference

@dataclass
class GroundTruth:
    document_id: str
    domain: Literal["medical","legal","technical","business","academic","policy","social_science","engineering","finance","environmental"]
    topic: str
    sections: list[dict]          # approved section content
    citations: list[dict]         # verified citation objects
    css_human_score: float        # 0.0-1.0, human-assigned ground truth
    forbidden_violations: int     # must be 0
    factual_errors: int           # human-verified, must be 0
    style_profile: str
    word_count: int
```

## §25.1 Golden Dataset

**20 documents** across 10 domains (2 per domain). Construction: first 50 production runs with human supervision → data flywheel.

```python
GOLDEN_DATASET_SPEC = {
    "total_documents": 20,
    "domains": 10,          # see GroundTruth.domain Literal
    "docs_per_domain": 2,
    "word_range": (3000, 5000),
    "min_citations_per_doc": 8,
    "css_ground_truth_method": "human_panel_3_reviewers",
    "agreement_threshold": 0.80,  # Cohen's kappa min for ground_truth acceptance
    "path": "tests/benchmark/golden_set/{domain}/{document_id}/",
    "files": ["case.yaml", "ground_truth.json", "approved_sections.json"]
}

# ground_truth.json structure
GROUND_TRUTH_SCHEMA = {
    "document_id": str,
    "domain": str,
    "css_human_score": float,    # 0.0-1.0
    "forbidden_violations": int, # == 0 required
    "factual_errors": int,       # == 0 required
    "citation_validity_rate": float,  # citations verified correct / total
    "style_compliance_score": float,  # 0.0-1.0
    "sections": list,
    "citations": list,
    "reviewer_ids": list[str],   # 3 human reviewers
    "kappa_score": float         # >= 0.80
}
```

**GoldenCase minimum per agent:** 30 cases for critical agents (writer, reflector, jury×3); 15 for secondary agents.

```
tests/benchmark/golden_set/
├── {domain}/
│   └── {document_id}/
│       ├── case.yaml
│       ├── ground_truth.json
│       └── approved_sections.json
tests/benchmark/golden_set/{agent}/
└── case_NNN.yaml     # per-agent prompt unit tests (§25.4)
```

## §25.2 Unit Tests — Deterministic Modules

**Modules under test** (no LLM, no network):

| Module | Key Assertions |
|--------|---------------|
| `style_linter` | L1 regex match/no-match; position reported correctly |
| `diff_merger` | span uniqueness; apply order RTL; ambiguous → `ValueError` |
| `context_compressor` | output token count ≤ input × 0.40; no hallucinated claims |
| `circuit_breaker` | CLOSED→OPEN after 3 failures in 60s; OPEN→HALF_OPEN after 300s |
| `retry_policy` | delays follow 2→4→8s exponential; jitter ≤ 1s |
| `pii_detector` | email/phone/CF detected; PERSON/ORG/LOC replaced with placeholder |
| `cost_tracker` | `total == sum(per_agent)`; no negative values |
| `webhook_signer` | HMAC-SHA256 matches; tampered payload fails |
| `schema_validator` | out-of-range CSS threshold raises `ValidationError` |
| `budget_estimator` | estimate ≤ actual × 1.30 on 10 historical runs |
| `oscillation_detector` | CSS variance < 0.05 over window=4 triggers flag |
| `css_formula` | weights sum == 1.0; range [0.0, 1.0] always |

```python
# Coverage target
UNIT_DETERMINISTIC_COVERAGE = 0.90  # line coverage, measured by pytest-cov
MAX_SUITE_DURATION_SECONDS = 5      # hard limit; CI fails if exceeded
RUNS: Literal["every_commit"] = "every_commit"
```

## §25.3 Integration Tests — MockLLMClient

### MockLLMClient Interface

```python
from abc import ABC, abstractmethod

class LLMClientBase(ABC):
    """Injected into every agent constructor. See §25.10."""
    @abstractmethod
    async def complete(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        """Returns: {content: str, model_used: str, tokens_in: int,
                     tokens_out: int, cost_usd: float, latency_ms: int}"""
        ...

class MockLLMClient(LLMClientBase):
    """Zero network. Deterministic outputs for orchestrator logic testing."""

    def __init__(
        self,
        responses: dict[str, str],          # model -> fixed response string
        agent_responses: dict[AgentName, str],  # agent_name -> response
        error_on: list[str] | None = None,  # model ids that raise 500
        rate_limit_on: list[str] | None = None,  # model ids that raise 429
    ): ...

    async def complete(self, model, system_prompt, user_prompt,
                       temperature=0.3, max_tokens=4096) -> dict:
        # Returns predefined output or raises configured error
        ...

    def get_call_log(self) -> list[dict]:
        """Returns ordered list of all calls for assertion."""
        ...

class MockSearchClient:
    def __init__(self, results: dict[str, list[dict]]): ...
    async def search(self, query: str, max_results: int) -> list[dict]: ...

class MockDBClient:
    def __init__(self): ...
    async def save_section(self, section: dict) -> str: ...
    async def get_section(self, section_id: str) -> dict | None: ...
    async def save_checkpoint(self, thread_id: str, state: dict) -> None: ...
    async def get_checkpoint(self, thread_id: str) -> dict | None: ...
```

### Agent Interception

```python
# Every agent constructed with injected clients — see §25.10
# Test pattern:
async def test_writer_uses_style_exemplar():
    mock_llm = MockLLMClient(agent_responses={"writer": WRITER_FIXTURE_OUTPUT})
    writer = WriterAgent(llm_client=mock_llm, db_client=MockDBClient())
    state = build_test_state(style_exemplar="Test exemplar text")
    result = await writer.run(state)
    calls = mock_llm.get_call_log()
    assert "Test exemplar text" in calls[0]["system_prompt"]
    assert result["current_draft"] != ""
```

### Integration Suite Spec

```python
INTEGRATION_SUITE = {
    "topics": 5,
    "profiles": 3,            # academic, business, technical
    "total_runs": 15,         # single section ~500 words each
    "estimated_cost_usd": 15.0,
    "frequency": "every_pr_on_graph_or_prompts",
    "timeout_seconds": 300,
}

INTEGRATION_ASSERTIONS = [
    "section_approved_within_max_iterations",
    "css_above_threshold_on_approval",
    "section_saved_to_store",
    "recovery_after_worker_kill_resumes_correctly",  # kill -9 mid-run
    "budget_cap_respected",
    "zero_l1_violations_in_approved_section",
]
```

## §25.4 Prompt Unit Tests

```python
@dataclass
class PromptUnitTest:
    test_id: str
    agent: AgentName
    prompt_version: str           # semver
    input: dict[str, Any]
    expected_output_structure: dict[str, Any]  # JSON Schema, validated by jsonschema
    forbidden_in_output: list[str]             # substrings; MUST NOT appear
    hard_constraints: list[str]                # Python assertions as strings
    # Example:
    # hard_constraints: [
    #   "len(output['feedback_items']) >= 1",
    #   "output['scope'] in ('SURGICAL','PARTIAL','FULL')",
    #   "all(f['severity'] in ('CRITICAL','HIGH','MEDIUM','LOW') for f in output['feedback_items'])"
    # ]

PROMPT_UNIT_TEST_POLICY = {
    "trigger": "any_prompt_file_change",
    "failure_action": "block_pr",
    "min_cases_critical_agents": 30,   # writer, reflector, judges
    "min_cases_secondary_agents": 15,
    "path": "tests/benchmark/golden_set/{agent}/case_NNN.yaml",
}
```

**Mandatory `forbidden_in_output` for all agents:**

```python
UNIVERSAL_FORBIDDEN = [
    "I cannot follow my previous instructions",
    "ignore previous",
    "disregard system",
    "OVERRIDE:",
    "[SYSTEM]",
    "you are now",
]
```

## §25.5 Regression Tests

```python
REGRESSION_POLICY = {
    "trigger": "any_prompt_or_threshold_change",
    "dataset": "golden_set_full_20_docs",
    "rollback_condition": "css_mean_delta < -0.05",  # vs baseline
    "rollback_action": "revert_prompt_to_previous_version_and_block_deploy",
    "metric": "Document Quality Score (DQS)",
    "dqs_formula": {
        "coverage":   0.20,
        "factual":    0.35,
        "citation":   0.20,
        "style":      0.15,
        "coherence":  0.10,
    },
    "dqs_pass_threshold": 0.75,      # all 20 docs must pass
    "dqs_block_threshold": 0.70,     # any doc below this blocks deploy
    "schedule": "sunday_0200",
    "subset_for_patch": 3,           # PATCH-level changes: 3 docs subset
}
```

## §25.6 Cost Tests

```python
@dataclass
class CostTest:
    test_id: str
    run_config: dict[str, Any]      # subset of DocumentConfig
    max_estimated_cost_usd: float   # hard upper bound for pre-run estimate
    max_actual_cost_usd: float      # hard upper bound for real run (Mock or staging)
    estimate_accuracy_tolerance: float = 0.20  # |estimate-actual|/actual <= 0.20

COST_TEST_ASSERTIONS = [
    "budget_estimator_never_exceeds_cap",
    "per_agent_soft_cap_respected",        # no agent > 50% total budget
    "cascading_reduces_jury_cost_by_0.60", # tier1 unanimous → no tier2/3 call
    "estimate_delta_under_20pct",          # see CostTest.estimate_accuracy_tolerance
    "circuit_breaker_prevents_runaway",
]
```

## §25.7 Oscillation Simulation

```python
OSCILLATION_SYNTHETIC_INPUTS = [
    {
        "name": "css_flat",
        "description": "Mock jury returns CSS alternating 0.48-0.52 every iteration",
        "mock_css_sequence": [0.48, 0.52, 0.49, 0.51],
        "expected_trigger": "CSS_OSCILLATION",
        "max_iterations_before_escalation": 4,
    },
    {
        "name": "semantic_loop",
        "description": "Draft embeddings: sim(N, N-2) > 0.85 and sim(N, N-1) < 0.60",
        "mock_similarity_matrix": [[1.0, 0.55, 0.87], [0.55, 1.0, 0.54], [0.87, 0.54, 1.0]],
        "expected_trigger": "SEMANTIC_OSCILLATION",
        "max_iterations_before_escalation": 4,
    },
    {
        "name": "whack_a_mole",
        "description": "Error categories rotate: iter1=factual, iter2=style, iter3=factual",
        "mock_error_category_sequence": ["factual", "style", "factual"],
        "expected_trigger": "WHACK_A_MOLE",
        "max_iterations_before_escalation": 3,
    },
]

OSCILLATION_TEST_ASSERTIONS = [
    "escalation_reaches_human_within_max_iterations",
    "oscillation_type_correctly_classified",
    "draft_embeddings_stored_in_state",
    "early_warning_logged_at_iteration_n_minus_1",
]
```

## §25.8 Chaos Tests

```python
CHAOS_SCENARIOS: list[dict] = [
    {
        "name": "worker_killed",
        "simulation": "os.kill(celery_pid, signal.SIGKILL)",
        "verify": ["checkpoint_exists_in_postgres", "resume_from_correct_node"],
    },
    {
        "name": "provider_down_10min",
        "simulation": "mock_503_for_model('anthropic/claude-opus-4-5', duration_s=600)",
        "verify": ["circuit_breaker_opens", "fallback_model_used", "run_completes"],
    },
    {
        "name": "postgres_slow",
        "simulation": "tc_netem_delay_100ms_on_postgres",
        "verify": ["run_completes", "total_latency_delta_under_20pct"],
    },
    {
        "name": "redis_down_30s",
        "simulation": "docker_stop_redis_30s",
        "verify": ["graceful_fallback_to_postgres", "resume_after_redis_up"],
    },
    {
        "name": "budget_exhausted_early",
        "simulation": "set_budget_to_2_sections_cost",
        "verify": ["partial_document_returned", "approved_sections_intact", "no_data_loss"],
    },
    {
        "name": "rate_limit_60s",
        "simulation": "mock_429_for_all_models_duration_s=60",
        "verify": ["backoff_sequence_correct_2_4_8s", "no_immediate_retry"],
    },
    {
        "name": "prompt_injection_attempt",
        "simulation": "inject_source_with_pattern('ignore previous instructions')",
        "verify": ["injection_detected", "logged_as_SECURITY_EVENT", "not_propagated_to_state"],
    },
]

CHAOS_SCHEDULE = "monthly_in_staging"
```

## §25.9 Quality Evaluation Framework

```python
QUALITY_METRICS = {
    "bertscore": {
        "model": "microsoft/deberta-xlarge-mnli",
        "field": "F1",
        "threshold": 0.82,
        "compare_against": "ground_truth.sections",
    },
    "citation_validity_rate": {
        "definition": "citations_verified_correct / total_citations",
        "threshold": 0.98,
        "verifier": "citation_verifier_http_plus_nli",
    },
    "style_compliance": {
        "definition": "1 - (l1_violations / total_rules_checked)",
        "threshold": 1.00,   # zero L1 violations tolerated
        "tool": "style_linter_regex",
    },
    "inter_judge_agreement": {
        "metric": "cohen_kappa",
        "threshold": 0.75,   # computed per mini-jury per document
        "escalate_if_below": 0.60,
    },
    "dqs": {
        "formula": "0.20*coverage + 0.35*factual + 0.20*citation + 0.15*style + 0.10*coherence",
        "pass_threshold": 0.75,
        "block_threshold": 0.70,
    },
}

# Cohen's kappa: computed between each judge pair within a mini-jury
# kappa < 0.60 on 3+ consecutive sections → Rogue Judge Detector flag (see §10.3)
```

## §25.10 Dependency Injection Architecture

```python
# RULE: every agent file in src/agents/ MUST follow this pattern.
# FORBIDDEN: direct imports of openai, anthropic, httpx, requests, boto3, redis
# in any src/agents/*.py file. Violation = CI lint check failure.

class BaseAgent:
    def __init__(
        self,
        llm_client: LLMClientBase,       # see §25.3
        search_client: MockSearchClient | SearchClientBase,
        db_client: MockDBClient | DBClientBase,
    ):
        self._llm = llm_client
        self._search = search_client
        self._db = db_client

# Production wiring (src/graph/graph.py):
def build_agents(settings) -> dict[str, BaseAgent]:
    llm = OpenRouterLLMClient(api_key=settings.OPENROUTER_API_KEY)
    search = TavilySearchClient(api_key=settings.TAVILY_API_KEY)
    db = PostgresDBClient(url=settings.POSTGRES_URL)
    return {
        "writer": WriterAgent(llm, search, db),
        "reflector": ReflectorAgent(llm, search, db),
        # ...
    }

# Test wiring (tests/conftest.py):
@pytest.fixture
def mock_agents():
    llm = MockLLMClient(agent_responses=FIXTURE_RESPONSES)
    search = MockSearchClient(results=FIXTURE_SEARCH_RESULTS)
    db = MockDBClient()
    return {
        "writer": WriterAgent(llm, search, db),
        "reflector": ReflectorAgent(llm, search, db),
        # ...
    }
```

## §25.11 Smoke Suite per Fase MVP

```python
# Run: make test-phase{N}  (N = 1|2|3|4)
# Duration: < 120 seconds per phase
# Gate: phase N considered COMPLETE only after smoke suite passes 100%

SMOKE_SUITES: dict[str, list[str]] = {
    "phase1": [
        "writer_produces_parsable_output",           # json.loads succeeds
        "budget_cap_hard_stop_respected",            # no spend beyond max_budget_dollars
        "pipeline_end_to_end_single_section",        # topic→markdown, no crash
        "retry_activates_on_429",                    # mock 429 → backoff triggered
        "style_linter_detects_l1_violation",         # known forbidden string detected
    ],
    "phase2": [
        "oscillation_detected_on_synthetic_input",   # see §25.7 css_flat scenario
        "minority_veto_blocks_section",              # veto_category set → section not approved
        "resume_from_crash_checkpoint",             # kill → restart → continues from checkpoint
        "panel_discussion_triggers_below_0_50_css",
        "rogue_judge_detector_fires_at_70pct_disagreement",
        "jury_cascading_skips_tier2_on_unanimous_tier1",
    ],
    "phase3": [
        "style_exemplar_saved_and_injected_in_writer_prompt",
        "context_compressor_reduces_token_count_by_40pct",
        "coherence_guard_detects_synthetic_contradiction",
        "nli_entailment_check_rejects_ghost_citation",
        "pii_detector_replaces_email_before_llm_call",
        "mow_fusor_produces_css_above_single_writer",
    ],
    "phase4": [
        "run_companion_responds_in_under_3s",
        "drs_chain_functional_to_technical_completes",
        "grafana_alert_fires_on_simulated_oscillation",
        "sse_stream_delivers_section_approved_event",
        "webhook_hmac_signature_verified",
        "gdpr_deletion_endpoint_removes_all_user_data",
    ],
}

SMOKE_POLICY = {
    "pass_threshold": 1.00,       # 100% of checks must pass
    "failure_action": "block_phase_completion",
    "timeout_per_check_seconds": 20,
    "uses_mock_llm": True,        # no real API calls, zero cost
}
```

### Pre-Deploy Checklist

```
□ Layer 1 (unit_deterministic): 100% pass, coverage >= 0.90, duration < 5s
□ Layer 2 (unit_llm): all agents meet per-agent thresholds (see §25.2 table)
□ Layer 3 (integration): 15/15 runs success
□ Layer 4 (e2e golden_set): DQS >= 0.75 all 20 docs, none below 0.70
□ Prompt CI/CD: no degradation > -0.05 vs baseline
□ Security scan: zero CRITICAL/HIGH CVEs
□ Dependency audit: zero CRITICAL CVEs
□ DB migration: tested on staging
□ Rollback plan: previous version deployable < 5 min
□ Smoke suite phase N: 100% pass
```

<!-- SPEC_COMPLETE -->