"""MODEL_PRICING — §28.4 canonical. Single source of truth for all cost calculations."""

MODEL_PRICING: dict[str, dict[str, float]] = {
    # format: {"in": $/M_input_tokens, "out": $/M_output_tokens}
    # Last verified: 2026-02-01 against OpenRouter /models endpoint.
    "anthropic/claude-opus-4-5":          {"in": 15.00,  "out": 75.00},
    "anthropic/claude-sonnet-4":          {"in":  3.00,  "out": 15.00},
    "openai/o3":                          {"in": 10.00,  "out": 40.00},
    "openai/o3-mini":                     {"in":  1.10,  "out":  4.40},
    "openai/gpt-4.5":                     {"in": 75.00,  "out": 150.00},
    "openai/gpt-4o":                      {"in":  2.50,  "out": 10.00},
    "openai/gpt-4o-search-preview":       {"in":  2.50,  "out": 10.00},
    "google/gemini-2.5-pro":              {"in":  1.25,  "out": 10.00},
    "google/gemini-2.5-flash":            {"in":  0.075, "out":  0.30},
    "perplexity/sonar-pro":               {"in":  3.00,  "out": 15.00},
    "perplexity/sonar":                   {"in":  1.00,  "out":  1.00},
    "deepseek/deepseek-r1":               {"in":  0.55,  "out":  2.19},
    "qwen/qwq-32b":                       {"in":  0.15,  "out":  0.60},
    "qwen/qwen3-7b":                      {"in":  0.03,  "out":  0.05},
    "mistral/mistral-large-2411":         {"in":  2.00,  "out":  6.00},
    "mistral/mistral-large":              {"in":  2.00,  "out":  6.00},
    "meta/llama-3.3-70b-instruct":        {"in":  0.59,  "out":  0.79},
    "meta/llama-3.3-8b-instruct":         {"in":  0.06,  "out":  0.06},
    "meta/llama-3.1-70b-instruct":        {"in":  0.52,  "out":  0.75},
}


def cost_usd(model_id: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost in USD for a single LLM call."""
    p = MODEL_PRICING[model_id]
    return (tokens_in * p["in"] + tokens_out * p["out"]) / 1_000_000
