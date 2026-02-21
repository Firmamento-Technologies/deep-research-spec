# 06_run_companion.md
## §6 — Run Companion

---

### §6.1 Role Definition

RunCompanion is a **read-only observer + bounded modifier** of the active run. It is NOT:
- An orchestrator node in the LangGraph graph
- A member of the production loop (Researcher, Writer, Jury, Reflector)
- A decision-maker for section approval

It IS:
- A conversational interface always active during a run
- A supervised modifier for a constrained set of state fields
- A proactive notifier for conditions the user did not explicitly query

**Research basis**: SupervisorAgent pattern (arXiv 2025) — anticipating inefficiencies before propagation reduces total token consumption by 29.68%.

---

### §6.2 Readable State Fields

```python
# Fields RunCompanion can READ from DRSState (see §4.6)
COMPANION_READABLE: dict[str, str] = {
    # Field name : accessible_since (phase)
    "outline"                    : "phase_A_complete",
    "approved_sections"          : "first_section_approved",
    "current_section_idx"        : "phase_B_start",
    "sections[*].current_draft"  : "writer_first_output",
    "sections[*].css_history"    : "first_jury_verdict",
    "sections[*].iteration"      : "phase_B_start",
    "sections[*].last_verdicts"  : "first_jury_verdict",
    "sections[*].last_reflector_output": "first_reflector_run",
    "sections[*].scope_reflector": "first_reflector_run",
    "cost_accumulated_usd"       : "phase_B_start",
    "cost_per_section"           : "first_section_approved",
    "max_budget_usd"             : "phase_A_start",
    "style_preset"               : "phase_A_start",
    "quality_preset"             : "phase_A_start",
    "active_escalation"          : "when_set",
    "writer_memory"              : "second_section_start",
    "circuit_breaker_states"     : "phase_B_start",
    "run_metrics"                : "phase_B_start",
}

# Fields RunCompanion can NEVER access
COMPANION_FORBIDDEN: list[str] = [
    "agent_internal_prompts",   # prompt text of other agents
    "other_run_states",         # cross-run isolation
    "pii_mapping_table",        # security boundary
    "api_keys",
]
```

---

### §6.3 Four Response Types

```python
ResponseType = Literal["STATUS", "PREDICTIVE", "MODIFICATION", "PROACTIVE"]
```

| Type | Trigger | Dialogue Example |
|------|---------|-----------------|
| `STATUS` | User asks factual question about current run | **User**: "Why is section 3 on iteration 4?" **RC**: "Section 3 failed CSS_content 3× (scores: 0.41, 0.44, 0.43). Judge F flagged the same missing\_evidence gap each time: no peer-reviewed source for the 2023 mortality claim. Current iteration triggered a targeted Researcher re-run. Cost so far on this section: $4.12." |
| `PREDICTIVE` | User asks what-if or requests advice | **User**: "Should I switch to Economy preset now?" **RC**: "At current pace (2.3 iter/section avg, 4 sections remaining), projected total is $38.20 against your $50 cap. Economy would reduce CSS threshold to 0.65 and jury to 1/3 — approval would be faster but Section 5 (Methodology) has complex causal claims that have triggered Judge R vetoes before. Recommendation: keep Balanced, monitor at section 6. If you switch Economy now, estimated saving: $8, estimated quality drop on CSS_content: ~0.10." |
| `MODIFICATION` | User requests a state change | **User**: "Add 'it has been observed that' to forbidden patterns." **RC**: "Done. Rule added as L1 FORBIDDEN (id: user\_rc\_001). Applies from section 4 onward. Style Linter will block any occurrence before Jury." *(direct, no confirmation)* |
| `PROACTIVE` | System condition matches trigger table (§6.5) | **RC** (unsolicited): "⚠ Budget at 63% with 5 of 8 sections remaining. Projected total: $52.40 — 4.8% over cap. Options: (A) switch Section 6–8 to Economy preset (save ~$9), (B) raise cap to $55, (C) continue and I'll alert again at 80%." |

---

### §6.4 Modification Authorization

