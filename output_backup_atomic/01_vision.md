Looking at the identified issue, I need to fix the `max_budget_dollars` field in `§1.4 MandatoryParams` — the value is already `le=500.0` which is correct. Let me re-read carefully.

The issue states:
- `§01_vision.md MandatoryParams` sets `le=500.0` ✓ (already correct)
- `§03_input_config.md DRSConfig` sets `le=10_000.0` (needs fixing in that file)
- `§29.6 UserConfig` sets `le=500.0` ✓ (already correct)

The file to fix IS `01_vision.md`, and looking at the current content, `MandatoryParams` already has `le=500.0`. The validation table also shows `500.0`. So the file is already correct on that field.

Wait — re-reading the FIX instruction: "Standardize max_budget_dollars upper bound to le=500.0 across all three files (§03_input_config.md DRSConfig, §01_vision.md MandatoryParams, §29.6 UserConfig). The le=10_000.0 in §03_input_config.md appears to be an error introduced during editing."

The current `01_vision.md` already has `le=500.0` in both the Pydantic model and the validation table. No change is needed to this file for the budget issue — it's already correct.

The file as provided is already correct with respect to the one issue that applies to it. I must output the file unchanged (since it's already correct) with the spec complete tag.

```markdown
# 01_vision.md — System Vision and Foundational Constraints
## §1.1–1.4

---

## §1.1 System Description

The Deep Research System (DRS) is a multi-agent AI pipeline that produces long-form, verifiable research documents through iterative section-by-section generation, multi-model jury evaluation, and human-in-the-loop checkpoints. A heterogeneous jury (3 mini-juries × 3 models each) evaluates each section draft independently; consensus is measured via Consensus Strength Score (CSS, see §9.1); sections are immutable once approved. The system enforces an inviolable budget ceiling before any token is consumed, adapts quality parameters dynamically to remaining budget, and persists full state to PostgreSQL enabling crash recovery at any checkpoint.

---

## §1.2 Use-Case Table

```python
from typing import Literal

DocType = Literal[
    "scientific_report",
    "business_report",
    "technical_documentation",
    "journalistic",
    "narrative_essay",
    "ai_instructions",
    "blog",
]

ComplexityLevel = Literal["standard", "high", "very_high"]
```

| `doc_type` | `word_range: tuple[int, int]` | `complexity: ComplexityLevel` |
|---|---|---|
| `"scientific_report"` | `(5_000, 50_000)` | `"very_high"` |
| `"business_report"` | `(3_000, 20_000)` | `"high"` |
| `"technical_documentation"` | `(2_000, 30_000)` | `"high"` |
| `"journalistic"` | `(1_500, 10_000)` | `"standard"` |
| `"narrative_essay"` | `(2_000, 15_000)` | `"standard"` |
| `"ai_instructions"` | `(1_000, 8_000)` | `"high"` |
| `"blog"` | `(500, 5_000)` | `"standard"` |

---

## §1.3 User-Type Table

```python
from typing import TypedDict

class UserPersona(TypedDict):
    persona: str
    primary_need: str
    user_story: str
    doc_types: list[DocType]
```

| `persona` | `primary_need` | `user_story` |
|---|---|---|
| `"researcher"` | Verified citations, academic rigor | As a researcher I want a fully-cited draft with NLI-verified sources so I can submit without manual fact-checking |
| `"professional"` | Actionable insights, tight budget | As a professional I want a business report under $30 so I can brief stakeholders without hiring a writer |
| `"developer"` | Machine-readable spec output | As a developer I want a multi-file software spec so a coding agent can implement without clarification |
| `"enterprise"` | Privacy, compliance, volume | As an enterprise user I want self-hosted LLM mode so no draft content leaves my infrastructure |

---

## §1.4 Mandatory Parameters

```python
from pydantic import BaseModel, Field, field_validator

class MandatoryParams(BaseModel):
    max_budget_dollars: float = Field(
        ...,
        ge=1.0,
        le=500.0,
        description="Hard ceiling; system never exceeds this value",
    )
    target_words: int = Field(
        ...,
        ge=500,
        le=50_000,
        description="Target word count for the final document",
    )

    @field_validator("max_budget_dollars")
    @classmethod
    def budget_precision(cls, v: float) -> float:
        # Reject sub-cent precision to avoid float comparison errors
        return round(v, 2)
```

### Validation Rules

| Parameter | Type | Min | Max | Hard-stop if violated |
|---|---|---|---|---|
| `max_budget_dollars` | `float` | `1.0` | `500.0` | Yes — preflight blocks execution |
| `target_words` | `int` | `500` | `50_000` | Yes — preflight blocks execution |

---

## §1.4.1 Derived Parameters

All parameters below are **computed automatically** from `MandatoryParams`; the user NEVER sets them directly. They are resolved by the Budget Estimator (see §19.1) and stored in `DocumentState.budget`.

```python
from typing import Literal

QualityPreset = Literal["Economy", "Balanced", "Premium"]

class DerivedParams(TypedDict):
    budget_per_word: float          # max_budget_dollars / target_words
    quality_preset: QualityPreset   # see §19.2 threshold table
    css_threshold: float            # ≥0.65 Economy | ≥0.70 Balanced | ≥0.78 Premium
    max_iterations_per_section: int # 2 Economy | 4 Balanced | 8 Premium
    jury_size: int                  # 1 Economy | 2 Balanced | 3 Premium
    estimated_sections: int         # ceil(target_words / 1_000)  [planning default]
    budget_per_section: float       # max_budget_dollars / estimated_sections
    mow_enabled: bool               # False if Economy; True otherwise
    panel_discussion_enabled: bool  # False if Economy; True otherwise
```

### Regime Derivation Rule

```python
def derive_quality_preset(budget_per_word: float) -> QualityPreset:
    if budget_per_word < 0.002:
        return "Economy"
    elif budget_per_word <= 0.005:
        return "Balanced"
    else:
        return "Premium"
```

> `budget_per_word` is the single scalar that deterministically cascades into all quality parameters. No other user input influences these derived values.

---

## §1.4.2 Cross-Reference Map

| Concept | Defined at |
|---|---|
| CSS formula | §9.1 |
| Quality regime table (full) | §19.2 |
| Budget Estimator logic | §19.1 |
| Pre-flight validation | §4.1 |
| `DocumentState` full schema | §4.6 |
| Style profiles | §26 |
| Mandatory YAML config schema | §29 |

<!-- SPEC_COMPLETE -->
```