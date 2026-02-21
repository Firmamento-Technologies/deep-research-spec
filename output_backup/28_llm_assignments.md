# §28 — LLM Assignments

## §28.1 Task-Fit Principle

Model selection criterion: **task-fit over benchmark rank**. A model ranked #1 on MMLU is not automatically optimal for constrained JSON generation or adversarial critique. Each assignment below lists the decisive capability that drives the choice, not overall leaderboard position.

**Decisive capability axes:**

| Axis | Measures |
|------|----------|
| `long_context_coherence` | Quality retention across 128k+ tokens |
| `structured_output` | JSON/YAML compliance under strict schemas |
| `adversarial_reasoning` | Actively seeks flaws, resists sycophancy |
| `search_grounded` | Native web retrieval with citation attribution |
| `factual_precision` | Low hallucination rate on verifiable claims |
| `creative_diversity` | Syntactic/stylistic variation at higher temperature |
| `analytical_synthesis` | Multi-source comparison without content invention |
| `light_extraction` | Fast, cheap summarization / deterministic extraction |

---

## §28.2 Full Model Assignment Table

```python
from typing import Literal

AgentSlot = Literal[
    "planner", "researcher",
    "writer_wa", "writer_wb", "writer_wc",
    "fusor",
    "judge_r1", "judge_r2", "judge_r3",
    "judge_f1", "judge_f2", "judge_f3",
    "judge_s1", "judge_s2", "judge_s3",
    "reflector",
    "context_compressor",
    "post_draft_analyzer",
    "style_fixer",
    "span_editor",
    "run_companion",
]
```

