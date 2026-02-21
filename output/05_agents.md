# 05_agents.md — Agent Specifications §5.1–5.22

## Shared Types

```python
from typing import TypedDict, Literal, Optional
from pydantic import BaseModel

VetoCategory = Literal["fabricated_source","factual_error","logical_contradiction","plagiarism"]
Severity = Literal["CRITICAL","HIGH","MEDIUM","LOW"]
Scope = Literal["SURGICAL","PARTIAL","FULL"]
AgentOutcome = Literal["ok","error","degraded"]
StyleProfile = Literal["scientific_report","business_report","technical_documentation",
                        "journalistic","narrative_essay","ai_instructions","blog","software_spec"]
QualityPreset = Literal["Economy","Balanced","Premium"]

class Source(TypedDict):
    url: str
    title: str
    source_type: Literal["academic","institutional","social","general","uploaded"]
    publisher: str
    published_at: str          # ISO date
    reliability_score: float   # 0.0–1.0
    doi: Optional[str]
    abstract: Optional[str]

class JudgeVerdict(TypedDict):
    judge_slot: str            # R1|R2|R3|F1|F2|F3|S1|S2|S3
    model: str
    pass_fail: bool
    veto_category: Optional[VetoCategory]
    confidence: Literal["low","medium","high"]
    motivation: str
    failed_claims: list[str]
    missing_evidence: list[str]
    external_sources_consulted: list[str]   # Judge F only

class ReflectorFeedback(TypedDict):
    id: str
    severity: Severity
    category: str
    affected_text: str         # exact quote
    context_before: str
    context_after: str
    action: str
    replacement_length_hint: Literal["SHORTER","SAME","LONGER"]
    priority: int              # 1=highest

class StyleViolation(TypedDict):
    rule_id: str
    level: Literal["L1","L2","L3"]
    position: int              # char offset
    matched_text: str
    message: str
    fix_hint: str
```

DocumentState: see §4.6.

---

## §5.1 Planner

```
AGENT: Planner [§5.1]
RESPONSIBILITY: Generate section outline from topic + config
MODEL: google/gemini-2.5-pro / TEMP: 0.3 / MAX_TOKENS: 4096
INPUT:
  topic: str
  target_words: int
  style_profile: StyleProfile
  quality_preset: QualityPreset
  custom_outline: Optional[list[dict]]   # user override, see §3.2
OUTPUT:
  outline: list[dict]   # [{index:int, title:str, scope:str, target_words:int, dependencies:list[int]}]
  document_type: Literal["survey","tutorial","review","report","spec","essay","blog"]
CONSTRAINTS:
  MUST distribute target_words ±5% across sections; no section <200 words
  MUST detect document_type and adapt section order accordingly
  MUST respect custom_outline if provided (merge, not replace)
  NEVER produce >20 sections regardless of target_words
  ALWAYS output valid JSON parseable by Pydantic; parse failure → FAIL
ERROR_HANDLING:
  parse_error → retry with simplified prompt (1×) → fallback: return custom_outline if present else raise
  model_unavailable → fallback google/gemini-2.5-flash → google/gemini-1.5-pro
CONSUMES: [topic, config, custom_outline] from DocumentState
PRODUCES: [outline, outline_approved=False] -> DocumentState
```

---

## §5.2 Researcher

```
AGENT: Researcher [§5.2]
RESPONSIBILITY: Retrieve and rank sources for a single section
MODEL: perplexity/sonar-pro / TEMP: 0.1 / MAX_TOKENS: 2048
INPUT:
  section_scope: str
  section_index: int
  query_hints: list[str]         # from Planner scope or Reflector missing_evidence
  enabled_connectors: list[str]  # see §17.1–17.6
  max_sources: int               # default 12
  targeted_mode: bool            # True when called by Post-Draft Analyzer (§5.11)
OUTPUT:
  sources: list[Source]          # ranked by SourceRanker, deduplicated
  diversity_score: float         # 0.0–1.0; see §17.8
CONSTRAINTS:
  MUST deduplicate by URL+DOI before returning
  MUST cap at max_sources (hard); drop lowest-ranked if over
  MUST flag diversity_score <0.6 → trigger re-query with diversification instruction
  NEVER include sources with reliability_score <0.20
  ALWAYS respect robots.txt in scraper fallback (§17.5)
ERROR_HANDLING:
  connector_down → cascade: sonar-pro → Tavily → Brave → BeautifulSoup scraper
  zero_results → broaden query (1×) → return empty list with warning flag
  rate_limit_429 → exponential backoff 2s→4s→8s (tenacity, max 3) → next connector
CONSUMES: [current_section_idx, outline, config.sources] from DocumentState
PRODUCES: [current_sources] -> DocumentState
```

---

## §5.3 Citation Manager

```
AGENT: CitationManager [§5.3]
RESPONSIBILITY: Build citation map from source metadata (deterministic)
MODEL: none — deterministic / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  sources: list[Source]
  citation_style: Literal["APA","Harvard","Chicago","Vancouver"]
OUTPUT:
  citation_map: dict[str, str]   # source_id → formatted citation string
  bibliography: list[str]        # ordered list of formatted entries
CONSTRAINTS:
  MUST handle ISBN sources (books/monographs) without URL (see §18.4)
  MUST generate unique source_id for every source
  NEVER mutate source metadata
  ALWAYS produce parseable bibliography; malformed entry → log + skip
ERROR_HANDLING:
  missing_doi → use URL fallback for APA/Harvard; if both absent → ISBN if present else title+publisher
  empty_sources → return empty citation_map + empty bibliography (not an error)
CONSUMES: [current_sources] from DocumentState
PRODUCES: [citation_map] -> DocumentState (ephemeral per section)
```