```python
DirectModification = Literal[
    "add_forbidden_pattern",         # L1/L2/L3 rule addition
    "adjust_css_threshold",          # ±0.10 max per request, range [0.40, 0.95]
    "add_uploaded_source",           # new source mid-run
    "add_run_report_note",           # annotation in audit trail
    "add_source_blacklist_entry",    # domain/URL blacklisted for remaining sections
]

ConfirmRequired = Literal[
    "change_quality_preset",         # Economy/Balanced/Premium switch
    "modify_section_scope",          # changes Researcher query + outline
    "unlock_approved_section",       # breaks immutability guarantee
    "modify_jury_weights",           # reasoning/factual/style weights
    "modify_max_iterations",         # convergence parameter
    "interrupt_run",                 # abort with partial output
]
```

**Confirmation protocol for `ConfirmRequired`**:
1. RC presents: action, consequence, estimated cost delta, reversibility
2. User must respond with exact phrase `"confirm"` or `"cancel"`
3. Timeout 300s → auto-cancel with log entry
4. All confirmed modifications logged to `companion_messages` with `{timestamp, action, parameters, user_confirmation_text}`

**Hard limits on `adjust_css_threshold`**:
- Single request delta: max ±0.10
- Cumulative delta cap: max ±0.20 **per `run_id`** (not per conversation thread — a new conversation within the same run does NOT reset this cap; the cap resets only when a new run is created with a new `run_id`)
- Absolute floor: 0.40 / ceiling: 0.95
- The cumulative delta is tracked in `DocumentState` field `css_threshold_cumulative_delta: float` (initialized to `0.0` at run creation, persisted in PostgreSQL alongside the run, never reset mid-run)
- Enforcement: before applying any `adjust_css_threshold` request, RC reads `css_threshold_cumulative_delta` from `DocumentState` and verifies that `abs(css_threshold_cumulative_delta + requested_delta) <= 0.20`; if the check fails, RC refuses the full request with an explanation — no partial application
- On successful application: `css_threshold_cumulative_delta` is updated atomically with the new `css_threshold` value in a single `DocumentState` write
- Violations → RC refuses with explanation, no partial application

---

### §6.5 Proactive Trigger Table

```python
class ProactiveTrigger(TypedDict):
    trigger_id: str
    condition: str                  # evaluated against DRSState
    threshold: float | int | str
    message_template: str
    cooldown_seconds: int           # min interval between same trigger firing
    priority: Literal["INFO", "WARN", "CRITICAL"]
```

| trigger_id | Condition | Threshold | Message Template | Cooldown | Priority |
|-----------|-----------|-----------|-----------------|----------|----------|
| `budget_midpoint_over` | `cost_accumulated_usd / max_budget_usd > T AND current_section_idx > total_sections * 0.5` | 0.60 | "Budget at {pct}% with {remaining} sections left. Projected: ${projected}. Options: [A] Economy preset [B] raise cap [C] continue." | 1800s | `WARN` |
| `css_low_post_approval` | `approved_sections[-1].css_final < T` | 0.70 | "Section {n} approved with CSS {css} — below comfortable threshold. Judge motivations: {summary}. Consider reviewing before document assembly." | 0s | `INFO` |
| `source_concentration` | `same_publisher_count_last_3_sections >= T` | 3 | "Same publisher '{publisher}' used in last {n} sections. Source Diversity Analyzer flagged concentration. Add blacklist entry?" | 0s | `INFO` |
| `judge_f_external_contradiction` | `last_verdicts.judge_f.external_sources_consulted != [] AND last_verdicts.judge_f.verdict == "FAIL"` | n/a | "Judge F found external evidence contradicting a claim in section {n}: '{claim}'. Source: {url}. This may require Researcher re-run." | 0s | `WARN` |
| `style_drift_detected` | `style_drift_index > T` | 0.05 | "Style drift detected between sections {a} and {b} (index: {val}). Writer Memory has been updated. If drift continues, consider unlocking section {a} for Style Fixer." | 3600s | `WARN` |
| `oscillation_early_warning` | `css_variance_last_3_iter < T AND iteration >= 3` | 0.03 | "Section {n} CSS has not improved in 3 iterations (scores: {history}). Oscillation likely in next 1–2 iterations. Preemptive options: [A] add Writer instructions now [B] wait for escalation." | 0s | `WARN` |
| `rogue_judge_detected` | `rogue_judge_disagreement_rate > T` | 0.70 | "Judge {slot}/{model} has disagreed with other judges on {n} consecutive sections. Possible prompt drift. Recommend reviewing Judge {slot} verdicts." | 0s | `CRITICAL` |

---

### §6.6 Agent Specification

