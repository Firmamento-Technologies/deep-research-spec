# 08_jury_system.md
## §8 — Jury System: Three Mini-Juries, CSS Formula, Verdict Schema

---

## §8.0 Overview

Three independent mini-juries (R/F/S) evaluate each draft in parallel via `asyncio.gather`. They operate as two sequential gates: **Content Gate** (R+F only) then **Style Pass** (S only). Each jury uses cascading economic tiers (§8.5). CSS formula defined in §9.1.

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

JurySlot    = Literal["R", "F", "S"]
JuryTier    = Literal["tier1", "tier2", "tier3"]
VetoCategory = Literal[
    "fabricated_source", "factual_error",
    "logical_contradiction", "plagiarism"
]
Confidence   = Literal["low", "medium", "high"]
Outcome      = Literal["PASS", "FAIL", "VETO"]
RewriteScope = Literal["SURGICAL", "PARTIAL", "FULL"]
```

---

## §8.1 Mini-Jury Reasoning (R)

**AGENT: JuryReasoning [§8.1]**
RESPONSIBILITY: Evaluate logical coherence and inter-section consistency

| Field | Value |
|-------|-------|
| MODEL | Per §28.2 REASONING_JUDGE_SLOTS: `judge_r1` primary = `deepseek/deepseek-r1`; `judge_r2` primary = `openai/o3-mini`; `judge_r3` primary = `qwen/qwq-32b`. The three slots run in parallel with different primary models for epistemic decorrelation. Per-slot fallback chains are defined in §8.5 REASONING_SLOT_FALLBACKS. |
| TEMP | 0.1 |
| MAX_TOKENS | 1024 |

INPUT:
```python
draft:            str         # current section draft
outline:          list[dict]  # full outline for coherence context
approved_summaries: list[str] # compressed prior sections (see §14)
section_idx:      int
iteration:        int
jury_weights:     dict        # {"reasoning": 0.35, "factual": 0.45, "style": 0.20}
```

OUTPUT: `VerdictJSON` (see §8.6)

CONSTRAINTS:
- MUST set `verdict = "VETO"` only for `veto_category in ["logical_contradiction"]`
- MUST populate `failed_claims` with verbatim text spans when `verdict != "PASS"`
- NEVER evaluate style, citations, or factual accuracy (scope: logic only)
- MUST include `confidence` field; `confidence = "low"` logged but does not trigger micro-search
- ALWAYS score all four `dimension_scores` keys defined in §8.6

ERROR_HANDLING:
- JSON parse failure → retry with simplified prompt once → if still fails: `verdict="FAIL"`, `confidence="low"`, `comments="parse_error"`, flag `JURY_DEGRADED`
- Timeout (>45s) → circuit breaker (see §20.3) → fallback to next model in per-slot chain (§8.5)
- All tiers exhausted → `verdict="FAIL"`, set `state["jury_degraded"][slot]= True`

CONSUMES: `[current_draft, outline, approved_sections]` from DocumentState
PRODUCES: `[jury_verdicts]` → DocumentState

**Evaluation Rubric — Dimensions R:**

| Dimension | Weight | Threshold | Description |
|-----------|--------|-----------|-------------|
| `logical_flow` | 0.35 | ≥ 0.65 | Premises support conclusions, no non-sequiturs |
| `causal_validity` | 0.25 | ≥ 0.60 | Causal claims are directionally sound |
| `inter_section_coherence` | 0.25 | ≥ 0.70 | No contradiction with approved summaries |
| `argument_completeness` | 0.15 | ≥ 0.60 | Main claim has sufficient supporting structure |

---

## §8.2 Mini-Jury Factual (F)

**AGENT: JuryFactual [§8.2]**
RESPONSIBILITY: Verify claim-source fidelity and detect fabricated citations

| Field | Value |
|-------|-------|
| MODEL | `perplexity/sonar` (tier1) / `google/gemini-2.5-flash` (tier2) / `perplexity/sonar-pro` (tier3) |
| TEMP | 0.0 |
| MAX_TOKENS | 1500 |

INPUT:
```python
draft:              str
citation_map:       dict[str, str]   # source_id → formatted citation
verified_sources:   list[dict]       # from CitationVerifier (§5.4)
quality_preset:     Literal["Economy", "Balanced", "Premium"]
section_idx:        int
iteration:          int
```

OUTPUT: `VerdictJSON` (see §8.6) — includes `external_sources_consulted` when micro-search fires (§8.2.1)

CONSTRAINTS:
- MUST set `veto_category = "fabricated_source"` if DOI/URL not in `verified_sources` and claim is presented as fact
- MUST populate `missing_evidence: list[str]` with claim text for unsupported claims
- NEVER evaluate style, logic, or readability
- ALWAYS set `confidence` based on search tool availability: tool available → `"high"` possible; tool unavailable → max `"medium"`

ERROR_HANDLING:
- Search API 429 → exponential backoff 2s→4s→8s via `tenacity`, max 3 attempts → fallback tier2
- Ghost citation rate > 0.80 in session → emit `JURY_DEGRADED`, continue with `verdict="FAIL"`, notify via Run Companion (§6)
- JSON parse failure → see §8.1 ERROR_HANDLING pattern

CONSUMES: `[current_draft, citation_map, verified_sources, quality_preset]` from DocumentState
PRODUCES: `[jury_verdicts]` → DocumentState

**Evaluation Rubric — Dimensions F:**

| Dimension | Weight | Threshold | Description |
|-----------|--------|-----------|-------------|
| `citation_existence` | 0.40 | ≥ 0.90 | All cited sources exist and resolve |
| `claim_source_fidelity` | 0.35 | ≥ 0.75 | Claim matches source content (NLI entailment ≥ 0.70) |
| `quantitative_accuracy` | 0.15 | ≥ 0.80 | Numbers/dates match source values |
| `source_reliability` | 0.10 | ≥ 0.60 | Weighted avg reliability_score of cited sources |

### §8.2.1 Micro-Search — Agent-as-Judge (Falsification Logic)

JuryFactual MAY issue 1–2 external search queries per high-stakes claim to **falsify** (not confirm) it.

**Trigger conditions** (ANY of):
- Claim contains a specific statistic or percentage
- Claim asserts a non-trivial causal relationship
- Cited source `reliability_score < 0.75`
- `confidence` on initial check would be `"low"`

**Falsification protocol:**
```python
class MicroSearchSpec(BaseModel):
    claim_text:     str           # verbatim claim from draft
    queries:        list[str]     # max 2 queries, phrased to FIND contradictions
    search_tool:    Literal["tavily", "brave"]
    max_results:    int = 3