---

## §5.4 CitationVerifier

```
AGENT: CitationVerifier [§5.4]
RESPONSIBILITY: Verify source existence and claim–source entailment via NLI
MODEL: microsoft/deberta-v3-large-mnli (local inference) / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  sources: list[Source]
  citation_map: dict[str, str]
  claims_to_verify: list[dict]   # [{claim:str, source_id:str}]
OUTPUT:
  verified_sources: list[Source]           # http_verified=True/False added
  entailment_results: list[dict]           # [{source_id, claim, label:Literal["entailment","neutral","contradiction"], score:float}]
  ghost_citations: list[str]               # source_ids where HTTP 404 or DOI mismatch
CONSTRAINTS:
  MUST run HTTP HEAD check (timeout 3s) for every URL source
  MUST run DOI resolution via doi.org for every source with doi field
  MUST run DeBERTa NLI entailment for claims with score; threshold ENTAILMENT: score ≥0.80
  MUST flag contradiction label regardless of score
  NEVER mark a source verified if HTTP status ≠ 200 and no DOI confirms it
  ALWAYS check temporal consistency: claim_year ≤ source_published_at year
ERROR_HANDLING:
  http_timeout → retry 1× with 5s timeout → mark http_verified=False, continue
  doi_resolver_down → skip DOI check, log warning
  deberta_error → skip NLI for that claim, set label="neutral", log
CONSUMES: [current_sources, citation_map] from DocumentState
PRODUCES: [verified_sources, ghost_citations] -> DocumentState
```

---

## §5.5 SourceSanitizer

```
AGENT: SourceSanitizer [§5.5]
RESPONSIBILITY: Sanitize source content through 3-stage injection guard
MODEL: none — deterministic stages 1+3; structural stage 2 / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  verified_sources: list[Source]
OUTPUT:
  sanitized_sources: list[Source]   # content wrapped, injection patterns removed
  injection_attempts: list[dict]    # [{source_id, pattern_matched, truncated_at}]
CONSTRAINTS:
  STAGE_1 MUST run regex on raw content before any LLM sees it:
    patterns: ["ignore previous instructions","disregard system prompt",
               "<instructions>","[SYSTEM]","you are now","OVERRIDE:","ignore all above"]
    action: truncate at match position + append "[CONTENT TRUNCATED: INJECTION PATTERN]"
  STAGE_2 MUST wrap all source content in <external_source id="{source_id}"> XML tags
  STAGE_3 MUST scan any agent output for jailbreak success markers:
    patterns: ["I cannot follow my previous","my instructions have changed","new persona"]
    action: discard output + raise SECURITY_EVENT
  NEVER pass unsanitized content to Writer or any judge
  ALWAYS log injection_attempts to Run Report
ERROR_HANDLING:
  stage_1_regex_error → skip source, log, continue
  stage_3_triggered → mark agent_output as COMPROMISED, escalate to human
CONSUMES: [verified_sources] from DocumentState
PRODUCES: [sanitized_sources, injection_attempts] -> DocumentState
```

---

## §5.6 SourceSynthesizer

```
AGENT: SourceSynthesizer [§5.6]
RESPONSIBILITY: Compress verified source corpus before Writer call (Token Economy §2.12)
MODEL: anthropic/claude-sonnet-4 / TEMP: 0.1 / MAX_TOKENS: 2048
INPUT:
  sanitized_sources: list[Source]   # from §5.5
  section_scope: str
  target_compression_ratio: float   # default 0.40 (retain 40% of original token count)
  targeted_research_active: bool    # True if called after researcher_targeted; cleared here
OUTPUT:
  compressed_corpus: str            # deduplicated claims, confirmed_by fields merged
  compression_ratio_achieved: float
  skipped_source_ids: list[str]
CONSTRAINTS:
  MUST deduplicate semantically equivalent claims; merge confirmed_by into list
  MUST preserve all source_ids referenced in compressed text
  MUST achieve compression_ratio_achieved ≤ target_compression_ratio + 0.10
  NEVER fabricate claims not present in input sources
  NEVER run if len(sanitized_sources) ≤ 2 → pass through unchanged
  ALWAYS tag each retained claim with source_id inline: "claim [src:id]"
  MUST clear targeted_research_active flag (set to False) before returning,
    so writer receives targeted_research_active=False regardless of which path
    invoked source_synthesizer
ERROR_HANDLING:
  model_error → graceful degradation: return concatenated sanitized content truncated to 4000 tokens
  compression_ratio_not_met → accept result if ≥50% reduction achieved, else log warning
  model_unavailable → fallback anthropic/claude-haiku-3 → pass-through truncated
CONSUMES: [sanitized_sources, current_section_idx, targeted_research_active] from DocumentState
PRODUCES: [compressed_corpus, targeted_research_active=False] -> DocumentState (ephemeral per section)
```

---

## §5.7 Writer

