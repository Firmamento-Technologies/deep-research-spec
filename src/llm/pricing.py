"""MODEL_PRICING — §28.4 canonical. Single source of truth for all cost calculations."""

import logging

logger = logging.getLogger(__name__)

MODEL_PRICING: dict[str, dict[str, float]] = {
    # format: {"in": $/M_input_tokens, "out": $/M_output_tokens}
    # Last verified: 2026-03-12 against OpenRouter /models endpoint.

    # ── Anthropic ──
    "anthropic/claude-opus-4-5":          {"in": 15.00,  "out": 75.00},
    "anthropic/claude-sonnet-4":          {"in":  3.00,  "out": 15.00},
    "anthropic/claude-3.7-sonnet":        {"in":  3.00,  "out": 15.00},

    # ── OpenAI ──
    "openai/o3":                          {"in": 10.00,  "out": 40.00},
    "openai/o3-mini":                     {"in":  1.10,  "out":  4.40},
    "openai/gpt-4.5":                     {"in": 75.00,  "out": 150.00},
    "openai/gpt-4o":                      {"in":  2.50,  "out": 10.00},
    "openai/gpt-4o-search-preview":       {"in":  2.50,  "out": 10.00},

    # ── Google ──
    "google/gemini-2.5-pro":              {"in":  1.25,  "out": 10.00},
    "google/gemini-2.5-flash":            {"in":  0.075, "out":  0.30},
    "google/gemini-3-flash":              {"in":  0.075, "out":  0.30},

    # ── Perplexity ──
    "perplexity/sonar-pro":               {"in":  3.00,  "out": 15.00},
    "perplexity/sonar":                   {"in":  1.00,  "out":  1.00},

    # ── DeepSeek ──
    "deepseek/deepseek-r1":               {"in":  0.55,  "out":  2.19},

    # ── Qwen (legacy) ──
    "qwen/qwq-32b":                       {"in":  0.15,  "out":  0.60},
    "qwen/qwen3-7b":                      {"in":  0.03,  "out":  0.05},

    # ── Qwen 3.5 family (frontier, March 2026) ──
    "qwen/qwen3.5-0.8b":                  {"in":  0.05,  "out":  0.10},
    "qwen/qwen3.5-2b":                    {"in":  0.10,  "out":  0.15},
    "qwen/qwen3.5-4b":                    {"in":  0.10,  "out":  0.15},
    "qwen/qwen3.5-9b-instruct":           {"in":  0.10,  "out":  0.15},
    "qwen/qwen3.5-35b-a3b":               {"in":  0.25,  "out":  2.00},
    "qwen/qwen3.5-flash":                 {"in":  0.10,  "out":  0.40},
    "qwen/qwen3.5-plus":                  {"in":  0.40,  "out":  2.40},
    "qwen/qwen3.5-397b-moe":              {"in":  0.60,  "out":  3.60},

    # ── Mistral ──
    "mistral/mistral-large-2411":         {"in":  2.00,  "out":  6.00},
    "mistral/mistral-large":              {"in":  2.00,  "out":  6.00},

    # ── Meta ──
    "meta/llama-3.3-70b-instruct":        {"in":  0.59,  "out":  0.79},
    "meta/llama-3.3-8b-instruct":         {"in":  0.06,  "out":  0.06},
    "meta/llama-3.1-70b-instruct":        {"in":  0.52,  "out":  0.75},
}

# Fallback pricing for unknown models (avoids KeyError crash)
_FALLBACK_PRICING: dict[str, float] = {"in": 0.0, "out": 0.0}


def cost_usd(model_id: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost in USD for a single LLM call.

    Returns 0.0 for unknown models instead of crashing (FIX BUG #1.1).
    """
    p = MODEL_PRICING.get(model_id)
    if p is None:
        logger.warning("cost_usd: unknown model '%s', returning $0.00", model_id)
        p = _FALLBACK_PRICING
    return (tokens_in * p["in"] + tokens_out * p["out"]) / 1_000_000