| Agent Slot | Primary Model | Fallback 1 | Fallback 2 | Decisive Capability |
|------------|--------------|------------|------------|---------------------|
| `planner` | `google/gemini-2.5-pro` | `anthropic/claude-opus-4-5` | `openai/gpt-4.5` | `long_context_coherence` — outline must reason over full topic scope; Gemini 2.5 Pro sustains quality at 128k+ context |
| `researcher` | `perplexity/sonar-pro` | `perplexity/sonar` | `openai/gpt-4o-search-preview` | `search_grounded` — native retrieval with citation attribution; no hallucinated sources |
| `writer_wa` | `anthropic/claude-opus-4-5` | `anthropic/claude-sonnet-4` | `google/gemini-2.5-pro` | `long_context_coherence` @ temp=0.30 — Coverage angle requires exhaustive scope tracking |
| `writer_wb` | `anthropic/claude-opus-4-5` | `anthropic/claude-sonnet-4` | `google/gemini-2.5-pro` | `adversarial_reasoning` @ temp=0.60 — Argumentation angle requires logical hierarchy and causal precision |
| `writer_wc` | `anthropic/claude-opus-4-5` | `anthropic/claude-sonnet-4` | `google/gemini-2.5-pro` | `creative_diversity` @ temp=0.80 — Readability angle requires syntactic variation and narrative flow |
| `fusor` | `openai/o3` | `openai/o3-mini` | `anthropic/claude-opus-4-5` | `analytical_synthesis` — must compare 3 drafts and integrate best elements without inventing new claims |
| `judge_r1` | `deepseek/deepseek-r1` | `openai/o3-mini` | `qwen/qwq-32b` | `adversarial_reasoning` — chain-of-thought reasoning trained to find logical contradictions |
| `judge_r2` | `openai/o3-mini` | `deepseek/deepseek-r1` | `qwen/qwq-32b` | `adversarial_reasoning` — o3-mini is the designated tier2 model for the Reasoning jury (see §8.5 JURY_TIERS); consistent with cascading fallback ordering |
| `judge_r3` | `qwen/qwq-32b` | `deepseek/deepseek-r1` | `openai/o3-mini` | `adversarial_reasoning` — decorrelated training corpus from R1/o3-mini; reduces shared-bias majority error (see §10) |
| `judge_f1` | `perplexity/sonar` | `perplexity/sonar-pro` | `google/gemini-2.5-flash` | `search_grounded` + `factual_precision` — live search for claim falsification (micro-search, see §8.2.1) |
| `judge_f2` | `google/gemini-2.5-flash` | `google/gemini-2.5-pro` | `openai/gpt-4o-search-preview` | `factual_precision` — fast, low hallucination; native Google Search grounding |
| `judge_f3` | `openai/gpt-4o-search-preview` | `openai/gpt-4.5` | `perplexity/sonar` | `factual_precision` — third corpus source for epistemic decorrelation; Bing grounding distinct from Google |
| `judge_s1` | `openai/gpt-4.5` | `openai/gpt-4o` | `mistral/mistral-large-2411` | `structured_output` — style rubric scoring requires consistent JSON schema compliance |
| `judge_s2` | `mistral/mistral-large-2411` | `mistral/mistral-large` | `meta/llama-3.3-70b-instruct` | `creative_diversity` — European training data; lower sycophancy on style critique than OpenAI-family |
| `judge_s3` | `meta/llama-3.3-70b-instruct` | `meta/llama-3.1-70b-instruct` | `openai/gpt-4o` | `adversarial_reasoning` — Meta RLHF pipeline decorrelated from GPT/Mistral families |
| `reflector` | `openai/o3` | `openai/o3-mini` | `anthropic/claude-opus-4-5` | `analytical_synthesis` + `adversarial_reasoning` — must read full verdict history, identify error patterns, emit prioritized structured feedback |
| `context_compressor` | `qwen/qwen3-7b` | `meta/llama-3.3-8b-instruct` | `google/gemini-2.5-flash` | `light_extraction` — extractive summarization; task is deterministic compression not generation; cost must be minimal |
| `post_draft_analyzer` | `google/gemini-2.5-flash` | `meta/llama-3.3-70b-instruct` | `anthropic/claude-sonnet-4` | `light_extraction` + `long_context_coherence` — reads full draft + outline to identify gap categories; fast inference critical |
| `style_fixer` | `anthropic/claude-sonnet-4` | `anthropic/claude-opus-4-5` | `openai/gpt-4o` | `structured_output` — receives exact violation list from Style Linter; surgical form corrections only, must not alter content |
| `span_editor` | `anthropic/claude-sonnet-4` | `anthropic/claude-opus-4-5` | `openai/gpt-4o` | `structured_output` — constrained to ≤4 spans with exact context anchors; Sonnet follows tight schema better than Opus at lower cost |
| `run_companion` | `google/gemini-2.5-pro` | `anthropic/claude-sonnet-4` | `openai/gpt-4o` | `long_context_coherence` — reads entire DRSState including all verdicts, history, costs; must answer in <3s |

**Design note — Reasoning jury slot assignments vs. cascading tiers:**
The primary model column above defines the **decorrelated selection** for each judge slot (ensuring epistemic independence across R1/R2/R3). The `§8.5 JURY_TIERS` YAML block defines the **cascading fallback tiers within each slot** when the primary model is unavailable or budget triggers a downgrade. These are complementary, not contradictory:

- `judge_r1` primary = `deepseek/deepseek-r1` → §8.5 tier1 for slot R1
- `judge_r2` primary = `openai/o3-mini` → §8.5 tier2 for slot R2 (consistent with §8.5 JURY_TIERS `R.tier2`)
- `judge_r3` primary = `qwen/qwq-32b` → §8.5 tier3 for slot R3 (consistent with §8.5 JURY_TIERS `R.tier3`)

The ordering R1→R2→R3 also reflects descending cost priority for cascading: DeepSeek R1 (cheapest reasoning), o3-mini (mid-tier), qwq-32b (complementary corpus). Full o3 (non-mini) is **not** assigned to any Reasoning jury slot; it is reserved for `fusor` and `reflector` where `analytical_synthesis` over long multi-draft context is the decisive capability.

---

## §28.3 Model Verification Procedure

Executed at **preflight node** (see §4.1) before any LLM call is made.