```
AGENT: Writer [§5.7]
RESPONSIBILITY: Generate section draft from compressed corpus + memory + exemplar.
  On first iteration when MoW conditions are met (§7.1), this node internally
  dispatches three proposer instances (W-A/W-B/W-C) via asyncio.gather, runs the
  internal MoW jury evaluation, and invokes Fusor to produce a single fused draft
  before returning. On all other iterations, a single-draft path is used.
  The graph always sees exactly one 'writer' node with one inbound and one outbound edge.
MODEL: anthropic/claude-opus-4-5 / TEMP: 0.3 (W-A) | 0.6 (W-B) | 0.8 (W-C) / MAX_TOKENS: 8192
INPUT:
  section_scope: str
  target_words: int
  compressed_corpus: str            # from §5.6
  citation_map: dict[str, str]
  style_exemplar: Optional[str]     # from §3B.2, injected verbatim
  writer_memory: dict               # from §5.18
  reflector_feedback: Optional[list[ReflectorFeedback]]
  approved_sections_context: str    # compressed context from §5.16
  style_profile: StyleProfile
  targeted_research_active: bool    # always False at this point (cleared by §5.6)
  mow_angle: Optional[Literal["Coverage","Argumentation","Readability"]]  # see §7.2
OUTPUT:
  draft: str
  word_count: int
  citations_used: list[str]         # source_ids referenced in draft
CONSTRAINTS:
  MUST respect forbidden_patterns L1 from style profile (§26) — zero violations
  MUST inject style_exemplar in system prompt when present
  MUST inject writer_memory.recurring_errors as proactive warnings
  MUST use ONLY citations from citation_map; no external references
  MUST produce word_count within target_words ±15%
  NEVER introduce claims absent from compressed_corpus
  ALWAYS output plain prose; no markdown unless style_profile requires it
ERROR_HANDLING:
  word_count_miss >15% → single retry with explicit word constraint
  forbidden_pattern_in_output → pass to StyleFixer (§5.10), not re-generated
  model_unavailable → fallback anthropic/claude-sonnet-4 → google/gemini-2.5-pro
CONSUMES: [compressed_corpus, citation_map, style_exemplar, writer_memory,
           reflector_output, approved_sections_context] from DocumentState
PRODUCES: [current_draft, current_iteration+1] -> DocumentState
```

MoW activation: see §7.1. When MoW conditions are met, the writer node internally
runs three proposer instances (W-A/W-B/W-C) in asyncio.gather with angles from §7.2;
results feed the internal MoW jury and Fusor (§5.13) before the node returns a
single fused draft. The graph sees only a single 'writer' node with a single outbound
edge to 'post_draft_analyzer'. No external MoW nodes appear in the graph.

---

## §5.8 MetricsCollector

```
AGENT: MetricsCollector [§5.8]
RESPONSIBILITY: Compute deterministic quality metrics on draft before jury
MODEL: none — deterministic / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  draft: str
  citations_used: list[str]
  verified_sources: list[Source]
  target_words: int
OUTPUT:
  metrics: dict   # {
    #   flesch_kincaid_grade: float,
    #   avg_sentence_words: float,
    #   citation_coverage_ratio: float,    # cited_claims / total_claims (regex estimate)
    #   source_diversity_score: float,     # see §17.8
    #   plagiarism_similarity_max: float,  # cosine sim vs source texts, max across sources
    #   word_count: int,
    #   word_count_delta_pct: float,       # vs target_words
    #   draft_embedding: list[float]       # sentence embedding via all-MiniLM-L6-v2
    # }
CONSTRAINTS:
  MUST compute flesch_kincaid_grade via textstat library
  MUST flag plagiarism_similarity_max >0.40 in metrics (not block; jury decides)
  MUST compute citation_coverage_ratio; flag if <0.50
  MUST compute sentence embedding of draft using sentence-transformers/all-MiniLM-L6-v2
    and append to DocumentState.draft_embeddings list
  NEVER modify draft
  ALWAYS complete within 5s; timeout → return partial metrics with null fields
ERROR_HANDLING:
  textstat_error → set flesch_kincaid_grade=null, continue
  similarity_compute_error → set plagiarism_similarity_max=null, continue
  embedding_error → set draft_embedding=null, log warning, continue
CONSUMES: [current_draft, citations_used, verified_sources] from DocumentState
PRODUCES: [run_metrics.section_metrics[current_section_idx]] -> DocumentState
         [draft_embeddings append] -> DocumentState
```

---

## §5.9 StyleLinter

```
AGENT: StyleLinter [§5.9]
RESPONSIBILITY: Deterministic pre-jury check for L1/L2 rule violations
MODEL: none — deterministic regex / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  draft: str
  style_rules: list[dict]    # L1+L2 rules from active style profile (§26)
  universal_forbidden: list[str]  # see §26.9
OUTPUT:
  violations: list[StyleViolation]
  l1_count: int
  l2_count: int
  linter_pass: bool          # True iff l1_count == 0 AND l2_count == 0
CONSTRAINTS:
  MUST scan L1 (FORBIDDEN) patterns as case-insensitive regex; any match → violation
  MUST scan L2 (REQUIRED) elements; absence → violation
  MUST scan universal_forbidden (§26.9) in addition to profile-specific
  NEVER use LLM for any part of this check
  ALWAYS report exact char position and matched_text for each violation
  ALWAYS complete before jury invocation; if linter_pass=False → route to StyleFixer (§5.10)
ERROR_HANDLING:
  invalid_regex → skip rule, log warning, continue
  timeout >2s → return partial results with timeout_flag=True
CONSUMES: [current_draft, config.style_profile] from DocumentState
PRODUCES: [style_violations] -> DocumentState; routes to StyleFixer if linter_pass=False
```

---

## §5.10 StyleFixer

