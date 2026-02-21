# 30_output.md — Output System Specification

## §30 Output System

### §30.1 Document Final Properties

```python
class DocumentFinalProperties(TypedDict):
    word_count_actual: int          # MUST be within target_words ± 10%
    word_count_target: int
    word_count_tolerance: float     # 0.10 (fixed)
    l1_violations: int              # MUST == 0 at delivery
    l2_violations: int              # MUST == 0 at delivery
    citations_verified: int
    citations_total: int
    citation_accuracy: float        # citations_verified / citations_total; target >= 0.98
    coherence_guard_passed: bool    # MUST == True
    contradiction_count: int        # MUST == 0 for delivery
    format_validated: bool          # MUST == True
    css_avg: float                  # mean of all section css_final values
    css_min: float
    hallucination_rate_per_model: dict[str, float]  # model_id -> ghost_rate
```

**Delivery gate** (all conditions required):
```python
DELIVERY_GATE: dict[str, Any] = {
    "word_count_within_tolerance": True,   # |actual - target| / target <= 0.10
    "l1_violations": 0,
    "coherence_guard_passed": True,
    "format_validated": True,
    "contradiction_count": 0,
}
```

---

### §30.2 Output Formats

```python
OutputFormat = Literal["docx", "pdf", "markdown", "latex", "html", "json"]
```

| Format | Library | File Extension | Primary Use Case |
|--------|---------|----------------|------------------|
| `docx` | `python-docx` | `.docx` | Editable delivery |
| `pdf` | `weasyprint` or `pandoc` | `.pdf` | Archival/distribution |
| `markdown` | stdlib + `mistune` | `.md` | Git/Obsidian/Notion |
| `latex` | `pylatexenc` + BibTeX | `.tex` + `.bib` | Academic submission |
| `html` | `jinja2` + CSS responsive | `.html` | Web publishing |
| `json` | stdlib | `.json` | Programmatic consumption / API |

#### JSON Structured Output Schema

```python
class CitationJSON(TypedDict):
    id: str
    style_string: str               # formatted per citation_style config
    authors: list[str]
    year: int
    title: str
    source_type: Literal["academic", "institutional", "web", "social"]
    doi: str | None
    url: str | None
    reliability_score: float
    nli_entailment: float | None    # DeBERTa score if run
    http_verified: bool
    ghost_flag: bool

class SectionJSON(TypedDict):
    index: int
    title: str
    content: str
    word_count: int
    css_final: float
    css_breakdown: dict[str, float]  # {"reasoning": 0.89, "factual": 0.91, "style": 0.84}
    iterations_used: int
    sources: list[CitationJSON]
    warnings: list[str]             # soft coherence conflicts, JURY_DEGRADED flags

class DocumentJSON(TypedDict):
    doc_id: str
    title: str
    topic: str
    language: str
    style_profile: str
    word_count: int
    created_at: str                 # ISO 8601
    sections: list[SectionJSON]
    citations: list[CitationJSON]   # deduplicated full bibliography
    metadata: dict[str, Any]        # config snapshot at run time
    metrics: "RunReport"            # see §30.4
```

---

### §30.3 Publisher Agent

```
AGENT: Publisher [§30.3]
RESPONSIBILITY: Assemble approved sections from Store into all configured output formats
MODEL: deterministic (no LLM) / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  approved_sections: list[ApprovedSection]  # from Store, immutable
  citations: list[CitationJSON]
  config: dict[str, Any]
  output_formats: list[OutputFormat]
  template_path: str                        # .docx template file path
  run_report: RunReport                     # see §30.4
OUTPUT: dict[OutputFormat, str]             # format -> S3/MinIO object key
CONSTRAINTS:
  MUST verify DELIVERY_GATE before writing any output file (see §30.1)
  MUST generate auto-summary (max 200 words) as first element if style_profile != "software_spec"
  MUST generate bibliography section as final element (sorted by first author last name)
  MUST apply section_cache: if hash(section.content) matches previous run -> reuse artifact
  NEVER modify section content during assembly
  ALWAYS store output artifacts in S3/MinIO; return signed URL (TTL 900s) via API
ERROR_HANDLING:
  template_missing -> use fallback default template from package -> log warning
  weasyprint_failure -> fallback pandoc -> fallback markdown-only -> alert
  word_count_outside_tolerance -> raise DeliveryGateError with actual/target values
CONSUMES: [approved_sections, output_formats, run_report] from DocumentState
PRODUCES: [output_paths] -> DocumentState
```