```python
# src/llm/model_verifier.py
import httpx
from typing import TypedDict

class ModelStatus(TypedDict):
    model_id: str
    available: bool
    latency_ms: int
    fallback_activated: bool

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
VERIFICATION_TIMEOUT_S: float = 10.0

async def verify_models(
    model_ids: list[str],
    api_key: str,
) -> dict[str, ModelStatus]:
    """
    Calls GET /models on OpenRouter, checks each model_id is present.
    Returns status per model. Does NOT make a completion call (zero token cost).
    """
    async with httpx.AsyncClient(timeout=VERIFICATION_TIMEOUT_S) as client:
        t0 = __import__("time").monotonic()
        resp = await client.get(
            OPENROUTER_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"}
        )
        latency_ms = int((__import__("time").monotonic() - t0) * 1000)
        resp.raise_for_status()

    available_ids: set[str] = {m["id"] for m in resp.json()["data"]}
    results: dict[str, ModelStatus] = {}
    for mid in model_ids:
        results[mid] = ModelStatus(
            model_id=mid,
            available=mid in available_ids,
            latency_ms=latency_ms,
            fallback_activated=False,
        )
    return results

def resolve_with_fallbacks(
    slot: str,
    primary: str,
    fallbacks: list[str],
    statuses: dict[str, ModelStatus],
) -> str:
    """
    Returns first available model for slot. Updates fallback_activated flag.
    Raises RuntimeError if all models unavailable.
    """
    for model in [primary] + fallbacks:
        if statuses.get(model, {}).get("available", False):
            if model != primary:
                statuses[model]["fallback_activated"] = True
            return model
    raise RuntimeError(
        f"All models for slot '{slot}' unavailable: {[primary] + fallbacks}"
    )
```

**Procedure rules:**
- MUST run before `budget_estimator_node`
- If any primary model unavailable → activate fallback chain silently, log `WARN`
- If ALL models for a slot unavailable → `HARD_STOP`, emit `preflight_failure` event to SSE stream
- Results cached in `DRSState.circuit_breaker_states` for duration of run

---

## §28.4 MODEL_PRICING and Budget Estimator Impact

`MODEL_PRICING` is defined in a **single canonical file** `src/llm/pricing.py`. No other module in the codebase may define a duplicate `MODEL_PRICING` dict. All agents, the Budget Estimator (§19.1), and the Run Companion cost tracker MUST import from this module. Any reference to model pricing in §33.6 (LLM Routing) must import from `src/llm/pricing.py` rather than redeclaring prices inline.

```python
# src/llm/pricing.py
# Cost in USD per 1,000,000 tokens. Update via procedure below.
# Last verified: 2026-02-01 against OpenRouter /models endpoint.
# CANONICAL SOURCE OF TRUTH — do not duplicate in any other module.

MODEL_PRICING: dict[str, dict[str, float]] = {
    # format: {"in": $/M_input_tokens, "out": $/M_output_tokens}
    "anthropic/claude-opus-4-5":          {"in": 15.00,  "out": 75.00},
    "anthropic/claude-sonnet-4":           {"in":  3.00,  "out": 15.00},
    "openai/o3":                           {"in": 10.00,  "out": 40.00},
    "openai/o3-mini":                      {"in":  1.10,  "out":  4.40},
    "openai/gpt-4.5":                      {"in": 75.00,  "out": 150.00},
    "openai/gpt-4o":                       {"in":  2.50,  "out": 10.00},
    "openai/gpt-4o-search-preview":        {"in":  2.50,  "out": 10.00},
    # google/gemini-2.5-pro: out=$10.00/M verified 2026-02-01 via OpenRouter /models.
    # Earlier drafts listed $5.00/M — that figure is incorrect and must not be used.
    "google/gemini-2.5-pro":               {"in":  1.25,  "out": 10.00},
    "google/gemini-2.5-flash":             {"in":  0.075, "out":  0.30},
    "perplexity/sonar-pro":                {"in":  3.00,  "out": 15.00},
    "perplexity/sonar":                    {"in":  1.00,  "out":  1.00},
    "deepseek/deepseek-r1":                {"in":  0.55,  "out":  2.19},
    # qwen/qwq-32b: in=$0.15/M, out=$0.60/M verified 2026-02-01 via OpenRouter /models.
    # Earlier drafts listed in=$0.12/M, out=$0.18/M — those figures are incorrect.
    "qwen/qwq-32b":                        {"in":  0.15,  "out":  0.60},
    "qwen/qwen3-7b":                       {"in":  0.03,  "out":  0.05},
    "mistral/mistral-large-2411":          {"in":  2.00,  "out":  6.00},
    "mistral/mistral-large":               {"in":  2.00,  "out":  6.00},
    "meta/llama-3.3-70b-instruct":         {"in":  0.59,  "out":  0.79},
    "meta/llama-3.3-8b-instruct":          {"in":  0.06,  "out":  0.06},
    "meta/llama-3.1-70b-instruct":         {"in":  0.52,  "out":  0.75},
}

def cost_usd(model_id: str, tokens_in: int, tokens_out: int) -> float:
    p = MODEL_PRICING[model_id]
    return (tokens_in * p["in"] + tokens_out * p["out"]) / 1_000_000
```

