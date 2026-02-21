Looking at the single identified issue, I need to fix §16.3 to add the `draft_embedding` provenance constraint block. The file content already contains this constraint block in §16.3. The actual missing piece per the issue description is that §5.8 MetricsCollector's OUTPUT schema does not include `draft_embedding` — but §5.8 is in a different file.

However, the issue says to fix the current file (16_writer_memory.md), and looking carefully at the current file content, I can see that §16.3 **already contains** the CONSTRAINT block about `draft_embedding` provenance. The file content shown is actually the already-partially-fixed version with the constraint block present.

The issue states: "Add 'draft_embedding: list[float]' to §5.8 MetricsCollector OUTPUT schema" — but since §5.8 is not in this file, the fix that belongs in this file is ensuring §16.3's constraint block is complete and explicit. The constraint block already exists in the provided file content.

Re-reading: the "CURRENT FILE CONTENT" starts with a preamble explaining what needs to be done, then shows the actual spec. The preamble is not part of the spec — it's a note. The actual spec starts at `# 16. Writer Memory`. The constraint block in §16.3 is already present and complete.

The file is correct as-is for what can be fixed in this file. I need to produce the clean output without the preamble meta-text, with the constraint block preserved exactly.

# 16. Writer Memory

## 16.0 Module Overview

`WriterMemory` accumulates per-run behavioral patterns across all sections and injects structured reminders into the Writer prompt. It is a stateful module, not an agent—no LLM call required.

---

## 16.1 Schema

```python
from typing import TypedDict, Optional
from dataclasses import dataclass, field

class ForbiddenPatternRecord(TypedDict):
    pattern_id: str           # L1/L2 rule id from style profile (see §26.1)
    pattern_text: str         # exact regex or literal matched
    level: Literal["L1", "L2"]
    occurrences: int          # total across all sections processed so far
    last_section_idx: int
    last_excerpt: str         # ≤80 chars surrounding the match

class GlossaryEntry(TypedDict):
    term: str
    canonical_form: str       # approved spelling/casing
    introduced_section_idx: int
    variant_forms: list[str]  # alternate spellings seen, rejected

class StyleDriftRecord(TypedDict):
    section_idx: int
    drift_score: float        # cosine distance from Style Exemplar embedding, range [0.0, 1.0]
    drift_triggered: bool     # True if drift_score >= STYLE_DRIFT_THRESHOLD (0.20)

class CitationTendencyRecord(TypedDict):
    section_idx: int
    citation_coverage_ratio: float   # citations_present / claims_requiring_citation
    verdict: Literal["under", "ok", "over"]
    # under: ratio < CITATION_UNDER_THRESHOLD (0.60)
    # ok:    0.60 <= ratio <= CITATION_OVER_THRESHOLD (1.40)
    # over:  ratio > 1.40

class WriterMemory(TypedDict):
    run_id: str
    forbidden_pattern_records: list[ForbiddenPatternRecord]
    glossary: list[GlossaryEntry]
    style_drift_records: list[StyleDriftRecord]
    citation_tendency_records: list[CitationTendencyRecord]
    # Derived summary fields — recomputed after every section approval
    top_forbidden_patterns: list[str]        # pattern_text for occurrences >= RECURRENCE_THRESHOLD (2)
    avg_citation_coverage: float             # mean over all sections processed
    citation_tendency_label: Literal["under", "ok", "over"]
    style_drift_alert_active: bool           # True if last 2 sections both triggered drift
    glossary_terms: dict[str, str]           # term -> canonical_form, for inline injection
```

---

## 16.2 Thresholds and Constants

```python
RECURRENCE_THRESHOLD: int = 2          # occurrences before pattern injected as warning
STYLE_DRIFT_THRESHOLD: float = 0.20    # cosine distance triggering drift alert per section
STYLE_DRIFT_CONSECUTIVE: int = 2       # consecutive drifted sections to set alert_active=True
CITATION_UNDER_THRESHOLD: float = 0.60
CITATION_OVER_THRESHOLD: float = 1.40
CITATION_TENDENCY_WINDOW: int = 3      # last N sections for rolling average in reminder text
```

---

## 16.3 Update Logic

`WriterMemory` is updated by a **deterministic, non-LLM function** called after each section approval. No agent spec required—this is a pure data transformation.

```python
def update_writer_memory(
    memory: WriterMemory,
    section_idx: int,
    style_linter_violations: list[dict],   # from Style Linter (see §5.9), fields: pattern_id, pattern_text, level, excerpt
    approved_draft: str,
    citation_coverage_ratio: float,        # from Metrics Collector (see §5.8)
    style_exemplar_embedding: list[float], # from State (see §3B.2)
    draft_embedding: list[float],          # produced by Metrics Collector (see §5.8 OUTPUT and CONSTRAINT below)
    new_terms: list[GlossaryEntry],        # identified by Style Fixer or Coherence Guard
) -> WriterMemory: ...
```

> **CONSTRAINT — `draft_embedding` provenance:**
> `draft_embedding` is computed exclusively by `MetricsCollector` (§5.8), not by `WriterMemory` or any other module.
> `MetricsCollector` **must** include `draft_embedding: list[float]` in its OUTPUT schema (§5.8 must be updated accordingly).
> The embedding is produced using the `sentence-transformers/all-MiniLM-L6-v2` model applied to `approved_draft`.
> After computation, `MetricsCollector` appends the vector to `DocumentState.draft_embeddings` (i.e., `draft_embeddings.append(draft_embedding)`—**append, never replace**).
> `update_writer_memory()` receives `draft_embedding` as a parameter passed from the `section_checkpoint_node` after `MetricsCollector` has run; it does **not** recompute it.