```
AGENT: StyleFixer [§5.10]
RESPONSIBILITY: Correct L1/L2 style violations without altering content
MODEL: anthropic/claude-sonnet-4 / TEMP: 0.2 / MAX_TOKENS: 4096
INPUT:
  draft: str
  violations: list[StyleViolation]   # from §5.9
  style_exemplar: Optional[str]
  citation_map: dict[str, str]
OUTPUT:
  fixed_draft: str
  unfixable_violations: list[str]    # violation ids where fix would alter content
  style_fix_iterations: int
CONSTRAINTS:
  MUST correct ONLY the violations listed; no other edits
  MUST preserve all facts, numbers, citations, argument structure verbatim
  MUST re-run StyleLinter after fix; if violations remain → second pass (max 2 total)
  NEVER alter source_ids or citation strings
  NEVER fix if fix requires changing a factual claim → add to unfixable_violations
  ALWAYS set style_fix_iterations counter; if 2 passes fail → escalate to Reflector
ERROR_HANDLING:
  model_error → return original draft + all violations as unfixable
  model_unavailable → fallback anthropic/claude-haiku-3
CONSUMES: [current_draft, style_violations, style_exemplar] from DocumentState
PRODUCES: [current_draft (fixed)] -> DocumentState
```

---

## §5.11 PostDraftAnalyzer

```
AGENT: PostDraftAnalyzer [§5.11]
RESPONSIBILITY: Proactively identify information gaps in draft before jury
MODEL: google/gemini-2.5-flash / TEMP: 0.2 / MAX_TOKENS: 1024
INPUT:
  draft: str
  section_scope: str
  current_sources: list[Source]
  iteration: int
OUTPUT:
  gaps: list[dict]   # max 3; [{
    #   category: Literal["missing_evidence","emerging_subtopic","forward_looking"],
    #   description: str,
    #   suggested_queries: list[str]   # max 2 per gap
    # }]
  gap_found: bool
CONSTRAINTS:
  MUST run only on iteration == 1 (first draft per section)
  MUST NOT run if quality_preset == "Economy"
  MUST NOT run if len(current_sources) > 20
  MUST NOT run if section target_words < 400
  MUST cap at 3 gaps; ignore additional ones
  MUST complete within 30s; timeout → return gap_found=False
  NEVER suggest queries already answered by current_sources
ERROR_HANDLING:
  model_error → return gap_found=False, skip targeted research
  model_unavailable → fallback meta/llama-3.3-70b-instruct
  timeout → return gap_found=False
CONSUMES: [current_draft, current_sources, current_iteration] from DocumentState
PRODUCES: [post_draft_gaps] -> DocumentState; triggers targeted Researcher (§5.2) if gap_found=True
```

---

## §5.12 SpanEditor

```
AGENT: SpanEditor [§5.12]
RESPONSIBILITY: Apply surgical span-level edits from Reflector without full rewrite
MODEL: anthropic/claude-sonnet-4 / TEMP: 0.1 / MAX_TOKENS: 2048
INPUT:
  draft: str
  spans: list[ReflectorFeedback]   # scope==SURGICAL only, ≤4 spans
  citation_map: dict[str, str]
  style_profile: StyleProfile
  writer_memory: dict
OUTPUT:
  replacements: list[dict]   # [{original:str, replacement:str, feedback_id:str}]
  unfixable_span_ids: list[str]
CONSTRAINTS:
  MUST only edit the affected_text spans listed; all other text verbatim
  MUST connect fluently to context_before and context_after
  MUST respect replacement_length_hint (SHORTER|SAME|LONGER)
  NEVER introduce citations not in citation_map
  NEVER run on iteration ≥ 3 (degradation risk) → force Writer (§5.7) instead
  NEVER run if span count > 4 → route to Writer
  ALWAYS validate that affected_text appears exactly once in draft; if 0 or >1 → DiffMerger raises error → fallback Writer
ERROR_HANDLING:
  ambiguous_span (count ≠ 1) → add to unfixable_span_ids, skip
  content_altering_fix → add to unfixable_span_ids, preserve original
  model_unavailable → fallback Writer (§5.7) for full section
CONSUMES: [current_draft, reflector_output.spans] from DocumentState
PRODUCES: [span_replacements] -> diff_merger node -> [current_draft] -> DocumentState
```

DiffMerger (deterministic) — implemented as the `diff_merger` graph node:
```python
def apply_edits(draft: str, edits: list[dict]) -> str:
    sorted_edits = sorted(edits, key=lambda e: draft.rfind(e["original"]), reverse=True)
    for edit in sorted_edits:
        if draft.count(edit["original"]) != 1:
            raise ValueError(f"Ambiguous span: {edit['original'][:40]}")
        draft = draft.replace(edit["original"], edit["replacement"], 1)
    return draft
```

Graph edges for the surgical path:
```python
g.add_edge('span_editor', 'diff_merger')
g.add_edge('diff_merger', 'style_linter')   # re-lint after surgical edits
```

---

## §5.13 Fusor

```
AGENT: Fusor [§5.13]
RESPONSIBILITY: Synthesize MoW multi-draft into single base draft
  (invoked internally by the writer node when MoW is active — see §7.1)
MODEL: openai/o3 / TEMP: 0.2 / MAX_TOKENS: 8192
INPUT:
  drafts: list[dict]          # [{draft:str, css_individual:float, proposer:str}]
  best_elements: list[dict]   # [{source_draft:str, element_text:str, reason:str}] from jury_multi_draft
  section_scope: str
  style_exemplar: Optional[str]
OUTPUT:
  fused_draft: str
  base_draft_used: str        # proposer id with highest css_individual
  integration_rate: float     # fraction of best_elements incorporated
CONSTRAINTS:
  MUST use draft with highest css_individual as structural base; tie-break: highest Judge F CSS
  MUST integrate best_elements genuinely (rewrite transitions, not append)
  NEVER add claims absent from all three input drafts
  NEVER re-optimize style (that is Writer + StyleFixer responsibility)
  ALWAYS run exactly once per section on first iteration when MoW is active (§7.1)
  ALWAYS discard draft if its veto_category == "fabricated_source" entirely
ERROR_HANDLING:
  model_error → return highest-css_individual draft unchanged as fused_draft
  model_unavailable → fallback openai/o3-mini → anthropic/claude-opus-4-5
CONSUMES: [mow_drafts, mow_best_elements] from DocumentState
PRODUCES: [current_draft (fused)] -> DocumentState (via writer node)
```

