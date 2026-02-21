# 26. Style Profiles and L1/L2/L3 Rule System

## 26.1 Three-Level Enforcement Architecture

```python
from typing import Literal, Optional
import re

EnforcementLevel = Literal["L1", "L2", "L3"]
RuleCategory = Literal[
    "lexical", "structural", "ai_fingerprint",
    "citation", "register", "rhetoric"
]
Enforcement = Literal["BLOCK", "REQUIRE", "GUIDE"]

class StyleRule:
    id: str                        # e.g. "L1-UNIV-001"
    level: EnforcementLevel
    category: RuleCategory
    enforcement: Enforcement
    message: str                   # shown to Style Fixer
    fix_hint: str                  # actionable correction instruction
    regex_pattern: Optional[str]   # required for L1; optional for L2
```

| Level | Enforcement | Checked by | Blocks pipeline? | Regex required? |
|-------|-------------|------------|------------------|-----------------|
| L1 | BLOCK | Style Linter (deterministic, pre-jury) | YES — returns to Style Fixer | YES |
| L2 | REQUIRE | Style Linter (deterministic, pre-jury) | YES — returns to Style Fixer | Optional |
| L3 | GUIDE | Mini-jury S | NO — lowers CSS_style only | NO |

**Execution order**: Style Linter runs L1+L2 checks → if violations → Style Fixer → re-lint → if clean → jury S evaluates L3.

CSS_style threshold: `>= 0.80` (see §9.3). L1 violation count = 0 required before jury S activation.

---

## 26.2 Universal Forbidden Patterns (All Profiles)

Applied before profile-specific rules. L1 enforcement on all.

```python
UNIVERSAL_L1_RULES: list[StyleRule] = [
    StyleRule(
        id="L1-UNIV-001", level="L1", category="ai_fingerprint",
        enforcement="BLOCK",
        message="Trite AI opening phrase detected",
        fix_hint="Delete entire phrase; start sentence with substantive content",
        regex_pattern=r"(?i)\b(it is (worth|important) (noting|to note)|needless to say|as we can see|as mentioned (above|earlier))\b"
    ),
    StyleRule(
        id="L1-UNIV-002", level="L1", category="structural",
        enforcement="BLOCK",
        message="Dictionary-definition opening paragraph",
        fix_hint="Replace with concrete example, data point, or direct claim",
        regex_pattern=r"(?i)^[^\n]{0,120}(is defined as|refers to|can be defined as)[^\n]{0,200}\n"
    ),
    StyleRule(
        id="L1-UNIV-003", level="L1", category="ai_fingerprint",
        enforcement="BLOCK",
        message="Conclusion meta-phrase",
        fix_hint="Remove phrase; state conclusion content directly",
        regex_pattern=r"(?i)\b(in conclusion,?|to summarize,?|in summary,?|to conclude,?)\b"
    ),
    StyleRule(
        id="L1-UNIV-004", level="L1", category="ai_fingerprint",
        enforcement="BLOCK",
        message="Triadic list repetition (X, Y, and Z pattern used 3+ times)",
        fix_hint="Vary structure: use prose, two-element pairs, or numbered lists",
        regex_pattern=r"(\b\w[\w\s]{2,20},\s\w[\w\s]{2,20},?\s+and\s+\w[\w\s]{2,20}\b.*){3,}"
    ),
    StyleRule(
        id="L1-UNIV-005", level="L1", category="ai_fingerprint",
        enforcement="BLOCK",
        message="Meta-reference to document itself",
        fix_hint="State the content directly without self-reference",
        regex_pattern=r"(?i)\b(this (article|paper|document|report|essay) (will|aims to|explores|examines|discusses))\b"
    ),
    StyleRule(
        id="L1-UNIV-006", level="L1", category="ai_fingerprint",
        enforcement="BLOCK",
        message="'Delve into' AI fingerprint",
        fix_hint="Replace with 'examine', 'analyze', 'investigate', or remove",
        regex_pattern=r"(?i)\bdelve[sd]?\s+into\b"
    ),
]
```

