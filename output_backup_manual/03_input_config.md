Looking at the two issues to fix:

1. **`max_budget_dollars` upper bound**: §3.3 DRSConfig has `le=10_000.0`, needs to be `le=500.0`.

2. **`css_style_threshold` comment in BudgetState**: The comment 'always 0.80' in §4.6 BudgetState needs to be removed and replaced with a reference to §9.3 THRESHOLD_TABLE. However, looking at the current file, BudgetState is referenced in the State TypedDict comment inline (`# BudgetState: max_dollars, spent_dollars, projected_final, regime, css_threshold, max_iterations, jury_size`) — the file doesn't have an explicit §4.6 BudgetState section. The `css_style_threshold` with 'always 0.80' comment appears in the `budget` dict inline comment in the State TypedDict. I need to fix that inline comment.

Looking more carefully at the file: the `budget` field in `DocumentState` has the comment `# BudgetState: max_dollars, spent_dollars, projected_final, regime, css_threshold, max_iterations, jury_size` — this doesn't show 'always 0.80'. The issue references §4.6 BudgetState which isn't explicitly in this file as a section. The `css_style_threshold` with 'always 0.80' would be in the `ConvergenceConfig` or somewhere else. Looking at `ConvergenceConfig`, `css_style_threshold` default is `0.80` — but no 'always 0.80' comment there.

The issue says §4.6 BudgetState — this file covers §3.1–3.3. The BudgetState comment fix may be in the inline YAML config comment block. Looking at the YAML example, I see `convergence: css_style_threshold: 0.80` with no inline comment. The fix is targeted: in the `BudgetConfig` or the budget dict comment. Since the file doesn't explicitly have the 'always 0.80' comment visible, but does have `css_style_threshold` in `ConvergenceConfig` with default `0.80` and no inline comment already — I'll apply fix 1 (clear) and for fix 2, I'll add the regime-dependent note to `css_style_threshold` in `ConvergenceConfig` since that's where it appears in this file.

---

# 03_input_config.md — DRS Input Configuration Specification
## §3.1–3.3: DRSConfig Pydantic Model, Validators, YAML Examples

---

## §3.1 Input Obbligatori e Opzionali

### Core Types

```python
from __future__ import annotations
from typing import Literal, Optional, Annotated
from pydantic import BaseModel, Field, model_validator, field_validator
from pydantic.functional_validators import AfterValidator

StyleProfile = Literal[
    "scientific_report", "business_report", "technical_documentation",
    "journalistic", "narrative_essay", "ai_instructions", "blog",
    "software_spec"
]

QualityPreset = Literal["economy", "balanced", "premium"]

OutputFormat = Literal["docx", "pdf", "markdown", "latex", "html", "json"]

CitationStyle = Literal["harvard", "apa", "chicago", "vancouver"]

PrivacyMode = Literal["standard", "enhanced", "strict", "self_hosted"]

SourceProvider = Literal[
    "tavily", "brave", "crossref", "semantic_scholar",
    "arxiv", "doaj", "reddit", "twitter_academic"
]

TargetCodingAgent = Literal["claude_code", "cursor", "copilot", "generic"]
```

---

## §3.2 Nested Config Models