```

**Throttling by `quality_preset`:**

| Preset | Activation | Max claims | Max queries/claim |
|--------|-----------|------------|-------------------|
| Economy | Disabled | 0 | 0 |
| Balanced | `confidence == "low"` only | 2 | 1 |
| Premium | All trigger conditions | 3 | 2 |

**Cost target:** micro-search cost ≤ 8% of total run cost. Budget Controller (§19) enforces this via per-section cap.

**Query construction rule:** queries MUST be phrased adversarially, e.g.:
- Claim: "X increased by 40% in 2023"
- Query: "evidence against X growth 2023" OR "X declined 2023"

**Result classification:**
```python
MicroSearchOutcome = Literal["confirms", "contradicts", "inconclusive"]
```
- `contradicts` → VETO with `veto_category = "factual_error"`, include contradicting source in `external_sources_consulted`
- `confirms` / `inconclusive` → no verdict change, log in `external_sources_consulted`

---

## §8.3 Mini-Jury Style (S)

**AGENT: JuryStyle [§8.3]**
RESPONSIBILITY: Evaluate style compliance against active style profile and Style Exemplar

| Field | Value |
|-------|-------|
| MODEL | `meta/llama-3.3-70b-instruct` (tier1) / `mistral/mistral-large-2411` (tier2) / `openai/gpt-4.5` (tier3) |
| TEMP | 0.2 |
| MAX_TOKENS | 1024 |

INPUT:
```python
draft:           str
style_profile:   dict       # active frozen ruleset (§3B.3)
style_exemplar:  str        # approved sample from Style Calibration Gate (§3B.2)
forbidden_l1:    list[str]  # regex patterns — L1 enforcement
required_l2:     list[str]  # required elements — L2 enforcement
guide_l3:        list[str]  # soft guidance — L3 lowers CSS_style only
section_idx:     int
```

OUTPUT: `VerdictJSON` (see §8.6)

CONSTRAINTS:
- MUST detect L1 violations with `veto_category` = None (L1 → Style Fixer path, not VETO)
- NEVER issue VETO (Style jury has no veto authority)
- MUST compare draft register against `style_exemplar` concretely (not abstractly)
- ALWAYS list specific forbidden pattern text in `failed_claims` if detected

ERROR_HANDLING: see §8.1 ERROR_HANDLING pattern (identical)

CONSUMES: `[current_draft, style_profile, style_exemplar]` from DocumentState
PRODUCES: `[jury_verdicts]` → DocumentState

**Evaluation Rubric — Dimensions S:**

| Dimension | Weight | Threshold | Description |
|-----------|--------|-----------|-------------|
| `forbidden_pattern_absence` | 0.40 | 1.0 = zero violations | L1+L2 pattern compliance |
| `register_match` | 0.30 | ≥ 0.75 | Tone/formality matches `style_exemplar` |
| `readability` | 0.20 | ≥ 0.65 | Sentence variety, no repetitive structures |
| `exemplar_fidelity` | 0.10 | ≥ 0.60 | Stylistic proximity to approved exemplar |

> **NOTE — Style Calibration Gate (§3B.4):** During the pre-Phase A Style Calibration Gate, a lightweight `StyleCalibrationJury` is used instead of the production Mini-Jury S. The `StyleCalibrationJury` operates only on `(sample_text, style_profile, style_exemplar)` and does NOT require `citation_map`, `verified_sources`, or `section_idx` from DocumentState, since no current draft or citation context exists at that stage. It computes `CSS_style = pass_S / n_S` identically to production, but its input contract is restricted to the three fields above. See §3B for the full calibration gate specification.

---

## §8.4 Judge Calibration and Normalization

**Calibration dataset:** 20 documents with human-assigned CSS ground truth, stored in `tests/benchmark/golden_set/calibration/`.

**Normalization:** z-score correction applied per judge per session:
```python
calibrated_score = (raw_score - judge_mean_historical) / judge_std_historical
```
Applied when judge has ≥ 10 historical verdicts in `jury_rounds` table (§21.1).

**Confidence scoring:** all judges MUST emit `confidence: Confidence`. Mapping:
- `"high"`: external verification performed or claim has ≥ 2 supporting sources
- `"medium"`: single source, no external check
- `"low"`: claim unverifiable in available sources

**Disagreement analysis:** stored in `jury_rounds` table. Rogue Judge detection (§10.3) reads this table.

---

## §8.5 Cascading Economic Tiers

Each mini-jury slot has a **primary model** assigned by §28.2 (the model called first). The tiers defined below are **per-slot fallback chains**: when the primary model for a given slot fails (timeout, circuit breaker open, or all retries exhausted), the slot falls back through its chain in order.

> **Relationship to §28.2:** §28.2 `REASONING_JUDGE_SLOTS` defines which model is the primary for each of the three parallel judge slots (judge_r1, judge_r2, judge_r3). The per-slot fallback chains below define what is called next if that primary fails. These two concepts are complementary and non-conflicting: §28.2 governs slot assignment; §8.5 governs intra-slot fallback sequencing.

```python
# Per-slot fallback chains for Reasoning jury (R).
# The primary model for each slot is defined in §28.2 REASONING_JUDGE_SLOTS:
#   judge_r1 primary: deepseek/deepseek-r1
#   judge_r2 primary: openai/o3-mini
#   judge_r3 primary: qwen/qwq-32b
# These chains are invoked only when the primary for that slot fails.
REASONING_SLOT_FALLBACKS: dict[str, list[str]] = {
    "judge_r1": ["openai/o3-mini", "qwen/qwq-32b"],    # primary: deepseek/deepseek-r1
    "judge_r2": ["deepseek/deepseek-r1", "qwen/qwq-32b"],  # primary: openai/o3-mini
    "judge_r3": ["deepseek/deepseek-r1", "openai/o3-mini"],  # primary: qwen/qwq-32b
}