**Good/Bad examples** (one per universal pattern):

| Rule | BAD | GOOD |
|------|-----|------|
| L1-UNIV-001 | "It is worth noting that inflation affects..." | "Inflation affects purchasing power through..." |
| L1-UNIV-002 | "Blockchain is defined as a distributed ledger..." | "Bitcoin's 2009 launch demonstrated..." |
| L1-UNIV-003 | "In conclusion, the evidence shows..." | "Three factors drive adoption:..." |
| L1-UNIV-005 | "This paper will explore the impact of..." | "AI investment surged 340% between 2020–2024." |
| L1-UNIV-006 | "We delve into the mechanisms of..." | "We examine the mechanisms of..." |

---

## 26.3 Profile Definitions

### Schema

```python
ProfileName = Literal[
    "scientific_report", "business_report", "technical_documentation",
    "journalistic", "narrative_essay", "ai_instructions", "blog"
]

class StyleProfile:
    name: ProfileName
    tone: Literal["formal", "semi-formal", "conversational", "authoritative", "analytical"]
    register: Literal["C1", "C2", "B2", "mixed"]
    rules: list[StyleRule]
    writer_angles: dict[Literal["W-A", "W-B", "W-C"], str]  # see §7.3
```

---

### 26.3.1 `scientific_report`

```yaml
tone: formal
register: C2
writer_angles:
  W-A: "Complete literature coverage; standard paper structure (intro/methods/results/discussion); all sub-aspects addressed"
  W-B: "Logical flow of argument; cautious hedging on uncertain claims ('suggests' not 'proves'); clear hypothesis chain"
  W-C: "Academic prose fluency; syntactic variety; zero redundant hedging"
rules:
  L1:
    - id: L1-SCI-001
      category: lexical
      message: "Overconfident claim without hedge"
      fix_hint: "Replace 'proves/shows/demonstrates' with 'suggests/indicates/implies' unless claim is definitively established"
      regex_pattern: "(?i)\\b(this proves|definitively shows|clearly demonstrates|it is certain that)\\b"
    - id: L1-SCI-002
      category: ai_fingerprint
      message: "Bullet list in body text (not permitted in scientific prose)"
      fix_hint: "Convert to numbered list only if strictly procedural, else integrate into prose"
      regex_pattern: "^\\s*[-•*]\\s+.{20,}"
  L2:
    - id: L2-SCI-001
      category: structural
      enforcement: REQUIRE
      message: "Abstract missing"
      fix_hint: "Add 150–250 word abstract as first paragraph: background, objective, method, result, conclusion"
    - id: L2-SCI-002
      category: citation
      enforcement: REQUIRE
      message: "Fewer than 5 peer-reviewed citations"
      fix_hint: "Researcher must supply minimum 5 DOI-verified academic sources"
  L3:
    - id: L3-SCI-001
      category: lexical
      enforcement: GUIDE
      message: "Lexical repetition: same root word within 3 sentences"
      fix_hint: "Use synonym or restructure"
    - id: L3-SCI-002
      category: structural
      enforcement: GUIDE
      message: "Paragraph exceeds 150 words without topic-sentence break"
      fix_hint: "Split at logical sub-argument boundary"
```

---

### 26.3.2 `business_report`