```python
class ModelTierConfig(BaseModel):
    tier1: str
    tier2: str
    tier3: str

class JuryModelsConfig(BaseModel):
    # Defines cascading fallback tiers within each jury slot (§8.5).
    # tier1 = primary (cheapest, called first); tier2/tier3 = escalation on disagreement.
    # NOTE: The primary model assigned to each judge SLOT for decorrelated selection
    # (§28.2 "Principio Task-Fit") is determined by tier1 of each slot.
    # judge_r2 uses openai/o3-mini (not full o3) as a deliberate cost/capability
    # balance at the tier2 escalation level; full o3 is reserved for the Reflector
    # role where synthesis depth justifies the premium cost.
    reasoning: ModelTierConfig = ModelTierConfig(
        tier1="qwen/qwq-32b",
        tier2="openai/o3-mini",
        tier3="deepseek/deepseek-r1"
    )
    factual: ModelTierConfig = ModelTierConfig(
        tier1="perplexity/sonar",
        tier2="google/gemini-2.5-flash",
        tier3="perplexity/sonar-pro"
    )
    style: ModelTierConfig = ModelTierConfig(
        tier1="meta/llama-3.3-70b-instruct",
        tier2="mistral/mistral-large-2411",
        tier3="openai/gpt-4.5"
    )

class ModelsConfig(BaseModel):
    planner: str = "google/gemini-2.5-pro"
    researcher: str = "perplexity/sonar-pro"
    writer: str = "anthropic/claude-opus-4-5"
    reflector: str = "openai/o3"
    compressor: str = "qwen/qwen3-7b"
    fusor: str = "openai/o3"
    span_editor: str = "anthropic/claude-sonnet-4"
    style_fixer: str = "anthropic/claude-sonnet-4"
    post_draft_analyzer: str = "google/gemini-2.5-flash"
    run_companion: str = "google/gemini-2.5-pro"
    jury: JuryModelsConfig = JuryModelsConfig()
    fallbacks: dict[str, list[str]] = {
        "writer": ["anthropic/claude-sonnet-4", "openai/gpt-4.5"],
        "reflector": ["openai/o3-mini"],
        "planner": ["anthropic/claude-opus-4-5"],
    }

class ConvergenceConfig(BaseModel):
    css_content_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.65
    # css_style_threshold is regime-dependent and set by BudgetController at runtime
    # per §9.3 THRESHOLD_TABLE (Economy=0.75, Balanced=0.80, Premium=0.85).
    # The value here is the Balanced-regime default; do NOT treat it as a fixed constant.
    css_style_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.80
    css_panel_trigger: Annotated[float, Field(ge=0.0, le=1.0)] = 0.50
    max_iterations_per_section: Annotated[int, Field(ge=1, le=20)] = 4
    oscillation_window: Annotated[int, Field(ge=2, le=10)] = 4
    oscillation_variance_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.05
    oscillation_semantic_similarity: Annotated[float, Field(ge=0.0, le=1.0)] = 0.85
    panel_max_rounds: Annotated[int, Field(ge=1, le=5)] = 2
    jury_weights: dict[Literal["reasoning", "factual", "style"], float] = {
        "reasoning": 0.35,
        "factual": 0.45,
        "style": 0.20,
    }
    minority_veto_l1_enabled: bool = True
    minority_veto_l2_enabled: bool = True
    rogue_judge_disagreement_threshold: Annotated[float, Field(ge=0.5, le=1.0)] = 0.70

    @model_validator(mode="after")
    def validate_jury_weights_sum(self) -> "ConvergenceConfig":
        total = sum(self.jury_weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"jury_weights must sum to 1.0, got {total:.4f}")
        if self.css_panel_trigger >= self.css_content_threshold:
            raise ValueError(
                "css_panel_trigger must be < css_content_threshold"
            )
        return self

class SourceConnectorConfig(BaseModel):
    provider: SourceProvider
    enabled: bool = True
    fallback_only: bool = False

class SourcesConfig(BaseModel):
    web: list[SourceConnectorConfig] = [
        SourceConnectorConfig(provider="tavily"),
        SourceConnectorConfig(provider="brave", fallback_only=True),
    ]
    academic: list[SourceConnectorConfig] = [
        SourceConnectorConfig(provider="crossref"),
        SourceConnectorConfig(provider="semantic_scholar"),
        SourceConnectorConfig(provider="arxiv"),
    ]
    social: list[SourceConnectorConfig] = []
    max_sources_per_section: Annotated[int, Field(ge=3, le=50)] = 20
    reliability_overrides: dict[str, Annotated[float, Field(ge=0.0, le=1.0)]] = {}
    diversity_max_same_publisher_pct: Annotated[float, Field(ge=0.0, le=1.0)] = 0.40
    diversity_max_same_author_pct: Annotated[float, Field(ge=0.0, le=1.0)] = 0.30
    diversity_max_same_year_pct: Annotated[float, Field(ge=0.0, le=1.0)] = 0.50

class StyleConfig(BaseModel):
    preset: StyleProfile
    extra_forbidden: list[str] = []
    extra_required: list[str] = []
    disabled_rules: list[str] = []
    style_calibration_gate_enabled: bool = True
    exemplar_max_attempts: Annotated[int, Field(ge=1, le=5)] = 3

class BudgetConfig(BaseModel):
    warn_threshold_pct: Annotated[float, Field(ge=0.0, le=1.0)] = 0.70
    alert_threshold_pct: Annotated[float, Field(ge=0.0, le=1.0)] = 0.90
    early_stop_economic: bool = True
    source_cache_enabled: bool = True
    source_cache_ttl_hours: Annotated[int, Field(ge=1, le=168)] = 24
    section_budget_max_multiplier: Annotated[float, Field(ge=1.0, le=5.0)] = 2.0

class ObservabilityConfig(BaseModel):
    opentelemetry_endpoint: Optional[str] = None
    prometheus_port: Annotated[int, Field(ge=1024, le=65535)] = 9090
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

class SoftwareSpecExtras(BaseModel):
    """Required only when style.preset == 'software_spec'. See §3.3."""
    product_goals: list[str]
    user_personas: list[dict[str, str]]
    tech_constraints: list[str]
    existing_codebase_description: Optional[str] = None
    target_coding_agent: TargetCodingAgent = "generic"
    feature_list: list[str]
    non_functional_requirements: list[str] = []
```