---

## §5.14 Reflector

```
AGENT: Reflector [§5.14]
RESPONSIBILITY: Synthesize jury feedback into structured actionable edit instructions
MODEL: openai/o3 / TEMP: 0.3 / MAX_TOKENS: 4096
INPUT:
  all_verdicts_history: list[JudgeVerdict]   # all rounds for current section
  current_draft: str
  css_history: list[float]
  section_scope: str
  iteration: int
OUTPUT:
  feedback: list[ReflectorFeedback]   # priority-sorted
  scope: Scope                        # SURGICAL | PARTIAL | FULL
  conflict_resolution: list[dict]     # [{feedback_ids, resolution, reason}]
CONSTRAINTS:
  MUST assign severity (CRITICAL/HIGH/MEDIUM/LOW) to every feedback item
  MUST resolve contradictory feedback: higher severity wins; tie → Judge Factual wins
  MUST set scope=SURGICAL only if ≤4 isolated spans AND iteration ≤ 2
  MUST set scope=FULL only if argument structure is fundamentally flawed
  MUST set scope=PARTIAL for all other cases
  MUST route scope=FULL to human escalation (never to Writer alone)
  NEVER generate feedback requiring content change to fix a style issue
  ALWAYS analyze full verdicts_history for recurring error patterns
ERROR_HANDLING:
  model_error → return single HIGH feedback "rewrite section with attention to jury notes"
  parse_error → retry with simplified prompt → fallback scope=PARTIAL
  model_unavailable → fallback openai/o3-mini
CONSUMES: [all_verdicts_history, current_draft, css_history] from DocumentState
PRODUCES: [reflector_output] -> DocumentState; routes to oscillation_check (SURGICAL/PARTIAL) or await_human (FULL)
```

---

## §5.15 OscillationDetector

```
AGENT: OscillationDetector [§5.15]
RESPONSIBILITY: Detect CSS, semantic, and whack-a-mole oscillation patterns
MODEL: none — deterministic + sentence-transformers (local) / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  css_history: list[float]             # current section
  draft_embeddings: list[list[float]]  # one per iteration
  all_verdicts_history: list[JudgeVerdict]
  oscillation_window: int              # default 4
  variance_threshold: float            # default 0.05
  semantic_similarity_threshold: float # default 0.85
OUTPUT:
  oscillation_detected: bool
  oscillation_type: Optional[Literal["CSS","SEMANTIC","WHACK_A_MOLE"]]
  early_warning: bool   # True if approaching but not yet triggered
CONSTRAINTS:
  CSS_OSCILLATION: variance(css_history[-oscillation_window:]) < variance_threshold
    AND len(css_history) >= oscillation_window
  SEMANTIC_OSCILLATION: cosine_sim(draft_N, draft_{N-2}) > semantic_similarity_threshold
    AND cosine_sim(draft_N, draft_{N-1}) < semantic_similarity_threshold
    requires ≥3 embeddings
  WHACK_A_MOLE: error categories in verdicts rotate completely ≥3 consecutive iterations
  early_warning: any condition met with window-1 observations
  MUST use sentence-transformers all-MiniLM-L6-v2 for embeddings (local, zero API cost)
  NEVER trigger on iteration < 3
ERROR_HANDLING:
  embedding_error → skip SEMANTIC check, continue CSS+WHACK_A_MOLE
  insufficient_history → return oscillation_detected=False
CONSUMES: [css_history, draft_embeddings, all_verdicts_history, current_iteration] from DocumentState
PRODUCES: [oscillation_detected, oscillation_type, human_intervention_required] -> DocumentState
```

---

## §5.16 ContextCompressor

```
AGENT: ContextCompressor [§5.16]
RESPONSIBILITY: Compress approved sections into context budget for Writer
MODEL: qwen/qwen3-7b / TEMP: 0.1 / MAX_TOKENS: 2048
INPUT:
  approved_sections: list[dict]      # full content of approved sections
  outline: list[dict]
  current_section_idx: int
  context_budget_tokens: int         # computed from MECW formula (§Scalability)
OUTPUT:
  compressed_context: str
  load_bearing_claims: list[str]     # preserved verbatim regardless of position
CONSTRAINTS:
  NEVER invoke on section_idx == 0 (first section has no prior context to compress).
    When current_section_idx == 0, return immediately with compressed_context = ""
    and load_bearing_claims = [] (no-op). The graph edge from coherence_guard always
    routes through context_compressor; the no-op on idx==0 is the implementation
    contract that avoids adding a separate conditional edge.
  MUST apply position-based strategy for idx > 0:
    idx >= current-1 or current-2: verbatim (last 2 sections)
    idx in [current-3, current-5]: structured summary 80–120 words per section
    idx < current-5: thematic extract, key claims only
  MUST preserve verbatim any claim tagged as load_bearing (referenced in future section scopes)
  MUST fit output within context_budget_tokens (measured by tiktoken cl100k_base)
  NEVER summarize the current section being written
  ALWAYS invoke after coherence_guard confirms no HARD conflicts, before section_checkpoint
ERROR_HANDLING:
  model_error → return truncated raw content within budget
  budget_exceeded → aggressive truncation: discard extract-level sections first
  model_unavailable → fallback meta/llama-3.3-70b-instruct
CONSUMES: [approved_sections, outline, current_section_idx] from DocumentState
PRODUCES: [compressed_context] -> DocumentState
```