```yaml
tone: authoritative
register: C1
writer_angles:
  W-A: "All data and operational implications covered; executive summary implicit in structure"
  W-B: "Problem→evidence→recommendation hierarchy; active voice; every recommendation actionable"
  W-C: "Short sentences (avg ≤22 words); short paragraphs (≤5 sentences); eliminate jargon"
rules:
  L1:
    - id: L1-BIZ-001
      category: lexical
      message: "Business buzzword detected"
      fix_hint: "Replace with specific operational term or concrete description"
      regex_pattern: "(?i)\\b(synerg(y|ies|ize)|leverage[sd]?|paradigm shift|holistic(ally)?|best-in-class|value-add|move the needle|circle back|boil the ocean)\\b"
    - id: L1-BIZ-002
      category: lexical
      message: "Vague intensifier without metric"
      fix_hint: "Quantify: replace 'significant/major/substantial' with the actual number or percentage"
      regex_pattern: "(?i)\\b(significant(ly)?|substantial(ly)?|major(ly)?|considerable)\\s+(increase|decrease|growth|decline|improvement)\\b"
  L2:
    - id: L2-BIZ-001
      category: structural
      enforcement: REQUIRE
      message: "Executive summary missing or <150 words"
      fix_hint: "Add executive summary section: problem, key findings, top 3 recommendations, required actions"
    - id: L2-BIZ-002
      category: rhetoric
      enforcement: REQUIRE
      message: "Recommendation lacks specific action owner or timeline"
      fix_hint: "Each recommendation must specify: what, who (role), by when"
  L3:
    - id: L3-BIZ-001
      category: structural
      enforcement: GUIDE
      message: "Section lacks data point supporting main claim"
      fix_hint: "Add one specific statistic, benchmark, or case reference"
```

---

### 26.3.3 `technical_documentation`

```yaml
tone: analytical
register: C1
writer_angles:
  W-A: "All components, edge cases, and configurations covered; tables/pseudocode where applicable"
  W-B: "Specs→implementation→trade-offs logical flow; zero ambiguity in behavior description"
  W-C: "Concrete examples with specific metrics; no 'fast' without benchmark; accessible to adjacent-domain engineer"
rules:
  L1:
    - id: L1-TECH-001
      category: lexical
      message: "Vague ease qualifier"
      fix_hint: "Remove 'simply/just/easily' or specify exact steps required"
      regex_pattern: "(?i)\\b(simply|just|easily|trivially|obviously)\\s+(run|add|configure|set|call|use|implement)\\b"
    - id: L1-TECH-002
      category: lexical
      message: "Performance claim without metric"
      fix_hint: "Specify: latency (ms/s), throughput (req/s), memory (MB), or CPU (%)"
      regex_pattern: "(?i)\\b(fast(er)?|slow(er)?|efficient(ly)?|performant|scalable)\\b(?!.*\\b(ms|seconds?|req\\/s|MB|GB|%))"
    - id: L1-TECH-003
      category: structural
      message: "TBD or undefined placeholder"
      fix_hint: "Specify the value, range, or decision criteria; TBD blocks coding agents"
      regex_pattern: "(?i)\\b(TBD|TODO|FIXME|to be determined|to be defined|placeholder)\\b"
  L2:
    - id: L2-TECH-001
      category: structural
      enforcement: REQUIRE
      message: "Command/API call lacks expected output example"
      fix_hint: "Add expected output or return value after every non-trivial command block"
    - id: L2-TECH-002
      category: structural
      enforcement: REQUIRE
      message: "Code block missing language specifier"
      fix_hint: "Add language tag: ```python, ```bash, ```yaml, ```sql"
  L3:
    - id: L3-TECH-001
      category: structural
      enforcement: GUIDE
      message: "Prerequisites not stated at section start"
      fix_hint: "Add 'Prerequisites:' list before first instruction"
```

---

### 26.3.4 `journalistic`

