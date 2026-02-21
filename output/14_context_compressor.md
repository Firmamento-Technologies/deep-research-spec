# §14 Context Compressor

## §14.0 Overview

Dedicated agent for progressive context window management across multi-section documents. Invoked exactly once per section approval, after the coherence guard confirms no hard conflicts, before the section is checkpointed and before the next section's Researcher call.

---

## §14.1 Compression Strategy by Position

Position is measured as **distance from the current section**. Distance is defined as `(current_section_idx - approved_section_idx)`, so the immediately preceding approved section has distance=1 (not distance=0). The current section being written has no distance value; compression applies only to already-approved sections.

```python
from typing import Literal

PositionTier = Literal["verbatim", "structured_summary", "thematic_extract"]

POSITION_TO_TIER: dict[tuple[int, int], PositionTier] = {
    (1, 2): "verbatim",           # last 2 approved sections (distance=1 and distance=2)
    (3, 5): "structured_summary", # sections 3–5 positions back (distance=3, 4, or 5)
}
# distance >= 6 → "thematic_extract"

def resolve_tier(distance: int) -> PositionTier:
    """
    distance = current_section_idx - approved_section_idx
    The immediately preceding section has distance=1.
    """
    if distance <= 2:
        return "verbatim"
    elif distance <= 5:
        return "structured_summary"
    return "thematic_extract"
```

### Tier Definitions

| Tier | Content Preserved | Max Tokens |
|---|---|---|
| `verbatim` | Full approved content, unchanged | no limit |
| `structured_summary` | Key claims + citations + section thesis, prose condensed | 120 words |
| `thematic_extract` | Load-bearing claims only (see §14.2) + section title + 1-sentence scope | 40 words |

---

## §14.2 Load-Bearing Claim Identification Algorithm

A claim is **load-bearing** if any future section (as declared in the outline) presupposes it as a logical premise, factual anchor, or definitional dependency.

```python
class LoadBearingClaim(TypedDict):
    text: str                          # verbatim sentence from approved section
    source_section_idx: int
    presupposed_by: list[int]          # future section indices that depend on this
    claim_type: Literal["factual", "definitional", "causal", "quantitative"]
    citation_ids: list[str]            # must be preserved with the claim

class CompressionInput(TypedDict):
    section_idx: int                   # section being compressed
    section_content: str               # full approved text
    outline: list[dict]                # full outline, all sections
    future_section_scopes: list[str]   # scope strings for sections idx+1..N
```

**Algorithm** (executed by qwen3-7b, structured output):

1. For each sentence in `section_content`, test: does any `future_section_scopes[i]` semantically require this sentence to be true or defined?
2. If yes → mark as load-bearing, record `presupposed_by=[i]`.
3. Load-bearing claims are **always preserved verbatim** regardless of tier.
4. Non-load-bearing content is compressed per tier rule (§14.1).

Load-bearing claims are extracted **before** tier compression and injected into the compressed output as a separate `## Load-Bearing Claims` subsection.

---

## §14.3 Agent Specification

```
AGENT: ContextCompressor [§14]
RESPONSIBILITY: compress approved sections into tiered context representations to fit Writer context budget
MODEL: qwen/qwen3-7b / TEMP: 0.1 / MAX_TOKENS: 512
INPUT:
  section_idx: int                        # index of just-approved section
  approved_sections: list[ApprovedSection]  # all approved so far (see §21.1)
  outline: list[dict]                     # full outline
  target_budget_tokens: int              # max tokens for compressed context block
OUTPUT: CompressedContext
CONSTRAINTS:
  MUST preserve all load-bearing claims verbatim regardless of tier (§14.2)
  MUST NOT alter any citation_id, author, year, or quantitative value in preserved claims
  MUST produce output parseable as CompressedContext within MAX_TOKENS
  NEVER invoke on section_idx == 0 (first section has no prior context to compress)
  ALWAYS run after coherence_guard confirms no HARD conflicts, before section_checkpoint
  MUST complete in under 15 seconds wall-clock time; timeout → fallback (see ERROR_HANDLING)
  distance MUST be computed as (current_section_idx - approved_section_idx); immediately preceding section has distance=1
ERROR_HANDLING:
  model_timeout (>15s) -> use previous compressed_context unchanged -> log WARNING with section_idx
  output_parse_failure -> retry once with simplified prompt (extract only load-bearing claims) -> if retry fails, return raw text truncated to target_budget_tokens
  load_bearing_detection_failure -> treat all claims in section as load-bearing -> log WARNING
CONSUMES: [approved_sections, outline, current_section_idx] from DocumentState
PRODUCES: [compressed_context] -> DocumentState
```