# Full tier table for Factual (F) and Style (S) juries.
# F and S juries use identical models across all three slots (no decorrelation requirement),
# so their fallback chains are uniform and expressed as a single tier sequence.
JURY_TIERS: dict[JurySlot, dict[str, str]] = {
    "F": {
        "tier1": "perplexity/sonar",
        "tier2": "google/gemini-2.5-flash",
        "tier3": "perplexity/sonar-pro",
    },
    "S": {
        "tier1": "meta/llama-3.3-70b-instruct",
        "tier2": "mistral/mistral-large-2411",
        "tier3": "openai/gpt-4.5",
    },
}
```

> **Cascading with jury_size < 3 (Balanced/Economy regimes):** When `jury_size < 3` (as set by the Budget Controller in §19.2), cascading is **disabled**. Tier1 results are final regardless of agreement level, and the CSS is computed on the available judges only (n_R, n_F, or n_S reflects the actual number of non-degraded judges that ran). This rule also applies when `JURY_DEGRADED` reduces the effective jury below 3. See §19.5 for how `jury_size` is treated as an adaptive severity parameter.

```python
CASCADING_UNANIMITY_THRESHOLD: int = 3   # all 3 tier1 judges agree → stop
CASCADING_MIN_JURY_SIZE: int = 3         # cascading disabled when jury_size < 3
EXPECTED_COST_REDUCTION_PCT: float = 0.65  # target vs all-premium baseline
```

Three mini-juries execute in parallel: `await asyncio.gather(run_R(), run_F(), run_S())`. Cascading is internal to each jury, not across juries.

---

## §8.6 VerdictJSON — Full Typed Schema

```python
class DimensionScores(BaseModel):
    # Jury R dimensions
    logical_flow:               Optional[float] = None  # [0.0, 1.0]
    causal_validity:            Optional[float] = None
    inter_section_coherence:    Optional[float] = None
    argument_completeness:      Optional[float] = None
    # Jury F dimensions
    citation_existence:         Optional[float] = None
    claim_source_fidelity:      Optional[float] = None
    quantitative_accuracy:      Optional[float] = None
    source_reliability:         Optional[float] = None
    # Jury S dimensions
    forbidden_pattern_absence:  Optional[float] = None
    register_match:             Optional[float] = None
    readability:                Optional[float] = None
    exemplar_fidelity:          Optional[float] = None


