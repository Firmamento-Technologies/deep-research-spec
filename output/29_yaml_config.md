# §29 — YAML Configuration & Pydantic Validation Schema

## §29.1 User Section

```yaml
# config/drs_config.yaml — ANNOTATED REFERENCE (all params shown)

user:
  max_budget_dollars: 50.0        # float, range [1.0, 500.0]; pre-run estimator blocks if projected > this
  target_words: 10000             # int, range [500, 50000]; drives section word budgets
  language: "it"                  # BCP-47 code; drives model selection for jury_style (see §28.1)
  style_profile: "academic"       # Literal["academic","business","technical","journalistic","narrative_essay","ai_instructions","blog","software_spec"]
  quality_preset: "balanced"      # Literal["economy","balanced","premium"]; auto-derives CSS/iter/jury_size (see §19.2)
  output_formats:                 # min 1 item
    - "docx"
    - "pdf"
    - "markdown"
  citation_style: "APA"           # Literal["APA","Harvard","Chicago","Vancouver"]
```

## §29.2 Models Section

```yaml
models:
  # Per-agent primary model + fallback chain (see §28.1 for rationale)
  planner: "google/gemini-2.5-pro"
  researcher: "perplexity/sonar-pro"
  writer: "anthropic/claude-opus-4-5"           # Writer W-A/B/C all use this (see §7.2)
  fusor: "openai/o3"
  reflector: "openai/o3"
  compressor: "qwen/qwen3-7b"
  post_draft_analyzer: "google/gemini-2.5-flash"
  style_fixer: "anthropic/claude-sonnet-4"
  span_editor: "anthropic/claude-sonnet-4"
  run_companion: "google/gemini-2.5-pro"
  source_synthesizer: "anthropic/claude-sonnet-4"

  # Reasoning jury: THREE INDEPENDENT PER-SLOT assignments (§28.2 + §8.5).
  # Each slot has its own primary model for epistemic decorrelation.
  # Slots run in parallel; each has its own fallback chain (§8.5 REASONING_SLOT_FALLBACKS).
  # Primary assignments (§28.2 REASONING_JUDGE_SLOTS, authoritative):
  #   judge_r1: deepseek/deepseek-r1
  #   judge_r2: openai/o3-mini
  #   judge_r3: qwen/qwq-32b
  # MUST NOT express reasoning jury as a single shared tier1/tier2/tier3 cascade.
  jury_reasoning:
    judge_r1:
      primary: "deepseek/deepseek-r1"
      fallbacks:
        - "openai/o3-mini"
        - "qwen/qwq-32b"
    judge_r2:
      primary: "openai/o3-mini"
      fallbacks:
        - "deepseek/deepseek-r1"
        - "qwen/qwq-32b"
    judge_r3:
      primary: "qwen/qwq-32b"
      fallbacks:
        - "deepseek/deepseek-r1"
        - "openai/o3-mini"

  # Factual jury: shared tier cascade (no per-slot decorrelation requirement)
  jury_factual:
    tier1: "perplexity/sonar"
    tier2: "google/gemini-2.5-flash"
    tier3: "perplexity/sonar-pro"

  # Style jury: shared tier cascade (no per-slot decorrelation requirement)
  jury_style:
    tier1: "meta/llama-3.3-70b-instruct"
    tier2: "mistral/mistral-large-2411"
    tier3: "openai/gpt-4.5"

  fallbacks:                      # ordered list; tried in sequence if primary + circuit breaker open
    writer:
      - "anthropic/claude-sonnet-4"
      - "google/gemini-2.5-pro"
    reflector:
      - "openai/o3-mini"
      - "anthropic/claude-opus-4-5"
    fusor:
      - "openai/o3-mini"
      - "anthropic/claude-opus-4-5"
    run_companion:
      - "anthropic/claude-sonnet-4"

  writer_temperatures:            # MoW angles (see §7.2); applied to all three proposers
    w_a_coverage: 0.30
    w_b_argumentation: 0.60
    w_c_readability: 0.80
```

## §29.3 Convergence Section