---

## §5.17 CoherenceGuard

```
AGENT: CoherenceGuard [§5.17]
RESPONSIBILITY: Detect factual contradictions between new section and approved sections
MODEL: google/gemini-2.5-flash / TEMP: 0.1 / MAX_TOKENS: 2048
INPUT:
  new_section_content: str
  approved_sections: list[dict]   # {index, title, content}
  section_index: int
OUTPUT:
  conflicts: list[dict]   # [{
    #   type: Literal["SOFT","HARD"],
    #   claim_new: str,
    #   claim_existing: str,
    #   existing_section_index: int,
    #   description: str
    # }]
  conflict_detected: bool
CONSTRAINTS:
  SOFT conflict: numerical inconsistency or phrasing ambiguity → log + warning, do not block
  HARD conflict: direct logical contradiction of factual claim → escalate to human
  MUST compare only factual claims (dates, numbers, causal statements), not opinions
  NEVER modify content; only report
  ALWAYS run BEFORE context_compressor and section_checkpoint nodes
ERROR_HANDLING:
  model_error → return conflict_detected=False, log warning
  model_unavailable → fallback google/gemini-1.5-flash → skip with warning
CONSUMES: [current_draft (approved), approved_sections] from DocumentState
PRODUCES: [coherence_conflicts] -> DocumentState; HARD → await_human node
```

---

## §5.18 WriterMemory

```
AGENT: WriterMemory [§5.18]
RESPONSIBILITY: Accumulate and inject cross-section Writer error patterns
MODEL: none — deterministic accumulator / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  new_verdicts: list[JudgeVerdict]
  new_violations: list[StyleViolation]
  section_index: int
  draft: str
OUTPUT:
  writer_memory: dict   # {
    #   recurring_errors: list[str],         # forbidden patterns seen ≥2× across sections
    #   technical_glossary: dict[str,str],   # term → canonical form
    #   style_drift_index: float,            # 0.0–1.0; alert if >0.05
    #   citation_tendency: Literal["under","normal","over"],
    #   proactive_warnings: list[str]        # injected into Writer prompt
    # }
CONSTRAINTS:
  MUST track forbidden pattern occurrences across sections; flag recurring if count ≥ 2
  MUST compute style_drift_index as cosine distance between section embeddings
  MUST alert if style_drift_index > 0.05 (via Run Companion notification)
  MUST update citation_tendency based on citation_coverage_ratio history
  NEVER expose internal state to any agent other than Writer (§5.7)
  ALWAYS update synchronously after each section approval
ERROR_HANDLING:
  accumulation_error → return last known writer_memory unchanged
CONSUMES: [all_verdicts_history, style_violations, approved_sections] from DocumentState
PRODUCES: [writer_memory] -> DocumentState (persistent across sections)
```

---

## §5.19 Publisher

```
AGENT: Publisher [§5.19]
RESPONSIBILITY: Assemble approved sections into final document artifacts
MODEL: none — deterministic / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  approved_sections: list[dict]      # ordered by index
  bibliography: list[str]
  output_formats: list[Literal["docx","pdf","markdown","latex","html","json"]]
  citation_style: Literal["APA","Harvard","Chicago","Vancouver"]
  template_path: Optional[str]       # DOCX template; fallback to default
  run_metrics: dict
OUTPUT:
  output_paths: dict[str, str]       # format → S3/MinIO path
  word_count_final: int
  target_words_delta_pct: float
CONSTRAINTS:
  MUST verify word_count_final within target_words ±10% before publishing
  MUST generate automatic TOC for DOCX (python-docx Heading styles)
  MUST append bibliography as final section
  MUST include run_metrics as JSON metadata in all formats
  NEVER publish if any approved_section has content=None
  ALWAYS produce DOCX as primary; other formats derived
  ALWAYS use section.version (latest) from Store (§21.1)
ERROR_HANDLING:
  docx_build_error → retry with minimal template → fallback plain markdown
  pdf_convert_error → log warning, skip PDF, continue with other formats
  s3_upload_error → retry 3× with backoff → store locally, return local path
CONSUMES: [approved_sections, bibliography, config.output, run_metrics] from DocumentState
PRODUCES: [output_paths, run_metrics.final] -> DocumentState
```

---

## §5.20 FeedbackCollector

```
AGENT: FeedbackCollector [§5.20]
RESPONSIBILITY: Collect post-delivery user feedback and update training loop
MODEL: none — API endpoint receiver / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  run_id: str
  section_ratings: dict[int, Literal[1,2,3,4,5]]    # section_index → 1–5
  error_highlights: list[dict]    # [{section_index, text_excerpt, error_type}]
  source_blacklist: list[str]     # URLs/DOIs to blacklist
  style_feedback: str             # free text, max 500 chars
OUTPUT:
  feedback_record: dict           # persisted to PostgreSQL feedback table
  blacklist_updated: bool
  prompt_improvement_signal: dict # {agent, dimension, delta_direction}
CONSTRAINTS:
  MUST persist feedback_record atomically; partial write → rollback
  MUST update source_blacklist in config immediately (affects subsequent runs)
  MUST generate prompt_improvement_signal for agents with avg section_rating <3.0
  NEVER expose feedback from other users or other run_ids
  ALWAYS timestamp and user_id-tag every feedback record
ERROR_HANDLING:
  db_write_error → retry 3× → store in Redis fallback queue → async flush
  invalid_rating → reject with 422, do not partial-persist
CONSUMES: [run_id, user_id] from DocumentState (read-only, post-completion)
PRODUCES: [feedback_record] -> PostgreSQL; [source_blacklist update] -> config store
```

