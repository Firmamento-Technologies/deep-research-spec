# 03b_style_calibration.md
## §3B — Style Calibration Gate

---

## §3B.0 Flow Diagram

```
[User selects preset] ──► [Show rules in natural language]
         │
         ▼
[User confirms / edits rules]
         │
         ▼
[Writer produces 250-word sample] ──► attempt_count += 1
         │
         ▼
[StyleCalibrationJury evaluates sample] ──► CSS_style score
         │
         ▼
[UI: show sample + CSS_style]
         │
    ┌────┴────────────────────────────────┐
    ▼                                     ▼
[APPROVE]                    [FEEDBACK / REGENERATE]
    │                                     │
    ▼                              attempt_count ≥ 3?
[Freeze ruleset]                  ┌──────┴──────┐
[Save StyleExemplar]              ▼             ▼
[Inject into Writer context]   [retry]   [Suggest preset change]
    │                                     (block progression)
    ▼
[Proceed to Phase A]
```

---

## §3B.1 StyleCalibrationGate Agent

```
AGENT: StyleCalibrationGate [§3B]
RESPONSIBILITY: produce and approve a style sample before Phase A begins
MODEL: anthropic/claude-opus-4-5 / TEMP: 0.5 / MAX_TOKENS: 600
INPUT:
  topic: str
  style_preset: StylePreset          # see §26
  style_profile_name: str
  attempt_count: int                 # 0-indexed, max 3
  user_feedback: str | None          # present on regenerate
OUTPUT: StyleCalibrationResult
CONSTRAINTS:
  MUST produce exactly 250 ± 25 words
  MUST use the actual topic (not placeholder text)
  MUST apply all active L1/L2 rules from style_preset
  NEVER reference the document structure or section titles
  ALWAYS inject user_feedback into prompt when attempt_count > 0
ERROR_HANDLING:
  parse_error -> retry once with simplified prompt -> fallback: mark attempt as FAILED, increment count
  model_unavailable -> fallback chain [claude-sonnet-4, gpt-4.5] -> if all fail: skip gate, log WARNING
CONSUMES: [style_preset, topic, attempt_count, user_feedback] from DocumentState
PRODUCES: [style_calibration_result] -> DocumentState
```

```python
class StyleCalibrationResult(TypedDict):
    sample_text: str
    attempt_count: int
    css_style: float                 # 0.0–1.0, from StyleCalibrationJury
    status: Literal["pending_approval", "approved", "failed_max_attempts"]
    user_feedback: str | None
```

---

## §3B.2 StyleCalibrationJury — Lightweight Evaluation Path

The Style Calibration Gate operates **before Phase A begins**. At this point, `DocumentState` does not yet contain `current_draft`, `citation_map`, `verified_sources`, or `section_idx`. The production Mini-Jury S (§8.3) requires these fields and **cannot be invoked during calibration**.

Therefore, a distinct `StyleCalibrationJury` is defined as a separate, lightweight evaluation path that operates exclusively on `(sample_text, style_profile, style_exemplar_candidate)` without any document-state dependencies.

```
AGENT: StyleCalibrationJury [§3B.2]
RESPONSIBILITY: evaluate the 250-word calibration sample for style conformance only
                — no citation checking, no section coherence, no document context required
EVALUATION PATH: SEPARATE from production Mini-Jury S (§8.3)
                 Do NOT invoke Mini-Jury S here under any circumstances
MODEL SLOTS (3 judges, same family as production Mini-Jury S):
  SCJ-1: openai/gpt-4.5
  SCJ-2: mistral/mistral-large-2411
  SCJ-3: meta/llama-3.3-70b-instruct
TEMP: 0.2 / MAX_TOKENS: 300 per judge
INPUT (all three fields required; no others accepted):
  sample_text: str                   # the 250-word sample to evaluate
  style_profile: StylePreset         # L1/L2/L3 rules from the active preset (§26)
  style_exemplar_candidate: str | None  # None on attempt 1; previous approved sample if retrying
OUTPUT per judge:
  pass_fail: bool
  dimension_scores:
    forbidden_pattern_compliance: float   # 0.0–1.0 (L1 rules)
    required_element_presence: float      # 0.0–1.0 (L2 rules)
    register_and_tone: float              # 0.0–1.0 (L3 guide)
    syntactic_variety: float              # 0.0–1.0
  comments: str
AGGREGATION:
  CSS_style = pass_count / 3            # simple ratio over 3 judges
  range: 0.0–1.0
  approval: USER-DRIVEN (CSS_style is informational only; does not gate approval)
CONSTRAINTS:
  MUST NOT access DocumentState fields: current_draft, citation_map,
    verified_sources, section_idx, approved_sections, or any outline data
  MUST NOT perform citation verification or factual checking
  MUST evaluate style conformance only
  Three judges run in parallel (asyncio.gather)
ERROR_HANDLING:
  single judge failure -> CSS_style computed over available judges (min 2/3)
                          with JURY_DEGRADED flag in StyleCalibrationResult
  all judges fail      -> css_style = None, status = "failed_max_attempts",
                          log WARNING, skip gate
```

### Distinction from Production Mini-Jury S (§8.3)