### Pricing Update Procedure

```
Trigger: Weekly cron OR any model addition to YAML config
Steps:
  1. GET https://openrouter.ai/api/v1/models (authenticated)
  2. For each model_id in MODEL_PRICING:
       new_in  = response["pricing"]["prompt"]      * 1_000_000
       new_out = response["pricing"]["completion"]  * 1_000_000
  3. If abs(new_price - old_price) / old_price > 0.10:
       log WARNING with diff, update MODEL_PRICING in src/llm/pricing.py,
       commit to repo with message "pricing: update <model_id> verified <date>"
  4. Run: python scripts/validate_pricing.py
       → re-runs Budget Estimator on 3 golden-set configs
       → asserts estimated_cost within ±15% of last known actual
  5. If assertion fails: open issue "PRICING_DRIFT", block deploy
  6. Record verification timestamp in the "Last verified" comment at top of
     src/llm/pricing.py (format: YYYY-MM-DD against OpenRouter /models endpoint)
```

### Budget Estimator Impact

The `budget_estimator_node` (see §19.1) uses `MODEL_PRICING` directly via import from `src/llm/pricing.py`:

```python
# Simplified formula — full version at §19.1
from src.llm.pricing import cost_usd, MODEL_PRICING

def estimate_run_cost(
    n_sections: int,
    target_words: int,
    avg_iterations: float,        # default 2.5
    mow_enabled: bool,
    active_models: dict[str, str], # slot -> model_id
) -> float:
    words_per_sec = target_words / n_sections
    tok_writer = int(words_per_sec * 1.5)       # output tokens
    tok_judge  = int(words_per_sec * 0.4)       # each judge output
    tok_reflector = 800

    cost_writer_iter = cost_usd(
        active_models["writer_wa"], 0, tok_writer
    )
    cost_jury_iter = sum(
        cost_usd(active_models[slot], tok_judge * 3, tok_judge)
        for slot in ["judge_r1","judge_f1","judge_s1"]  # tier1 only in estimate
    )
    cost_reflector_iter = cost_usd(active_models["reflector"], tok_judge * 5, tok_reflector)

    mow_multiplier = 3.75 if mow_enabled else 1.0  # 3× writers + fusor overhead

    return (
        n_sections
        * avg_iterations
        * (cost_writer_iter * mow_multiplier + cost_jury_iter + cost_reflector_iter)
    )
```

**Impact chain:** `MODEL_PRICING` change → `estimate_run_cost` change → `regime` selection change (Economy/Balanced/Premium, see §19.2) → `css_threshold`, `max_iterations`, `jury_size` change → document quality/cost trade-off shifts. Any pricing update MUST be followed by re-validation of regime boundary thresholds against the 3 golden-set runs.

**Consistency enforcement:** The CI pipeline runs `python scripts/validate_pricing.py --check-duplicates` on every PR. This script asserts that `MODEL_PRICING` is defined in exactly one location (`src/llm/pricing.py`) and raises an error if any other Python file in the repository contains a dict literal named `MODEL_PRICING` or inline pricing values for any model ID present in the canonical dict.

<!-- SPEC_COMPLETE -->