```yaml
convergence:
  # CSS Content Gate (Jury R + F only); see §9.3 THRESHOLD_TABLE for regime values
  # Economy=0.65, Balanced=0.70, Premium=0.78 — set by BudgetController at runtime
  css_content_threshold: 0.65     # float [0.50, 0.95]; section blocked if CSS_content < this

  # CSS Style Pass (Jury S only); see §9.3 THRESHOLD_TABLE for regime values
  # Economy=0.75, Balanced=0.80, Premium=0.85 — set by BudgetController at runtime
  css_style_threshold: 0.80       # float [0.60, 1.00]; must be >= css_content_threshold

  # Panel Discussion trigger; see §11.1 and §9.3 THRESHOLD_TABLE
  # Economy=0.40, Balanced=0.50, Premium=0.55 — set by BudgetController at runtime
  css_panel_threshold: 0.50       # float [0.30, css_content_threshold)

  # Oscillation detection window (see §13.1)
  oscillation_window: 4           # int [3, 10]; consecutive iterations checked
  oscillation_variance_threshold: 0.05  # float [0.01, 0.20]; CSS variance below this = stalled
  oscillation_semantic_similarity: 0.85 # float [0.70, 0.99]; cosine sim draft_N vs draft_{N-2}

  max_iterations_per_section: 4   # int [1, 12]; hard cap per section (overridden by budget regime)
  panel_max_rounds: 2             # int [1, 3]

  # Jury weights for CSS_composite (Run Report only); see §9.2
  # Routing uses CSS_content and CSS_style directly, not the composite.
  # Must sum to 1.0.
  jury_weights:
    reasoning: 0.35
    factual: 0.45
    style: 0.20

  minority_veto_l1_enabled: true  # bool; fabricated_source/factual_error/logical_contradiction/plagiarism
  minority_veto_l2_enabled: true  # bool; unanimous 0/3 in any mini-jury blocks regardless of CSS

  # Rogue judge detection threshold (see §10.3)
  rogue_judge_disagreement_threshold: 0.70  # float [0.50, 0.95]; disagreement rate over 3+ sections
```

## §29.4 Sources Section

```yaml
sources:
  web:
    - provider: "tavily"
      enabled: true
      fallback_only: false
    - provider: "brave"
      enabled: true
      fallback_only: true         # used only if tavily returns 429/500

  academic:
    - provider: "crossref"
      enabled: true
    - provider: "semantic_scholar"
      enabled: true
    - provider: "arxiv"
      enabled: false

  social:
    - provider: "reddit"
      enabled: false

  scraper_fallback:
    enabled: true                 # BeautifulSoup + Playwright if all APIs down (see §17.5)
    respect_robots_txt: true

  max_sources_per_section: 15     # int [3, 50]
  min_sources_per_section: 3      # int [1, max_sources_per_section]

  # Source diversity enforcement (see §17.8)
  diversity:
    max_same_publisher_pct: 0.40  # float [0.10, 0.80]
    max_same_author_pct: 0.30     # float [0.10, 0.60]
    max_same_year_pct: 0.50       # float [0.20, 0.90]

  # Base reliability scores per source type (see §17.1-17.4)
  reliability_scores:
    academic: 0.85
    institutional: 0.85
    web_general: 0.55
    social: 0.30

  # Per-domain overrides (trumps type-level score)
  reliability_overrides:
    "yourdomain.com": 0.95
    "twitter.com": 0.25

  # Judge F micro-search throttle (see §8.2.1)
  micro_search:
    economy: false
    balanced: "low_confidence_only"   # Literal[false,"low_confidence_only",true]
    premium: true
    max_claims_per_eval: 3
    max_queries_per_claim: 2
```

## §29.5 Style Section

```yaml
style:
  # Reference to a profile file under src/style_presets/
  profile_ref: "academic"         # Literal["academic","business","technical","journalistic","narrative_essay","ai_instructions","blog","software_spec"]

  # Additional forbidden patterns beyond the profile (three accepted formats)
  extra_forbidden:
    # Format 1: plain string (exact match, case-insensitive)
    - "needless to say"
    # Format 2: regex pattern (prefixed with "re:")
    - "re:\\bIn conclusione[,.]"
    # Format 3: structured rule object
    - id: "custom_001"
      level: "L1"                 # Literal["L1","L2","L3"]
      pattern: "re:\\bit is worth noting\\b"
      message: "AI fingerprint phrase"
      fix_hint: "Delete or rephrase to assert claim directly"

  extra_required:                 # additional L2 required elements
    - id: "custom_req_001"
      level: "L2"
      description: "Must include at least one concrete numerical example"
      message: "No numerical example found in section"

  disabled_rules:                 # rule IDs from profile to suppress (L3 only; L1/L2 cannot be disabled)
    - "L3_005"
    - "L3_012"

  style_calibration_gate:
    enabled: true                 # bool; runs §3B.1 before Phase A
    max_attempts: 3               # int [1, 5]
```