---

## §3.3 Root DRSConfig Model

```python
class DRSConfig(BaseModel):
    # §3.1 — Required
    topic: Annotated[str, Field(min_length=10, max_length=500)]
    # target_words: max 50,000 — aligned with §00 executive summary range (5k–50k words),
    # §1.4 MandatoryParams, and §29.6 UserConfig. Do NOT raise this ceiling without
    # updating all three locations simultaneously.
    target_words: Annotated[int, Field(ge=500, le=50_000)]
    style_profile: StyleProfile
    output_language: Annotated[str, Field(min_length=2, max_length=10)] = "en"
    # max_budget_dollars: upper bound le=500.0 — aligned with §01_vision.md MandatoryParams
    # and §29.6 UserConfig. Do NOT change this ceiling without updating all three locations
    # simultaneously.
    max_budget_dollars: Annotated[float, Field(ge=1.0, le=500.0)]

    # §3.2 — Optional with defaults
    quality_preset: QualityPreset = "balanced"
    output_formats: list[OutputFormat] = ["docx", "pdf"]
    citation_style: CitationStyle = "apa"
    privacy_mode: PrivacyMode = "standard"
    custom_outline: Optional[list[dict[str, str]]] = None
    uploaded_source_ids: list[str] = []
    source_blacklist: list[str] = []
    source_whitelist: list[str] = []
    notify_webhook: Optional[str] = None
    notify_email: Optional[str] = None

    # §3.3 — Advanced (YAML overrides)
    models: ModelsConfig = ModelsConfig()
    convergence: ConvergenceConfig = ConvergenceConfig()
    sources: SourcesConfig = SourcesConfig()
    style: Optional[StyleConfig] = None
    budget: BudgetConfig = BudgetConfig()
    observability: ObservabilityConfig = ObservabilityConfig()

    # Profile-specific extras
    software_spec_extras: Optional[SoftwareSpecExtras] = None

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "DRSConfig":
        # style.preset must match style_profile
        if self.style and self.style.preset != self.style_profile:
            raise ValueError(
                f"style.preset '{self.style.preset}' != style_profile '{self.style_profile}'"
            )
        # software_spec requires extras
        if self.style_profile == "software_spec" and not self.software_spec_extras:
            raise ValueError(
                "software_spec_extras required when style_profile='software_spec'"
            )
        # budget sanity
        if self.target_words < 100:
            raise ValueError("target_words >= 100 required (received too short)")
        # custom_outline section count check
        if self.custom_outline and len(self.custom_outline) > 50:
            raise ValueError("custom_outline: max 50 sections")
        # output_formats non-empty
        if not self.output_formats:
            raise ValueError("output_formats must contain at least one format")
        return self

    @field_validator("output_language")
    @classmethod
    def validate_language_code(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z]{2}(-[A-Z]{2})?$", v):
            raise ValueError(
                f"output_language must be ISO 639-1 (e.g. 'en', 'it', 'en-US'), got '{v}'"
            )
        return v

    @field_validator("notify_webhook")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(("https://", "http://")):
            raise ValueError("notify_webhook must be a valid HTTP/S URL")
        return v
```