**DOCX Template Styles** (applied via `python-docx`):

```python
DOCX_STYLE_MAP: dict[str, str] = {
    "h1": "Heading 1",
    "h2": "Heading 2",
    "h3": "Heading 3",
    "body": "Body Text",
    "citation_block": "Quote",
    "code": "Code",
    "auto_summary": "Abstract",
    "bibliography_entry": "Bibliography",
}
```

**Auto-Summary** generation uses `google/gemini-2.5-flash` (200 words max, extractive + compressive, injected before section assembly).

**Section Cache** key:
```python
section_cache_key = f"section_cache:{sha256(section.content + section.title)[:16]}"
# Redis TTL: 7 days; cache miss -> regenerate artifact
```

---

### §30.4 Run Report Schema

```python
class AgentCostEntry(TypedDict):
    agent: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    call_count: int

class JuryVerdictRecord(TypedDict):
    section_index: int
    iteration: int
    judge_slot: Literal["R1","R2","R3","F1","F2","F3","S1","S2","S3"]
    model: str
    verdict: Literal["PASS","FAIL","VETO"]
    veto_category: str | None
    confidence: Literal["low","medium","high"]
    css_contribution: float
    motivation: str
    external_sources_consulted: list[str]  # Judge F micro-search URLs

class EscalationRecord(TypedDict):
    section_index: int
    iteration: int
    type: Literal["oscillation_css","oscillation_semantic","whack_a_mole","coherence_hard","budget_stop","full_rewrite"]
    trigger_value: float
    resolution: Literal["human_override","section_skipped","outline_modified","approved_warning"]

class CompanionMessage(TypedDict):
    timestamp: str          # ISO 8601
    role: Literal["user","companion"]
    content: str
    section_index: int | None
    iteration: int | None
    modification_applied: bool
    modification_detail: str | None

class RunReport(TypedDict):
    run_id: str
    doc_id: str
    topic: str
    profile: str
    quality_preset: Literal["economy","balanced","premium"]
    started_at: str
    completed_at: str
    elapsed_minutes: float

    # Cost breakdown
    total_cost_usd: float
    cost_by_agent: list[AgentCostEntry]
    cost_by_section: list[dict]         # [{section_index, cost_usd, iterations}]
    budget_max_usd: float
    budget_utilization_ratio: float     # total_cost / budget_max

    # Quality metrics
    css_history: list[dict]             # [{section_index, iteration, css_content, css_style}]
    css_avg: float
    css_min: float
    avg_iterations_per_section: float
    first_attempt_approval_rate: float  # sections approved on iter==1 / total sections

    # Verdicts
    jury_verdicts: list[JuryVerdictRecord]
    panel_discussion_count: int
    veto_count: int
    mow_enabled_sections: list[int]
    fusor_integration_rate: float       # % drafts with elements from >=2 proposers

    # Escalations
    escalations: list[EscalationRecord]
    oscillation_count: int
    human_interventions: int

    # Citations / Hallucinations
    citations_total: int
    citations_verified: int
    ghost_citations_detected: int
    hallucination_rate_per_model: dict[str, float]  # model_id -> ghost_count / total_calls

    # Source diversity (see §17.8)
    diversity_score_per_section: list[dict]   # [{section_index, score, warnings}]

    # Run Companion conversation
    companion_conversation: list[CompanionMessage]

    # Document properties
    word_count_final: int
    word_count_target: int
    delivery_gate_passed: bool
    l1_violations_final: int
    coherence_conflicts_resolved: int
```

Run Report written to `_run_report.json` in output directory and stored in PostgreSQL `runs` table (`run_metrics` JSONB column, see §21.1).

---

### §30.5 Multi-File Output for `software_spec`

When `profile == "software_spec"`, Publisher produces a directory (zipped or git-initialized) instead of a single document. See §31.2 for pipeline context.