```yaml
tone: authoritative
register: B2
writer_angles:
  W-A: "Inverted pyramid; all angles of topic covered including dissenting voices"
  W-B: "Clear central thesis; linear argumentation; conclusion doesn't repeat lede"
  W-C: "Strong lede first paragraph; active voice; varied sentence rhythm"
rules:
  L1:
    - id: L1-JOUR-001
      category: structural
      message: "Dictionary-definition lede"
      fix_hint: "Open with news peg: event, data, quote, or anecdote"
      regex_pattern: "(?i)^[^\\n]{0,60}(is (defined as|a type of|the process of))"
    - id: L1-JOUR-002
      category: lexical
      message: "Temporal vagueness without date"
      fix_hint: "Replace 'recently/last year/soon' with specific date or period"
      regex_pattern: "(?i)\\b(recently|last (year|month|week)|soon|in (recent|coming) (years|months))\\b"
    - id: L1-JOUR-003
      category: citation
      message: "Anonymous source without attribution qualifier"
      fix_hint: "Add attribution: 'according to [source type]' or 'documents reviewed by [outlet]'"
      regex_pattern: "(?i)\\bsources? (say|said|told|report|confirmed)\\b(?!.*\\b(according to|cited|named|identified)\\b)"
  L2:
    - id: L2-JOUR-001
      category: citation
      enforcement: REQUIRE
      message: "Unverified assertion without source attribution"
      fix_hint: "Add 'according to [named source]' or citation; if unverifiable, prefix 'allegedly'"
  L3:
    - id: L3-JOUR-001
      category: structural
      enforcement: GUIDE
      message: "Section exceeds 400 words without subhead or quote break"
      fix_hint: "Insert subhead or pull-quote to aid navigation"
```

---

### 26.3.5 `narrative_essay`

```yaml
tone: semi-formal
register: C1
writer_angles:
  W-A: "All thematic angles covered; concrete opening element (scene/object/data point)"
  W-B: "Clear thesis threading through sections; argument arc with genuine conclusion"
  W-C: "Rhythmic sentence variation; no mechanical connectives; prose cohesion"
rules:
  L1:
    - id: L1-NARR-001
      category: structural
      message: "Meta-reference to essay structure"
      fix_hint: "Remove; let structure emerge from prose flow"
      regex_pattern: "(?i)\\b(in (this|the following) (essay|section|part)|as (I|we) (will|have) (argue|show|demonstrate))\\b"
    - id: L1-NARR-002
      category: lexical
      message: "Mechanical transition connector"
      fix_hint: "Replace with thematic bridge sentence or remove"
      regex_pattern: "(?i)^(Furthermore,|Moreover,|Additionally,|In addition,|Lastly,|Firstly,|Secondly,|Thirdly,)\\s"
  L2:
    - id: L2-NARR-001
      category: structural
      enforcement: REQUIRE
      message: "Section opens with abstract statement not grounded in concrete detail"
      fix_hint: "Open section with specific: person, place, event, or data point"
  L3:
    - id: L3-NARR-001
      category: rhetoric
      enforcement: GUIDE
      message: "Three consecutive sentences with identical syntactic structure"
      fix_hint: "Vary: sentence length, subject position, or clause order"
```

---

### 26.3.6 `ai_instructions`

Optimized for AI coding agent as reader. Clarity is the primary aesthetic value.

```yaml
tone: analytical
register: C1
writer_angles:
  W-A: "All behaviors, inputs, outputs, and edge cases specified; no implicit assumptions"
  W-B: "Every constraint has explicit consequence; every rule has enforcement mechanism"
  W-C: "Machine-parseable structure; lists and tables preferred over prose for reference content"
rules:
  L1:
    - id: L1-AIINS-001
      category: lexical
      message: "Vague conditionality without trigger specification"
      fix_hint: "Specify exact condition: replace 'if necessary/appropriate/needed' with boolean trigger"
      regex_pattern: "(?i)\\b(if (necessary|appropriate|needed|applicable)|when (relevant|suitable))\\b"
    - id: L1-AIINS-002
      category: lexical
      message: "Best practice without enumeration"
      fix_hint: "List the specific practices; 'best practices' alone is non-actionable"
      regex_pattern: "(?i)\\bbest (practices?|approaches?|methods?)\\b(?![:\\n])"
    - id: L1-AIINS-003
      category: structural
      message: "TBD / undefined placeholder blocks agent implementation"
      fix_hint: "Specify value, range, enum, or decision criteria"
      regex_pattern: "(?i)\\b(TBD|to be (defined|determined|decided)|\\[PLACEHOLDER\\])\\b"
    - id: L1-AIINS-004
      category: lexical
      message: "Ambiguous comparison without reference"
      fix_hint: "Specify: 'similar to X' → write the pattern explicitly"
      regex_pattern: "(?i)\\b(similar to|like|analogous to)\\s+\\w+\\b(?!.*:)"
  L2:
    - id: L2-AIINS-001
      category: rhetoric
      enforcement: REQUIRE
      message: "Behavior described without concrete example"
      fix_hint: "Add INPUT→OUTPUT example or code block for every non-trivial behavior"
    - id: L2-AIINS-002
      category: structural
      enforcement: REQUIRE
      message: "Constraint stated without consequence for violation"
      fix_hint: "Add: 'Violation causes: [specific outcome]'"
  L3:
    - id: L3-AIINS-001
      category: structural
      enforcement: GUIDE
      message: "Prose paragraph where table would improve scannability"
      fix_hint: "Convert to table if 3+ items share same attributes"
```