class ExternalSource(BaseModel):
    url:              str
    query_used:       str
    outcome:          Literal["confirms", "contradicts", "inconclusive"]
    snippet:          str   # ≤ 200 chars


class VerdictJSON(BaseModel):
    # Identity
    jury_slot:        JurySlot
    judge_model:      str               # actual model used (may differ from primary if fell back)
    tier_used:        JuryTier
    section_idx:      int
    iteration:        int
    timestamp_iso:    str               # UTC ISO 8601

    # Decision
    verdict:          Outcome
    confidence:       Confidence
    veto_category:    Optional[VetoCategory] = None   # required when verdict == "VETO"

    # Scores
    dimension_scores: DimensionScores
    jury_score:       float             # weighted avg of applicable dimensions, [0.0, 1.0]

    # Evidence
    failed_claims:    list[str]         # verbatim text spans; empty list if PASS
    missing_evidence: list[str]         # F jury only; claims needing sources
    comments:         str              # ≤ 500 chars; mandatory if verdict != "PASS"

    # Micro-search (F jury only)
    external_sources_consulted: list[ExternalSource] = []

    # CSS contribution
    css_contribution: float            # this verdict's weighted contribution to CSS_content or CSS_style
```

**Invariants (enforced by Pydantic validators):**
- `veto_category` MUST be set iff `verdict == "VETO"`
- `jury_slot == "S"` MUST NOT set `veto_category` (Style jury has no veto)
- `dimension_scores` fields for wrong jury slot MUST be `None`
- `jury_score` MUST equal weighted avg of non-None `dimension_scores` values
- `external_sources_consulted` MUST be empty unless `jury_slot == "F"`

---

## §8.7 Two-Gate Approval Sequence

Aggregator (§9) enforces this sequence; juries run in parallel but gates are sequential:

```
Phase 1 — Content Gate (R + F):
  CSS_content = (pass_R/n_R × 0.44) + (pass_F/n_F × 0.56)
  Threshold:  CSS_content ≥ css_content_threshold (from §9.3 THRESHOLD_TABLE)
  On FAIL:    → Reflector (§12) or Researcher if missing_evidence

Phase 2 — Style Pass (S):
  CSS_style = pass_S / n_S
  Threshold:  CSS_style ≥ css_style_threshold (from §9.3 THRESHOLD_TABLE)
  On FAIL:    → Style Fixer (§5.10), NOT Reflector, NOT Writer
```

Style Pass runs only after Content Gate PASS. `n_R`, `n_F`, `n_S` = number of non-degraded judges in each jury (1–3). CSS weights: see §9.2.

> **NOTE — Coefficient derivation:** The coefficients 0.44 and 0.56 in the Content Gate formula are **not independent constants**. They are derived at runtime from `jury_weights` (§9.2) by normalizing the reasoning and factual weights over their sum, excluding the style weight. They MUST NOT be hardcoded as fixed literals in implementation. Compute them as:
> ```python
> w_R_content = jury_weights["reasoning"] / (jury_weights["reasoning"] + jury_weights["factual"])
> w_F_content = jury_weights["factual"]   / (jury_weights["reasoning"] + jury_weights["factual"])
> # With default weights 0.35 / 0.45: w_R_content ≈ 0.44, w_F_content ≈ 0.56
> ```
> Any change to `jury_weights` in §9.2 MUST trigger recomputation of these coefficients. See §9.1 for the full derivation.

---

## §8.8 Jury Execution — State Fields

```python
# Fields consumed from DocumentState
CONSUMES: list[str] = [
    "current_draft",
    "current_sources",
    "citation_map",
    "style_profile",
    "style_exemplar",
    "approved_sections",        # compressed; see §14
    "outline",
    "quality_preset",
    "budget",                   # for micro-search throttling
    "jury_degraded",            # dict[JurySlot, bool]
]

# Fields produced to DocumentState
PRODUCES: list[str] = [
    "jury_verdicts",            # list[VerdictJSON] — all verdicts this iteration
    "all_verdicts_history",     # accumulated across iterations
    "css_history",              # float appended after Aggregator computes CSS
]
```

<!-- SPEC_COMPLETE -->