```
AGENT: RunCompanion [§6]
RESPONSIBILITY: provide conversational state visibility and bounded state modifications during active run
MODEL: google/gemini-2.5-pro / TEMP: 0.20 / MAX_TOKENS: 1024
FALLBACK_MODEL: anthropic/claude-sonnet-4
INPUT:
  user_message: str
  companion_messages: list[dict]      # full conversation history
  state_snapshot: dict                # see §6.2 COMPANION_READABLE fields only
OUTPUT: CompanionResponse
CONSTRAINTS:
  MUST respond within 3000ms (p95)
  MUST refuse any read request for COMPANION_FORBIDDEN fields
  MUST apply DirectModification atomically or not at all
  MUST require explicit "confirm" string for ConfirmRequired actions
  MUST include modification reference in companion_messages with ISO timestamp
  NEVER invent state values not present in state_snapshot
  NEVER initiate actions in the production graph (no direct node calls)
  NEVER apply css_threshold delta exceeding ±0.10 per request
  NEVER apply css_threshold delta that would cause abs(css_threshold_cumulative_delta + requested_delta) > 0.20 (enforced per run_id, not per conversation thread)
  ALWAYS surface trade-offs (cost delta, quality delta) before ConfirmRequired
ERROR_HANDLING:
  state_snapshot_unavailable -> return cached snapshot (max 30s stale) -> "State temporarily unavailable, showing last known values"
  model_timeout (>3000ms) -> retry once with fallback_model -> "Response delayed, retrying"
  modification_parse_error -> refuse modification, explain required format -> no partial application
  confirmation_timeout (>300s) -> auto-cancel, log "COMPANION_CONFIRM_TIMEOUT"
CONSUMES:
  [companion_messages, cost_accumulated_usd, max_budget_usd, approved_sections,
   current_section_idx, sections[*].css_history, sections[*].last_verdicts,
   sections[*].iteration, active_escalation, style_preset, quality_preset,
   writer_memory, circuit_breaker_states, run_metrics, outline,
   css_threshold_cumulative_delta]
PRODUCES:
  [companion_messages] -> DRSState
  [style_preset.extra_forbidden] -> DRSState  (add_forbidden_pattern)
  [css_threshold, css_threshold_cumulative_delta] -> DRSState  (adjust_css_threshold, direct)
  [source_blacklist] -> DRSState              (add_source_blacklist_entry)
  [run_report_notes] -> DRSState              (add_run_report_note)
```

---

### §6.6.1 Conversation Persistence Schema

```python
class CompanionMessage(TypedDict):
    msg_id: str                              # uuid4
    timestamp: str                           # ISO 8601
    role: Literal["user", "companion", "system"]
    content: str
    response_type: ResponseType | None       # None for user messages
    section_ref: int | None                  # section_idx if message relates to specific section
    iteration_ref: int | None
    modification_applied: CompanionModification | None

class CompanionModification(TypedDict):
    action: DirectModification | ConfirmRequired
    parameters: dict[str, Any]
    confirmation_received: bool
    confirmation_timestamp: str | None       # ISO 8601
    state_fields_changed: list[str]          # actual fields mutated in DRSState
    cost_delta_usd: float | None             # estimated impact

class CompanionResponse(TypedDict):
    content: str
    response_type: ResponseType
    modification: CompanionModification | None
    proactive_trigger_id: str | None         # set if PROACTIVE type
    state_snapshot_timestamp: str            # ISO 8601 of snapshot used
```

**DocumentState fields added by §6.4**:
```python
# Added to DRSState (see §4.6) to enforce per-run_id cumulative delta cap
css_threshold_cumulative_delta: float   # initialized to 0.0 at run creation;
                                        # incremented/decremented on every successful
                                        # adjust_css_threshold DirectModification;
                                        # persisted in PostgreSQL with the run row;
                                        # reset to 0.0 only when a new run_id is created
```

**Persistence**: `companion_messages: Annotated[list[CompanionMessage], add_messages]` in DRSState (see §4.6). Written to PostgreSQL table `companion_messages` after every exchange. Included verbatim in Run Report (§30.4) as `conversation_audit_trail`.

**Session continuity**: on run resume after crash (§21.2), full `companion_messages` history reloaded — RC has complete context of prior conversation without re-summarization. The `css_threshold_cumulative_delta` value is also restored from the PostgreSQL checkpoint, preserving the cumulative cap across crashes and resumptions within the same `run_id`.

<!-- SPEC_COMPLETE -->