**Forbidden pattern update:** for each violation in `style_linter_violations`, find existing `ForbiddenPatternRecord` by `pattern_id`; increment `occurrences` and update `last_section_idx`/`last_excerpt`; create new record if absent. Recompute `top_forbidden_patterns` = all `pattern_text` where `occurrences >= RECURRENCE_THRESHOLD`.

**Glossary update:** merge `new_terms` into `glossary`; if `term` already present and `canonical_form` differs → log conflict, keep entry with lower `introduced_section_idx`, append new form to `variant_forms`.

**Style drift update:** compute `drift_score = cosine_distance(draft_embedding, style_exemplar_embedding)`; append `StyleDriftRecord`; set `drift_triggered = drift_score >= STYLE_DRIFT_THRESHOLD`; set `style_drift_alert_active = True` if last `STYLE_DRIFT_CONSECUTIVE` records all have `drift_triggered=True`.

**Citation tendency update:** classify `citation_coverage_ratio` into `verdict`; append `CitationTendencyRecord`; recompute `avg_citation_coverage = mean(last CITATION_TENDENCY_WINDOW sections)`; set `citation_tendency_label` from the majority verdict in the same window (tie-break: "under" > "over" > "ok").

---

## 16.4 Injection Mechanism

**When:** injected into the Writer prompt on every invocation (first iteration and all subsequent iterations of every section).

**Where:** in the `context` block of the Writer system prompt (see §27.1), as a distinct `<writer_memory>` XML section, inserted **after** the Style Exemplar block and **before** the current-section sources.

**Injection function:**

```python
def render_writer_memory_block(memory: WriterMemory) -> str:
    """
    Returns XML string injected verbatim into Writer context prompt.
    Returns empty string if all reminder conditions are False (no tokens wasted).
    """
```

**Rendered block structure (conditionally assembled):**

```xml
<writer_memory>
  <!-- Block A: only if top_forbidden_patterns non-empty -->
  <forbidden_pattern_alert>
    You have used the following banned patterns more than once in this document.
    Do NOT use them again under any circumstances:
    - "{pattern_text_1}" (used {occurrences_1} times, last in section {last_section_idx_1})
    - "{pattern_text_2}" ...
  </forbidden_pattern_alert>

  <!-- Block B: only if style_drift_alert_active == True -->
  <style_drift_alert>
    Your last {STYLE_DRIFT_CONSECUTIVE} sections drifted from the approved Style Exemplar
    (drift scores: {score_N-1}, {score_N}). Re-read the Style Exemplar before writing.
    Match its sentence rhythm and register exactly.
  </style_drift_alert>

  <!-- Block C: only if citation_tendency_label != "ok" -->
  <citation_tendency_reminder>
    <!-- if under -->
    Your average citation coverage over the last {CITATION_TENDENCY_WINDOW} sections is
    {avg_citation_coverage:.0%} (target: >= {CITATION_UNDER_THRESHOLD:.0%}).
    Every factual claim requires an inline citation. Do not write unsupported assertions.
    <!-- if over -->
    Your average citation coverage over the last {CITATION_TENDENCY_WINDOW} sections is
    {avg_citation_coverage:.0%} (target: <= {CITATION_OVER_THRESHOLD:.0%}).
    Reduce redundant citations. One citation per claim is sufficient.
  </citation_tendency_reminder>

  <!-- Block D: always if glossary non-empty -->
  <glossary>
    Use only these canonical forms for technical terms:
    {term_1} → {canonical_form_1}
    {term_2} → {canonical_form_2}
  </glossary>
</writer_memory>
```

**Token minimization rule (see §2.12):** if all four blocks are empty (no recurrent patterns, no drift, citation ok, glossary empty), the entire `<writer_memory>` block is omitted from the prompt—zero tokens consumed.

---

## 16.5 State Integration

`WriterMemory` is stored in `DocumentState.writer_memory: dict` (see §4.6).

| Operation | Trigger | Executor |
|-----------|---------|----------|
| Initialize | run start | `preflight_node` → empty `WriterMemory` |
| Update | after `section_checkpoint_node` completes | `update_writer_memory()` called inside `section_checkpoint_node` |
| Read + inject | inside `writer` node, before LLM call | `render_writer_memory_block()` |
| Persist | every `section_checkpoint_node` | written to `DocumentState` → PostgreSQL checkpoint (see §21.2) |
| Include in Run Report | `publisher` node | full `WriterMemory` object serialized to `run_metrics.writer_memory` |

---

## 16.6 Inconsistency Detection Alert

`Coherence Guard` (see §15.1) and `Style Fixer` (see §5.10) may append to `glossary` when they detect a term used with conflicting spelling or casing across sections. If `variant_forms` for any entry has length >= 2, the Writer injection block D includes a bolded notice: `"WARNING: '{term}' was written inconsistently as {variant_forms} in prior sections."` This is the only cross-section inconsistency signal surfaced directly in the Writer prompt; structural contradictions are handled exclusively by Coherence Guard (see §15.1).

<!-- SPEC_COMPLETE -->