---

## §5.21 SectionCheckpoint

```
AGENT: SectionCheckpoint [§5.21]
RESPONSIBILITY: Mark an approved section as complete, persist it, advance section index,
  and trigger downstream context compression
MODEL: none — deterministic / TEMP: n/a / MAX_TOKENS: n/a
INPUT:
  current_draft: str                  # content approved by jury (CSS_content ≥threshold, CSS_style ≥threshold)
  css_history: list[float]            # full CSS history for current section
  jury_verdicts: list[JudgeVerdict]   # all verdicts for current section (all iterations)
  current_section_idx: int
  outline: list[dict]                 # for title/scope lookup
  doc_id: str
  run_id: str
OUTPUT:
  approved_sections: list[dict]       # previous list + newly appended entry:
    # {
    #   index: int,
    #   title: str,
    #   content: str,
    #   css_final: float,             # css_history[-1]
    #   css_breakdown: dict,          # {css_content: float, css_style: float}
    #   iterations_used: int,         # len(css_history)
    #   verdicts_history: list[JudgeVerdict],
    #   approved_at: str,             # ISO 8601 timestamp
    #   version: int                  # 1 for first approval; incremented on regeneration
    # }
  current_section_idx: int            # previous value + 1
  writer_memory: dict                 # updated via update_writer_memory() call
CONSTRAINTS:
  MUST INSERT one row into PostgreSQL sections table before updating current_section_idx:
    columns: document_id, run_id, section_index, title, content, css_final,
             css_breakdown (JSONB), iterations_used, verdicts_history (JSONB),
             approved_at (TIMESTAMPTZ DEFAULT now()), version
  MUST set approved_at timestamp atomically with the INSERT (database DEFAULT now())
  MUST call update_writer_memory(new_verdicts, new_violations, section_index, draft)
    synchronously before returning; WriterMemory (§5.18) accumulates cross-section patterns
  MUST increment current_section_idx by exactly 1 after successful DB INSERT
  MUST append the new approved section dict to approved_sections in DocumentState
  MUST emit a SECTION_APPROVED SSE event with {section_index, css_final, approved_at}
  NEVER advance current_section_idx if the DB INSERT fails (preserve idempotency)
  NEVER modify the content of any previously approved section entry
  ALWAYS run after CoherenceGuard (§5.17) confirms no HARD conflicts
  ALWAYS run after ContextCompressor (§5.16) has updated compressed_context
    (or returned no-op when current_section_idx == 0)
ERROR_HANDLING:
  db_insert_error → retry 3× with exponential backoff (1s→2s→4s) →
    if all retries fail: set status=CHECKPOINT_FAILED, emit alert, halt section advancement,
    preserve current_section_idx unchanged, raise to orchestrator for human escalation
  duplicate_insert (unique constraint violation on document_id+section_index+version) →
    log warning, skip insert (idempotent resume after crash), advance current_section_idx
  writer_memory_update_error → log warning, continue with last known writer_memory;
    section advancement is NOT blocked by WriterMemory failure
CONSUMES: [current_draft, css_history, jury_verdicts, current_section_idx,
           outline, doc_id, run_id] from DocumentState
PRODUCES:
  [approved_sections append] -> DocumentState
  [current_section_idx + 1] -> DocumentState
  [writer_memory (updated)] -> DocumentState
  [sections table INSERT] -> PostgreSQL
  [SECTION_APPROVED event] -> SSE stream
```

Graph edges for the section completion path:

```python
# Correct ordering:
# aggregator → coherence_guard → context_compressor → section_checkpoint
#
# context_compressor is a no-op when current_section_idx == 0 (§5.16 CONSTRAINTS).
# It always routes to section_checkpoint; the graph uses a simple edge (no conditional).

g.add_conditional_edges('coherence_guard', route_after_coherence, {
    'no_conflict':   'context_compressor',
    'soft_conflict': 'context_compressor',
    'hard_conflict': 'await_human'
})
g.add_edge('context_compressor', 'section_checkpoint')

g.add_conditional_edges('section_checkpoint', route_next_section, {
    'next_section': 'researcher',   # more sections remain
    'all_done':     'post_qa'       # all sections approved → Phase C
})
```

---

## §5.22 LengthAdjuster

```
AGENT: LengthAdjuster [§5.22]
RESPONSIBILITY: Correct word count of the assembled document during Phase C post-QA
  when final length falls outside the target_words ±10% tolerance.
MODEL: anthropic/claude-opus-4-5 / TEMP: 0.2 / MAX_TOKENS: 8192
INPUT:
  approved_sections: list[dict]   # assembled document sections from Store
  target_words: int               # from DRSConfig
  actual_words: int               # measured by Publisher during format validation
  delta_pct: float                # (actual_words - target_words) / target_words
OUTPUT:
  adjusted_sections: list[dict]   # same structure as approved_sections; content updated
  adjustment_applied: bool
  final_word_count: int
CONSTRAINTS:
  MUST NOT invoke the full jury/reflector loop — LengthAdjuster operates in Phase C
    after all sections are approved; it corrects length only, not content quality
  MUST NOT alter citations, source_ids, or factual claims
  MUST target final_word_count within target_words ±5% after adjustment
  MUST trim from lower-priority sections first (later sections, appendix-style content)
    when delta_pct > 0 (too long); expand underweight sections when delta_pct < 0
  MUST update approved_sections in DocumentState with adjusted content
  NEVER re-run coherence_guard or section_checkpoint after adjustment
  ALWAYS log adjustment details in run_metrics.length_adjustment
  ALWAYS route to publisher after completion (graph edge: length_adjuster → publisher)
ERROR_HANDLING:
  model_error → return sections unchanged; set adjustment_applied=False; log WARNING
  target_not_achievable (e.g., document is 50% too long) →
    apply maximum feasible reduction, log WARNING, continue to publisher
  model_unavailable → fallback anthropic/claude-sonnet-4 → return unchanged
CONSUMES: [approved_sections, target_words, format_validated, run_metrics] from DocumentState
PRODUCES: [approved_sections (updated), run_metrics.length_adjustment] -> DocumentState
```