```python
SOFTWARE_SPEC_OUTPUT_STRUCTURE: dict[str, str] = {
    "AGENTS.md":        "Coding agent onboarding: stack, dirs, commands, conventions, glossary",
    "architecture.md":  "Components, responsibilities, interfaces, data flows + Mermaid diagrams",
    "data_schema.sql":  "Full DDL: tables, columns, types, constraints, indexes",
    "api_spec.yaml":    "OpenAPI 3.1 spec with all endpoints, schemas, auth",
    "conventions.md":   "Naming, formatting, commit, error handling conventions",
    "workflows.md":     "Key operational workflows as step sequences",
    "features/":        "One file per feature in Gherkin (Given/When/Then)",
    "_run_report.json": "see §30.4",
    "_sources.bib":     "BibTeX bibliography of all verified sources",
}
```

```python
class SoftwareSpecSection(TypedDict):
    file: str                           # relative path in output dir
    scope: str                          # single sentence
    format: Literal["markdown","markdown_with_mermaid","sql_ddl","openapi_yaml","gherkin"]
    dependencies: list[str]             # other files that must be written first
    estimated_words: int
```

Publisher assembles files **in dependency order**; `features/` files generated last (depend on `api_spec.yaml` + `data_schema.sql`).

Delivery: `{project_name}-spec.zip` uploaded to S3; `GET /v1/documents/{id}/export?format=zip` returns pre-signed URL (TTL 900s). See §24.1.

---

### §30.6 Feedback Collector

```
AGENT: FeedbackCollector [§30.6]
RESPONSIBILITY: Collect post-delivery user ratings and route signals to training loop
MODEL: deterministic / TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  doc_id: str
  feedback: FeedbackPayload
OUTPUT: FeedbackRecord
CONSTRAINTS:
  MUST accept feedback within 30 days of document delivery
  MUST store feedback in PostgreSQL `feedback` table with FK to `documents`
  MUST NOT modify any approved section or run state
  ALWAYS write source_blacklist entries to user's config immediately
  ALWAYS trigger prompt_drift_check job if section_ratings contain avg < 3.0 on >=3 sections
ERROR_HANDLING:
  invalid_rating_range -> reject with 422, message "rating must be 1-5"
  doc_not_found -> 404
  feedback_window_expired -> 410 Gone
CONSUMES: [doc_id, run_report] from DocumentState (read-only)
PRODUCES: [feedback_record] -> PostgreSQL feedback table (not DocumentState)
```

```python
class SectionRating(TypedDict):
    section_index: int
    rating: int                     # 1-5 inclusive
    error_highlights: list[str]     # quoted text spans marked as errors by user
    error_categories: list[Literal["factual","style","citation","coherence","other"]]
    free_text: str | None

class FeedbackPayload(TypedDict):
    doc_id: str
    overall_rating: int             # 1-5 inclusive
    section_ratings: list[SectionRating]
    style_profile_correct: bool
    source_blacklist: list[str]     # URLs/domains to blacklist for this user
    source_whitelist: list[str]
    free_text: str | None

class FeedbackRecord(TypedDict):
    feedback_id: str
    doc_id: str
    user_id: str
    submitted_at: str               # ISO 8601
    payload: FeedbackPayload
    training_signals_emitted: list[str]  # which downstream jobs were triggered
```

**Training Loop** — triggered signals:

| Condition | Signal | Action |
|-----------|--------|--------|
| `overall_rating <= 2` | `PROMPT_REVIEW` | Opens GitHub issue tagged `prompt-degradation` |
| `section_rating.rating <= 2` on >=3 sections | `PROMPT_DRIFT_CHECK` | Runs Golden Set subset (see §25.5) |
| `error_category == "citation"` count >= 2 | `HALLUCINATION_AUDIT` | Flags model in `hallucination_rate_per_model` tracker (see §18.5) |
| `style_profile_correct == False` | `PRESET_REVIEW` | Logs to `style_preset_feedback` table for manual review |
| `source_blacklist` non-empty | `BLACKLIST_UPDATE` | Writes to user config `sources.reliability_overrides` with score `0.0` |

All signals are fire-and-forget async tasks (Celery); FeedbackCollector returns `202 Accepted` immediately.

**Feedback API endpoint**: `POST /v1/documents/{doc_id}/feedback` (see §24.1 for auth).

<!-- SPEC_COMPLETE -->