### Output Schema

```python
class SectionCompressed(TypedDict):
    section_idx: int
    title: str
    tier: PositionTier
    distance: int                      # = current_section_idx - section_idx; distance=1 means immediately preceding
    compressed_text: str               # tier-appropriate representation
    load_bearing_claims: list[LoadBearingClaim]
    original_word_count: int
    compressed_word_count: int

class CompressedContext(TypedDict):
    sections: list[SectionCompressed]  # all approved sections, ordered oldest→newest
    total_tokens_estimated: int
    budget_tokens: int
    budget_utilization_ratio: float    # total_tokens_estimated / budget_tokens; MUST be <= 1.0
```

### Injection Point

`compressed_context` is injected into the Writer prompt (§5.7) as the `context` block:

```
## Previously Approved Sections

{for section in compressed_context.sections}
### §{section.section_idx}: {section.title} [{section.tier}]
{section.compressed_text}

{if section.load_bearing_claims}
#### Load-Bearing Claims (preserve coherence):
{for claim in section.load_bearing_claims}
- [{claim.claim_type}] {claim.text}
{end}
{end}
{end}
```

The Researcher, Fusor, Reflector, and Coherence Guard also receive `compressed_context` read-only for cross-section coherence checks (§15.1).

---

## §14.4 Invocation Timing

```
aggregator → [coherence_guard] → [context_compressor] → [section_checkpoint] → route_next_section
```

- **Trigger**: aggregator emits approval signal (CSS above threshold), routing first to `coherence_guard`.
- **Ordering rationale**:
  1. `coherence_guard` runs **FIRST** on the approved draft before any compression occurs. If it finds a HARD conflict, the section is blocked and `compressed_context` is **NOT** updated — avoiding stale context from a rejected section.
  2. `context_compressor` runs **AFTER** `coherence_guard` confirms no HARD conflicts, preparing context for the NEXT section.
  3. `section_checkpoint` finalises the section in PostgreSQL after both guards pass.
- **Not invoked**: before any section starts, during iteration loops, or at outline approval.
- **State update**: `DocumentState.compressed_context` is overwritten (not appended) on each invocation — always reflects the full compressed history.

LangGraph edge definition (see §4.5):

```python
# Correct ordering: aggregator → coherence_guard → context_compressor → section_checkpoint
#
# Rationale:
#   1. CoherenceGuard runs FIRST on the draft before any compression occurs.
#      If it finds a HARD conflict, the section is blocked and compressed_context
#      is NOT updated — avoiding stale context from a rejected section.
#   2. ContextCompressor runs AFTER coherence_guard confirms the section is
#      conflict-free, preparing context for the NEXT section.
#   3. SectionCheckpoint finalises the section in PostgreSQL after both guards pass.

g.add_conditional_edges("coherence_guard", route_after_coherence, {
    "no_conflict":   "context_compressor",
    "soft_conflict": "context_compressor",
    "hard_conflict": "await_human"
})
g.add_edge("context_compressor", "section_checkpoint")
g.add_conditional_edges("section_checkpoint", route_next_section, {
    "next_section": "researcher",
    "all_done":     "post_qa"
})
```

---

## §14.5 Model Rationale

`qwen/qwen3-7b` is selected for ContextCompressor because:

| Criterion | Justification |
|---|---|
| Task type | Extractive + light abstractive — no complex reasoning required |
| Cost | Lowest-tier model; runs on every section approval, must minimize budget impact |
| Speed | Sub-15s target; larger models (o3, Claude Opus) add 30–60s latency per invocation |
| Context | Input fits within 8k tokens for documents up to 50k words when tiered correctly |
| Quality bar | Load-bearing claim detection requires semantic understanding, not creativity |

Fallback chain: `qwen/qwen3-7b` → `meta/llama-3.3-70b-instruct` → raw truncation to `target_budget_tokens`.

---

## §14.6 Token Budget Integration

`target_budget_tokens` is derived from `DocumentState.budget` (§19.3):

```python
CONTEXT_BUDGET_FRACTION = 0.15  # 15% of Writer context window reserved for prior sections

def compute_context_budget(writer_model_context_window: int) -> int:
    mecw = int(writer_model_context_window * 0.45)  # safety_factor for Writer, see scalability §
    return int(mecw * CONTEXT_BUDGET_FRACTION)
```

If `budget_utilization_ratio > 1.0` after compression, the Compressor re-runs with `target_budget_tokens` reduced by 20% and forces all non-verbatim tiers one level stricter (structured_summary → thematic_extract for distance 3–5, thematic_extract reduced to title-only for distance ≥6).

<!-- SPEC_COMPLETE -->