## §29.6 Pydantic Validation Schema

```python
# src/config/schema.py
from __future__ import annotations
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator, field_validator
import re


# ── Leaf models ────────────────────────────────────────────────────────────────

class ReasoningJudgeSlot(BaseModel):
    """
    Per-slot config for one Reasoning jury judge (§28.2 + §8.5).
    primary: the first model called for this slot.
    fallbacks: tried in order when primary fails (circuit breaker or timeout).
    """
    primary: str
    fallbacks: list[str] = Field(min_length=1)


class JuryReasoningConfig(BaseModel):
    """
    Three independent per-slot assignments for the Reasoning jury.
    Epistemic decorrelation requires different primary models per slot (§28.2).
    Primary assignments match §28.2 REASONING_JUDGE_SLOTS:
      judge_r1: deepseek/deepseek-r1
      judge_r2: openai/o3-mini
      judge_r3: qwen/qwq-32b
    Fallback chains per slot are defined in §8.5 REASONING_SLOT_FALLBACKS.
    MUST NOT be expressed as a single shared tier1/tier2/tier3 cascade.
    """
    judge_r1: ReasoningJudgeSlot = ReasoningJudgeSlot(
        primary="deepseek/deepseek-r1",
        fallbacks=["openai/o3-mini", "qwen/qwq-32b"],
    )
    judge_r2: ReasoningJudgeSlot = ReasoningJudgeSlot(
        primary="openai/o3-mini",
        fallbacks=["deepseek/deepseek-r1", "qwen/qwq-32b"],
    )
    judge_r3: ReasoningJudgeSlot = ReasoningJudgeSlot(
        primary="qwen/qwq-32b",
        fallbacks=["deepseek/deepseek-r1", "openai/o3-mini"],
    )


class JuryTiers(BaseModel):
    """Shared tier cascade for Factual and Style juries (no per-slot decorrelation)."""
    tier1: str
    tier2: str
    tier3: str


class FallbackChain(BaseModel):
    writer: list[str] = Field(min_length=1)
    reflector: list[str] = Field(min_length=1)
    fusor: list[str] = Field(min_length=1)
    run_companion: list[str] = Field(min_length=1)


class WriterTemperatures(BaseModel):
    w_a_coverage: float = Field(0.30, ge=0.0, le=1.0)
    w_b_argumentation: float = Field(0.60, ge=0.0, le=1.0)
    w_c_readability: float = Field(0.80, ge=0.0, le=1.0)


class JuryWeights(BaseModel):
    reasoning: float = Field(ge=0.0, le=1.0)
    factual: float = Field(ge=0.0, le=1.0)
    style: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "JuryWeights":
        total = round(self.reasoning + self.factual + self.style, 6)
        if total != 1.0:
            raise ValueError(
                f"jury_weights must sum to 1.0, got {total}. "
                "Adjust reasoning + factual + style."
            )
        return self


class DiversityConfig(BaseModel):
    max_same_publisher_pct: float = Field(0.40, ge=0.10, le=0.80)
    max_same_author_pct: float = Field(0.30, ge=0.10, le=0.60)
    max_same_year_pct: float = Field(0.50, ge=0.20, le=0.90)


class ReliabilityScores(BaseModel):
    academic: float = Field(0.85, ge=0.0, le=1.0)
    institutional: float = Field(0.85, ge=0.0, le=1.0)
    web_general: float = Field(0.55, ge=0.0, le=1.0)
    social: float = Field(0.30, ge=0.0, le=1.0)


class MicroSearchConfig(BaseModel):
    economy: Literal[False] = False
    balanced: Literal[False, "low_confidence_only", True] = "low_confidence_only"
    premium: Literal[True] = True
    max_claims_per_eval: int = Field(3, ge=1, le=5)
    max_queries_per_claim: int = Field(2, ge=1, le=3)


class SourceProviderConfig(BaseModel):
    provider: str
    enabled: bool
    fallback_only: bool = False


class ForbiddenRuleObject(BaseModel):
    id: str
    level: Literal["L1", "L2", "L3"]
    pattern: str
    message: str
    fix_hint: str = ""

    @field_validator("pattern")
    @classmethod
    def validate_regex_pattern(cls, v: str) -> str:
        if v.startswith("re:"):
            try:
                re.compile(v[3:])
            except re.error as e:
                raise ValueError(
                    f"Invalid regex in pattern '{v}': {e}. "
                    "Prefix 're:' requires a valid Python regex after it."
                )
        return v


class RequiredRuleObject(BaseModel):
    id: str
    level: Literal["L2"] = "L2"
    description: str
    message: str


class StyleCalibrationGate(BaseModel):
    enabled: bool = True
    max_attempts: int = Field(3, ge=1, le=5)


# ── Section models ─────────────────────────────────────────────────────────────

class UserConfig(BaseModel):
    max_budget_dollars: float = Field(
        ge=1.0, le=500.0,
        description="Hard cap; pre-run estimator blocks if projected cost exceeds this."
    )
    target_words: int = Field(
        ge=500, le=50_000,
        description="Target document word count. Values <500 produce unusably short output."
    )
    language: str = Field(
        min_length=2, max_length=10,
        description="BCP-47 language code (e.g. 'it', 'en', 'de')."
    )
    style_profile: Literal[
        "academic", "business", "technical", "journalistic",
        "narrative_essay", "ai_instructions", "blog", "software_spec"
    ]
    quality_preset: Literal["economy", "balanced", "premium"] = "balanced"
    output_formats: list[Literal["docx", "pdf", "markdown", "latex", "html", "json"]] = Field(
        min_length=1,
        description="At least one format required."
    )
    citation_style: Literal["APA", "Harvard", "Chicago", "Vancouver"] = "APA"


class ModelsConfig(BaseModel):
    planner: str
    researcher: str
    writer: str
    fusor: str
    reflector: str
    compressor: str
    post_draft_analyzer: str
    style_fixer: str
    span_editor: str
    run_companion: str
    source_synthesizer: str
    # jury_reasoning: THREE independent per-slot configs (§28.2 + §8.5).
    # Each slot has its own primary model for epistemic decorrelation.
    # MUST NOT be a single shared tier cascade.
    jury_reasoning: JuryReasoningConfig = JuryReasoningConfig()
    # jury_factual/jury_style: shared tier cascades (no decorrelation requirement).
    jury_factual: JuryTiers = JuryTiers(
        tier1="perplexity/sonar",
        tier2="google/gemini-2.5-flash",
        tier3="perplexity/sonar-pro",
    )
    jury_style: JuryTiers = JuryTiers(
        tier1="meta/llama-3.3-70b-instruct",
        tier2="mistral/mistral-large-2411",
        tier3="openai/gpt-4.5",
    )
    fallbacks: FallbackChain
    writer_temperatures: WriterTemperatures = WriterTemperatures()


class ConvergenceConfig(BaseModel):
    css_content_threshold: float = Field(0.65, ge=0.50, le=0.95)
    css_style_threshold: float = Field(0.80, ge=0.60, le=1.00)
    css_panel_threshold: float = Field(0.50, ge=0.30)
    oscillation_window: int = Field(4, ge=3, le=10)
    oscillation_variance_threshold: float = Field(0.05, ge=0.01, le=0.20)
    oscillation_semantic_similarity: float = Field(0.85, ge=0.70, le=0.99)
    max_iterations_per_section: int = Field(4, ge=1, le=12)
    panel_max_rounds: int = Field(2, ge=1, le=3)
    jury_weights: JuryWeights
    minority_veto_l1_enabled: bool = True
    minority_veto_l2_enabled: bool = True
    rogue_judge_disagreement_threshold: float = Field(0.70, ge=0.50, le=0.95)

    @model_validator(mode="after")
    def threshold_ordering(self) -> "ConvergenceConfig":
        if self.css_style_threshold < self.css_content_threshold:
            raise ValueError(
                f"css_style_threshold ({self.css_style_threshold}) must be >= "
                f"css_content_threshold ({self.css_content_threshold}). "
                "Style pass is stricter than content gate."
            )
        if self.css_panel_threshold >= self.css_content_threshold:
            raise ValueError(
                f"css_panel_threshold ({self.css_panel_threshold}) must be < "
                f"css_content_threshold ({self.css_content_threshold}). "
                "Panel triggers only when content CSS is below approval threshold."
            )
        return self


class SourcesConfig(BaseModel):
    web: list[SourceProviderConfig] = Field(min_length=1)
    academic: list[SourceProviderConfig] = []
    social: list[SourceProviderConfig] = []
    scraper_fallback_enabled: bool = True
    respect_robots_txt: bool = True
    max_sources_per_section: int = Field(15, ge=3, le=50)
    min_sources_per_section: int = Field(3, ge=1)
    diversity: DiversityConfig = DiversityConfig()
    reliability_scores: ReliabilityScores = ReliabilityScores()
    reliability_overrides: dict[str, float] = {}
    micro_search: MicroSearchConfig = MicroSearchConfig()

    @model_validator(mode="after")
    def min_lte_max(self) -> "SourcesConfig":
        if self.min_sources_per_section > self.max_sources_per_section:
            raise ValueError(
                f"min_sources_per_section ({self.min_sources_per_section}) must be <= "
                f"max_sources_per_section ({self.max_sources_per_section})."
            )
        return self

    @field_validator("reliability_overrides")
    @classmethod
    def override_scores_in_range(cls, v: dict[str, float]) -> dict[str, float]:
        bad = {k: s for k, s in v.items() if not (0.0 <= s <= 1.0)}
        if bad:
            raise ValueError(
                f"reliability_overrides values must be in [0.0, 1.0]. "
                f"Out-of-range entries: {bad}"
            )
        return v


class StyleConfig(BaseModel):
    profile_ref: Literal[
        "academic", "business", "technical", "journalistic",
        "narrative_essay", "ai_instructions", "blog", "software_spec"
    ]
    extra_forbidden: list[Union[str, ForbiddenRuleObject]] = []
    extra_required: list[RequiredRuleObject] = []
    disabled_rules: list[str] = []
    style_calibration_gate: StyleCalibrationGate = StyleCalibrationGate()

    @field_validator("disabled_rules")
    @classmethod
    def only_l3_disabled(cls, v: list[str]) -> list[str]:
        bad = [r for r in v if not r.startswith("L3_")]
        if bad:
            raise ValueError(
                f"Only L3 rules can be disabled. Attempted to disable: {bad}. "
                "L1 (FORBIDDEN) and L2 (REQUIRED) rules are non-negotiable."
            )
        return v


# ── Root config ────────────────────────────────────────────────────────────────

class DRSConfig(BaseModel):
    user: UserConfig
    models: ModelsConfig
    convergence: ConvergenceConfig
    sources: SourcesConfig
    style: StyleConfig

    @model_validator(mode="after")
    def profile_consistency(self) -> "DRSConfig":
        if self.user.style_profile != self.style.profile_ref:
            raise ValueError(
                f"user.style_profile ('{self.user.style_profile}') must match "
                f"style.profile_ref ('{self.style.profile_ref}'). "
                "Set both to the same value or use one as the source of truth."
            )
        return self


# ── Loader ─────────────────────────────────────────────────────────────────────

def load_config(path: str) -> DRSConfig:
    """
    Raises ValidationError with field-level messages on any constraint violation.
    Call during preflight_node before any LLM call.
    """
    import yaml
    from pydantic import ValidationError

    with open(path) as f:
        raw = yaml.safe_load(f)
    try:
        return DRSConfig.model_validate(raw)
    except ValidationError as e:
        # Preserve structured error list for preflight_node to surface in Run Report
        raise
```