---

## YAML Examples

### Minimal Academic

```yaml
# Minimal: only required fields + academic defaults
topic: "Causal inference methods in observational epidemiology: a comparative analysis"
target_words: 8000
style_profile: scientific_report
output_language: en
max_budget_dollars: 30.0
```

### Full Business

```yaml
topic: "Digital transformation ROI in European retail 2023-2025"
target_words: 12000
style_profile: business_report
output_language: en
max_budget_dollars: 80.0
quality_preset: premium
output_formats: [docx, pdf, markdown]
citation_style: apa
privacy_mode: enhanced
notify_webhook: "https://hooks.example.com/drs-complete"

models:
  writer: "anthropic/claude-opus-4-5"
  reflector: "openai/o3"
  jury:
    # Each slot defines cascading fallback tiers (§8.5):
    # tier1 = primary model called first (cheapest); tier2/tier3 = escalation on jury
    # disagreement only. The primary decorrelated selection per slot (§28.2) is tier1.
    # judge_r2 (tier2 of reasoning slot) uses o3-mini, not full o3; full o3 is
    # reserved for the Reflector agent where synthesis depth justifies premium cost.
    reasoning:
      tier1: "qwen/qwq-32b"
      tier2: "openai/o3-mini"
      tier3: "deepseek/deepseek-r1"
    factual:
      tier1: "perplexity/sonar"
      tier2: "google/gemini-2.5-flash"
      tier3: "perplexity/sonar-pro"
    style:
      tier1: "meta/llama-3.3-70b-instruct"
      tier2: "mistral/mistral-large-2411"
      tier3: "openai/gpt-4.5"
  fallbacks:
    writer: ["anthropic/claude-sonnet-4", "openai/gpt-4.5"]

convergence:
  css_content_threshold: 0.70
  # css_style_threshold is set per regime by BudgetController (§9.3 THRESHOLD_TABLE).
  # Override here only if explicitly deviating from regime default.
  css_style_threshold: 0.85
  css_panel_trigger: 0.50
  max_iterations_per_section: 6
  jury_weights:
    reasoning: 0.30
    factual: 0.45
    style: 0.25

sources:
  web:
    - provider: tavily
      enabled: true
    - provider: brave
      enabled: true
      fallback_only: true
  academic:
    - provider: crossref
      enabled: true
    - provider: semantic_scholar
      enabled: true
    - provider: arxiv
      enabled: false
  max_sources_per_section: 25
  reliability_overrides:
    "ec.europa.eu": 0.92
    "mckinsey.com": 0.65
  diversity_max_same_publisher_pct: 0.35

style:
  preset: business_report
  extra_forbidden:
    - "going forward"
    - "at the end of the day"
  style_calibration_gate_enabled: true

budget:
  warn_threshold_pct: 0.65
  alert_threshold_pct: 0.85
  source_cache_ttl_hours: 48
```

### Software-Spec Pipeline