---

## §12.5 route_after_reflector()

```python
def route_after_reflector(state: DocumentState) -> Literal[
    "oscillation_check", "await_human"
]:
    """
    Canonical definition — §12.5.
    Routes based on reflector_output.dominant_scope:
      FULL     → await_human directly (argument structurally broken;
                 oscillation detection irrelevant at this point)
      SURGICAL → oscillation_check (which routes to span_editor if no oscillation
                 and iteration <= 2, or writer if iteration > 2)
      PARTIAL  → oscillation_check (which routes to writer if no oscillation)
    """
    scope = state["reflector_output"]["dominant_scope"]
    if scope == "FULL":
        return "await_human"          # bypass oscillation_check entirely
    return "oscillation_check"        # covers SURGICAL and PARTIAL


def route_after_oscillation(state: DocumentState) -> Literal[
    "span_editor", "writer", "escalate_human"
]:
    """
    Scope-aware routing from oscillation_check node.
    Reads both oscillation_detected AND reflector_output.dominant_scope.

    Priority:
      oscillation_detected → escalate_human (any scope)
      SURGICAL + iteration <= 2 → span_editor
      all other cases (PARTIAL, or SURGICAL iter > 2) → writer

    Budget threshold warnings are handled by the BudgetController node,
    which runs before every Writer/Jury call. The oscillation detector
    only determines whether the section loop can continue or must escalate.
    """
    if state.get("oscillation_detected"):
        return "escalate_human"
    scope = state["reflector_output"]["dominant_scope"]
    iteration = state.get("current_iteration", 1)
    if scope == "SURGICAL" and iteration <= 2:
        return "span_editor"          # §5.12
    return "writer"                   # §5.7 — covers PARTIAL and SURGICAL iter>2
```

---

## §5.23 ResearcherTargeted

```
AGENT: ResearcherTargeted [§5.23]
RESPONSIBILITY: Execute targeted re-research for specific gaps identified by PostDraftAnalyzer
  or for missing evidence flagged by JuryFactual. Sets targeted_research_active=True so
  downstream agents (source_synthesizer, writer) can distinguish this path from initial research.
MODEL: perplexity/sonar-pro / TEMP: 0.1 / MAX_TOKENS: 2048
INPUT:
  post_draft_gaps: list[dict]    # [{category, description, suggested_queries}]
  section_scope: str
  section_index: int
  existing_sources: list[Source]  # to avoid duplicate retrieval
  targeted_research_active: bool  # set to True by this node
OUTPUT:
  additional_sources: list[Source]  # targeted results, deduplicated vs existing_sources
  targeted_research_active: bool    # always True on output
CONSTRAINTS:
  MUST set targeted_research_active = True in DocumentState
  MUST deduplicate against existing current_sources (no re-fetch of known sources)
  MUST use suggested_queries from post_draft_gaps if available; otherwise derive from gap description
  NEVER rerun on iteration > 1 (graph-level guard in route_post_draft_gap enforces this)
  MUST merge additional_sources into current_sources before citation_manager re-runs
ERROR_HANDLING:
  zero_results → return empty additional_sources; targeted_research_active still True
  connector_down → see §5.2 error handling (identical cascade)
CONSUMES: [post_draft_gaps, current_sources, current_section_idx] from DocumentState
PRODUCES: [current_sources (merged), targeted_research_active=True] -> DocumentState
```

---

## Agent Routing Summary

```python
# Post-Aggregator routing (§4.5 cross-ref)
# These are the keys returned by route_after_aggregator() (canonical: §9.4)
# and consumed by g.add_conditional_edges('aggregator', ...).
AggregatorRouteKey = Literal[
    "approved",          # CSS_content ≥ threshold AND CSS_style ≥ threshold → coherence_guard
    "force_approve",     # BudgetController iteration cap override → coherence_guard
    "fail_style",        # CSS_content pass, CSS_style < threshold → style_fixer
    "fail_reflector",    # CSS_content < threshold → reflector; scope then determines next hop
    "panel",             # CSS_content < panel_trigger → panel_discussion
    "veto",              # any L1 veto or L2 R/F unanimous FAIL → reflector
    "fail_missing_ev",   # judge_f.missing_evidence nonempty → researcher_targeted
    "budget_hard_stop",  # budget.spent ≥ budget.max → publisher (partial)
]

# Post-Reflector routing — two-stage routing explanation:
# Stage 1: aggregator emits 'fail_reflector' or 'veto' → reflector runs
# Stage 2: route_after_reflector() reads reflector_output.dominant_scope and returns:
ReflectorRouteKey = Literal[
    "oscillation_check",  # scope=SURGICAL or PARTIAL → oscillation_check
                          #   oscillation_check then routes via route_after_oscillation():
                          #     span_editor (SURGICAL, iter<=2, no oscillation)
                          #     writer      (PARTIAL or SURGICAL iter>2, no oscillation)
                          #     escalate_human (oscillation detected, any scope)
    "await_human",        # scope=FULL → directly, bypassing oscillation_check
]
```

<!-- SPEC_COMPLETE -->