### Validation Error Reference

| Field | Condition | Error Message Pattern |
|---|---|---|
| `user.max_budget_dollars` | `< 1.0` or `> 500.0` | `"max_budget_dollars must be in [1.0, 500.0]"` |
| `user.target_words` | `< 500` | `"target_words <500 produces unusably short output"` |
| `convergence.jury_weights` | `sum != 1.0` | `"jury_weights must sum to 1.0, got {total}"` |
| `convergence.css_style_threshold` | `< css_content_threshold` | `"css_style_threshold must be >= css_content_threshold"` |
| `convergence.css_panel_threshold` | `>= css_content_threshold` | `"css_panel_threshold must be < css_content_threshold"` |
| `sources.reliability_overrides` | any value `∉ [0.0, 1.0]` | `"Out-of-range entries: {bad}"` |
| `sources.min_sources_per_section` | `> max_sources_per_section` | `"min_sources_per_section must be <= max_sources_per_section"` |
| `style.disabled_rules` | any rule not prefixed `L3_` | `"Only L3 rules can be disabled. Attempted: {bad}"` |
| `style.extra_forbidden` regex entry | invalid regex after `re:` | `"Invalid regex in pattern '{v}': {e}"` |
| `DRSConfig` | `user.style_profile != style.profile_ref` | `"user.style_profile must match style.profile_ref"` |

<!-- SPEC_COMPLETE -->