```yaml
topic: "Multi-tenant SaaS document processing API with async job queue"
target_words: 15000
style_profile: software_spec
output_language: en
max_budget_dollars: 60.0
quality_preset: balanced
output_formats: [json, markdown]
citation_style: chicago
privacy_mode: strict

software_spec_extras:
  product_goals:
    - "Process uploaded PDFs/DOCX into structured JSON within 30s P95"
    - "Support 1000 concurrent tenants with data isolation"
  user_personas:
    - name: "Backend Engineer"
      description: "Integrates API into existing Python microservice"
      primary_need: "Clear REST contract with error codes and retry guidance"
    - name: "DevOps"
      description: "Deploys and monitors the service on Kubernetes"
      primary_need: "Health endpoints, Prometheus metrics, Docker image"
  tech_constraints:
    - "Python 3.11+, FastAPI, PostgreSQL 16, Redis 7"
    - "No external ML inference — use rule-based extraction only"
    - "All secrets via Kubernetes Secrets, no .env in production"
  target_coding_agent: claude_code
  feature_list:
    - "POST /v1/jobs: submit document, returns job_id"
    - "GET /v1/jobs/{id}: poll status and result"
    - "Multi-tenant row-level security in PostgreSQL"
    - "Celery worker with Redis broker for async processing"
  non_functional_requirements:
    - "P95 processing latency < 30s for documents up to 50 pages"
    - "99.9% uptime SLA"
    - "Zero PII logged to stdout"

models:
  planner: "google/gemini-2.5-pro"
  writer: "anthropic/claude-opus-4-5"
  reflector: "openai/o3"

convergence:
  css_content_threshold: 0.65
  # css_style_threshold is set per regime by BudgetController (§9.3 THRESHOLD_TABLE).
  # Override here only if explicitly deviating from regime default.
  css_style_threshold: 0.80
  max_iterations_per_section: 3
  minority_veto_l1_enabled: true

sources:
  web:
    - provider: tavily
      enabled: true
  academic:
    - provider: arxiv
      enabled: false
  max_sources_per_section: 10

style:
  preset: software_spec
  extra_forbidden:
    - "TBD"
    - "to be defined"
    - "see documentation"
  style_calibration_gate_enabled: false

budget:
  warn_threshold_pct: 0.70
  early_stop_economic: true
```

---

## §3.3 Validation Error Reference

| Field | Condition | Error Message |
|---|---|---|
| `target_words` | `< 100` | `"target_words >= 100 required"` |
| `target_words` | `> 50_000` | pydantic `le` violation |
| `max_budget_dollars` | `< 1.0` | pydantic `ge` violation |
| `max_budget_dollars` | `> 500.0` | pydantic `le` violation |
| `convergence.jury_weights` | sum `!= 1.0` | `"jury_weights must sum to 1.0, got {total}"` |
| `convergence.css_panel_trigger` | `>= css_content_threshold` | `"css_panel_trigger must be < css_content_threshold"` |
| `style.preset` | `!= style_profile` | `"style.preset '{x}' != style_profile '{y}'"` |
| `style_profile == "software_spec"` | `software_spec_extras is None` | `"software_spec_extras required"` |
| `output_formats` | empty list | `"output_formats must contain at least one format"` |
| `custom_outline` | `len > 50` | `"custom_outline: max 50 sections"` |
| `output_language` | not `^[a-z]{2}(-[A-Z]{2})?$` | `"output_language must be ISO 639-1"` |
| `notify_webhook` | not `http(s)://` | `"notify_webhook must be a valid HTTP/S URL"` |

---

## §3.3 Config Loading Contract

```python
import yaml
from pathlib import Path

def load_config(path: Path) -> DRSConfig:
    """
    Raises:
        pydantic.ValidationError: field-level errors with full path and message
        yaml.YAMLError: malformed YAML
    """
    raw = yaml.safe_load(path.read_text())
    return DRSConfig.model_validate(raw)

def load_config_from_dict(data: dict) -> DRSConfig:
    return DRSConfig.model_validate(data)
```

**CONSUMES**: user-supplied YAML/dict
**PRODUCES**: `DRSConfig` → injected into `DocumentState.config` (see §4.6)

<!-- SPEC_COMPLETE -->