---

### 26.3.7 `blog`

```yaml
tone: conversational
register: B2
writer_angles:
  W-A: "Strong lede; all topic angles relevant to target audience; frequent subheads"
  W-B: "Clear central thesis; linear argument; conclusion advances (not repeats) intro"
  W-C: "Conversational rhythm; sentence variety; natural inline links; engagement over formality"
rules:
  L1:
    - id: L1-BLOG-001
      category: register
      message: "Academic passive construction in blog context"
      fix_hint: "Convert to active voice with human subject"
      regex_pattern: "(?i)\\b(it (has been|was|is) (shown|demonstrated|established|noted) that|it (can|may|should) be (argued|noted|observed))\\b"
    - id: L1-BLOG-002
      category: structural
      message: "Paragraph block exceeds 100 words (blog readers scan)"
      fix_hint: "Split at natural pause; max 3–4 sentences per paragraph"
      regex_pattern: None  # word-count check, not regex
  L2:
    - id: L2-BLOG-001
      category: structural
      enforcement: REQUIRE
      message: "No subheading within 600 words of body text"
      fix_hint: "Insert H2/H3 subheading to aid scanning"
  L3:
    - id: L3-BLOG-001
      category: rhetoric
      enforcement: GUIDE
      message: "Three consecutive passive sentences"
      fix_hint: "Introduce at least one active-voice sentence to vary rhythm"
```

---

## 26.4 W-A/B/C Angle Reference Table

Full cross-profile summary. See individual profile sections for narrative detail.

| Profile | W-A (Coverage, temp=0.30) | W-B (Argumentation, temp=0.60) | W-C (Readability, temp=0.80) |
|---------|--------------------------|-------------------------------|------------------------------|
| scientific_report | All literature; all sub-aspects | Hypothesis chain; cautious hedging | Academic prose; syntactic variety |
| business_report | All data + operational implications | Problem→evidence→recommendation | Short sentences/paragraphs; no jargon |
| technical_documentation | All components, edge cases, configs | Specs→implementation→trade-offs; zero ambiguity | Concrete metrics; adjacent-domain readable |
| journalistic | All angles including dissent | Inverted pyramid; linear thesis | Strong lede; active voice; rhythm |
| narrative_essay | All themes; concrete opener | Clear arc; genuine conclusion | Rhythmic variety; no mechanical connectors |
| ai_instructions | All behaviors, inputs, outputs | Every constraint has consequence | Machine-parseable; tables/lists preferred |
| blog | All audience-relevant angles; subheads | Clear thesis; conclusion advances | Conversational; scannable; inline links |

---

## 26.5 Customization Modes

### Mode 1: Natural Language