| Dimension | StyleCalibrationJury (§3B.2) | Production Mini-Jury S (§8.3) |
|---|---|---|
| Invocation phase | Pre-Phase A (calibration only) | Phase B (section loop) |
| Required DocumentState fields | `sample_text`, `style_profile`, `style_exemplar_candidate` | `current_draft`, `citation_map`, `verified_sources`, `section_idx` |
| Citation checking | ❌ Never | ✅ Yes |
| Section coherence | ❌ Never | ✅ Yes |
| CSS feeds css_history | ❌ No | ✅ Yes |
| Approval mechanism | User-driven | Threshold-gated (CSS_style ≥ 0.80, §9.3) |

---

## §3B.3 StyleExemplar Schema

```python
class StyleExemplar(TypedDict):
    text: str                        # approved 250-word sample verbatim
    approved_at_attempt: int         # which attempt (1–3) was approved
    css_style_at_approval: float     # CSS_style score at approval moment
    profile_name: str                # e.g. "academic", "business"
    frozen_ruleset_version: str      # hash of frozen ruleset (see §3B.4)
```

**Injection mechanism**: `StyleExemplar.text` is injected into every Writer call (§5.7) as a dedicated context block:

```
<style_exemplar>
The following is an approved writing sample that establishes tone, rhythm,
and register for this document. Use it as a reference — not a template.
Do not copy sentences. Match its syntactic density and formality level.

{StyleExemplar.text}
</style_exemplar>
```

Placed after system identity, before fonti. Never truncated by Context Compressor (§14).

---

## §3B.4 Frozen Ruleset Mechanism

**What freezes**: at approval moment, the following fields from `StylePreset` are snapshot into `FrozenRuleset`:

```python
class FrozenRuleset(TypedDict):
    snapshot_hash: str               # sha256 of serialized ruleset
    frozen_at: str                   # ISO timestamp
    profile_name: str
    l1_forbidden: list[RuleEntry]    # see §26.1
    l2_required: list[RuleEntry]
    l3_guide: list[RuleEntry]
    forbidden_patterns_universal: list[str]   # see §26.9
    language: str
```

**When freezes**: immediately after `status == "approved"` is set in `StyleCalibrationResult`. Stored in `DocumentState.frozen_ruleset`.

**Immutability**: `FrozenRuleset` fields `l1_forbidden`, `l2_required`, `l3_guide` are read-only for the remainder of the run. No removal, no modification of active rules.

**Only exception**: new entries MAY be appended to `l1_forbidden` for future sections only. Conditions:
- Source: Run Companion (§6.4) direct modification, or user via UI escalation (§32.4)
- Appended entry must have `applies_from_section: int` set to current_section_idx + 1
- Already-approved sections are never re-evaluated against new entries

---

## §3B.5 UI Text — Exact Strings

### Approval screen header
```
"Review your writing sample"
```

### Approve button
```
"Approve and lock style"
```

### Feedback button
```
"Give feedback and regenerate"
```

### Regenerate button (after feedback submitted)
```
"Regenerate sample"
```

### Attempt counter display
```
"Attempt {n} of 3"
```

### Max attempts reached — preset change suggestion
```
"We couldn't reach an approved style after 3 attempts.
This may mean the current preset doesn't match your expectations.
Consider switching to a different profile before continuing.
You can also skip style calibration and proceed with preset defaults."
```

Actions rendered on max-attempts screen:
- `"Change preset"` → routes back to §3B.5 wizard step 1
- `"Skip and use defaults"` → bypasses gate, sets `style_exemplar = None`, freezes ruleset from preset as-is

### Freeze confirmation
```
"Style locked. This sample will guide the writing tone for all sections."
```

---

## §3B.6 Preset Integration Flow

```python
class StyleCalibrationConfig(TypedDict):
    enabled: bool                    # default True; False skips gate entirely
    max_attempts: int                # MUST be 3, not configurable per §3B.1
    css_style_display: bool          # show numeric score to user (default True)
    preset_name: str
    allow_rule_editing: bool         # True = user may edit L3 guide rules before sample
```

**Wizard sequence** (maps to §32.1):
1. User selects `preset_name` → system renders L1/L2/L3 rules as natural language list
2. If `allow_rule_editing=True`: user may add/remove L3 entries; L1/L2 immutable at this stage
3. User confirms → `StyleCalibrationGate` invoked → produces sample
4. `StyleCalibrationJury` evaluates (3 judges, see §3B.2); `CSS_style` computed as `pass_count / 3`
5. UI displays sample + `CSS_style` + attempt counter
6. User action: `approve` → freeze → proceed; `feedback+regenerate` → increment count → loop; max_attempts hit → preset-change screen

**CSS_style threshold for display**: shown as informational only during calibration. Approval is **user-driven**, not threshold-gated. `StyleCalibrationJury` score informs but does not block approval.

---

## §3B DocumentState Fields

```python
# Fields added to DocumentState (see §4.6) by this gate
style_exemplar: StyleExemplar | None
frozen_ruleset: FrozenRuleset | None
style_calibration_attempts: int          # 0 if gate skipped
style_calibration_skipped: bool
```

`style_exemplar` and `frozen_ruleset` are written once and never overwritten after approval. LangGraph checkpoint (§21.2) persists both immediately on write.

<!-- SPEC_COMPLETE -->