```python
class NLCustomizationRequest:
    free_text: str          # user description of style requirements
    max_refinement_cycles: int = 2

class NLCustomizationResult:
    generated_rules: list[StyleRule]
    yaml_preview: str       # shown to user for confirmation
    unresolvable_intents: list[str]  # intents that couldn't be converted to rules
```

Conversion agent: `google/gemini-2.5-flash`. If intent ambiguous after 2 cycles → prompt user for Mode 2.

### Mode 2: Guided Form

```python
class FormRule:
    rule_type: Literal["forbidden_pattern", "required_element", "register_constraint"]
    condition: str          # plain language: "whenever I use bullets in body text"
    message: str            # violation message
    fix_hint: str
    auto_generate_regex: bool = True
```

### Mode 3: YAML Direct

User submits raw `StyleRule` YAML. Pydantic validation enforced. Invalid `regex_pattern` fails fast with `re.compile()` test.

```python
class PresetMetadata:
    name: str
    description: str
    visibility: Literal["private", "team", "public"]
    base_profile: ProfileName
    extra_rules: list[StyleRule]
    disabled_rule_ids: list[str]
```

Saved to `style_presets` table (see §21.1). Loaded by name in YAML config `style_profiles.preset_id`.

---

## 26.6 Internationalization

### Language-Specific Model Selection for Jury S

```python
STYLE_JURY_BY_LANGUAGE: dict[str, list[str]] = {
    "en": ["openai/gpt-4.5", "mistral/mistral-large-2411", "meta/llama-3.3-70b-instruct"],
    "it": ["mistral/mistral-large-2411", "openai/gpt-4.5", "google/gemini-2.5-pro"],
    "de": ["mistral/mistral-large-2411", "openai/gpt-4.5", "google/gemini-2.5-pro"],
    "fr": ["mistral/mistral-large-2411", "openai/gpt-4.5", "meta/llama-3.3-70b-instruct"],
    "zh": ["qwen/qwen3-14b", "openai/gpt-4.5", "google/gemini-2.5-pro"],
    "es": ["openai/gpt-4.5", "mistral/mistral-large-2411", "meta/llama-3.3-70b-instruct"],
}
```

Default fallback for unlisted languages: `["openai/gpt-4.5", "google/gemini-2.5-pro", "mistral/mistral-large-2411"]`.

### Cross-Lingual Citation Handling

```python
class CrossLingualCitationPolicy:
    document_language: str
    source_language: str
    # When source_language != document_language:
    cite_original_title: bool = True       # always cite original title
    add_translated_title: bool = True      # append [Title in target_lang] in brackets
    translate_for_verification_only: bool = True  # translation never quoted as source
    min_abstract_language: str = "en"     # fallback for abstract comprehension
```

Forbidden: citing machine-translated text as if it were the original source. Writer prompt includes explicit instruction.

### Locale-Aware Forbidden Patterns

```python
LOCALE_FORBIDDEN_OVERRIDES: dict[str, list[StyleRule]] = {
    "it": [
        StyleRule(
            id="L1-IT-001", level="L1", category="ai_fingerprint",
            enforcement="BLOCK",
            message="Italian AI fingerprint phrase",
            fix_hint="Reformulate: avoid formulaic connectors typical of Italian LLM output",
            regex_pattern=r"(?i)\b(vale la pena notare|come (già |)menzionato|è importante sottolineare)\b"
        )
    ],
    "de": [
        StyleRule(
            id="L1-DE-001", level="L1", category="ai_fingerprint",
            enforcement="BLOCK",
            message="German AI fingerprint phrase",
            fix_hint="Reformulate to avoid formulaic openings typical in German LLM output",
            regex_pattern=r"(?i)\b(es ist (wichtig|erwähnenswert)|wie (oben |)erwähnt|abschließend lässt sich sagen)\b"
        )
    ],
}
```

Applied additionally to universal rules when `output_language` matches key.

---

## 26.7 Style Linter Agent

```
AGENT: StyleLinter [§26]
RESPONSIBILITY: Detect L1/L2 violations in draft before jury activation
MODEL: deterministic (regex + word-count; no LLM call)
TEMP: N/A / MAX_TOKENS: N/A
INPUT:
  draft: str
  profile: ProfileName
  language: str
  active_rule_ids: list[str]  # from frozen ruleset (§3B.3)
OUTPUT: StyleLintResult
CONSTRAINTS:
  MUST run before any jury call
  MUST return empty violations list for pipeline to proceed to jury
  NEVER call LLM; NEVER modify draft
  ALWAYS include char_offset for every L1 violation
  MUST apply universal rules (§26.2) + profile rules + locale overrides (§26.6)
ERROR_HANDLING:
  regex_compile_error -> skip rule, log warning, continue (rule treated as L3)
  draft_empty -> return single violation L1-EMPTY-001
CONSUMES: [current_draft, style_profile, language, active_rule_ids] from DocumentState
PRODUCES: [style_lint_result] -> DocumentState
```

```python
class StyleViolation:
    rule_id: str
    level: EnforcementLevel
    char_offset: int
    matched_text: str
    message: str
    fix_hint: str

class StyleLintResult:
    violations: list[StyleViolation]
    l1_count: int
    l2_count: int
    passed: bool  # True iff l1_count == 0 and l2_count == 0
```

---

## 26.8 Style Fixer Agent

```
AGENT: StyleFixer [§26]
RESPONSIBILITY: Correct L1/L2 violations without altering factual content
MODEL: anthropic/claude-sonnet-4 / TEMP: 0.2 / MAX_TOKENS: 4096
INPUT:
  draft: str
  violations: list[StyleViolation]
  style_exemplar: str        # from §3B.2
  profile: ProfileName
OUTPUT: str  # corrected draft
CONSTRAINTS:
  MUST NOT alter: facts, numbers, citations, named entities, argument order
  MUST fix every L1 violation listed
  MUST NOT introduce new L1 violations
  NEVER rewrite sections not flagged in violations
  ALWAYS flag in output JSON if violation is "uncorrectable without content change"
  MAX 2 invocations per section per iteration
ERROR_HANDLING:
  uncorrectable_violation -> mark field uncorrectable:true, preserve original span, log
  max_invocations_exceeded -> escalate to Writer with violation list
CONSUMES: [current_draft, style_lint_result, style_exemplar, style_profile] from DocumentState
PRODUCES: [current_draft] -> DocumentState
```

---

## 26.9 Ruleset Lifecycle

**Freeze point**: ruleset frozen at Style Calibration Gate approval (§3B.3).

| Operation | Permitted during run? |
|-----------|----------------------|
| Add new L1/L2 rule for future sections | YES |
| Remove active rule | NO |
| Modify existing rule regex | NO |
| Add new L3 guide | YES |
| Override specific section | NO (requires human escalation) |

Frozen ruleset stored in `DocumentState.style_profile.active_rule_ids` (list of rule IDs). Any YAML config change outside these operations requires new run.

---

## 26.10 YAML Config Reference for Style Profiles

```yaml
style_profiles:
  active: "scientific_report"           # ProfileName
  preset_id: null                       # optional saved preset name
  extra_forbidden:                      # additional L1 rules appended
    - id: "L1-CUST-001"
      level: "L1"
      category: "lexical"
      enforcement: "BLOCK"
      message: "Domain-specific forbidden term"
      fix_hint: "Use approved terminology from glossary"
      regex_pattern: "(?i)\\bfoo_term\\b"
  extra_required: []                    # additional L2 rules
  disabled_rule_ids: []                 # disable specific rule IDs (L3 only; L1/L2 cannot be disabled)
  style_calibration_gate:
    enabled: true
    max_attempts: 3
```

`disabled_rule_ids` accepts only L3 rule IDs. Attempting to disable L1/L2 raises `Pydantic ValidationError` at pre-flight (§4.1).

<!-- SPEC_COMPLETE -->