"""Canonical model pricing for DRS.

All cost calculations MUST import from this module. No other module may define
a duplicate MODEL_PRICING dict or inline pricing values.

Last verified: 2026-02-01 against OpenRouter /models endpoint.
Update procedure: §28.4 in spec.
"""

from typing import Dict

# Cost in USD per 1,000,000 tokens
# Format: {"in": input_price_per_M, "out": output_price_per_M}
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # --- Writer models ---
    "anthropic/claude-opus-4-5": {"in": 15.00, "out": 75.00},
    "anthropic/claude-sonnet-4": {"in": 3.00, "out": 15.00},
    "anthropic/claude-haiku-3": {"in": 0.25, "out": 1.25},
    
    # --- Reasoning models (Jury R) ---
    "openai/o3": {"in": 10.00, "out": 40.00},
    "openai/o3-mini": {"in": 1.10, "out": 4.40},
    "deepseek/deepseek-r1": {"in": 0.55, "out": 2.19},
    "qwen/qwq-32b": {"in": 0.15, "out": 0.60},  # Verified 2026-02-01
    
    # --- GPT family ---
    "openai/gpt-4.5": {"in": 75.00, "out": 150.00},  # Critical: Judge S1
    "openai/gpt-4o": {"in": 2.50, "out": 10.00},
    "openai/gpt-4o-search-preview": {"in": 2.50, "out": 10.00},
    
    # --- Gemini family ---
    "google/gemini-2.5-pro": {"in": 1.25, "out": 10.00},  # Verified $10/M out
    "google/gemini-2.5-flash": {"in": 0.075, "out": 0.30},
    "google/gemini-1.5-pro": {"in": 1.25, "out": 5.00},
    
    # --- Search models (Researcher, Judge F) ---
    "perplexity/sonar-pro": {"in": 3.00, "out": 15.00},
    "perplexity/sonar": {"in": 1.00, "out": 1.00},
    
    # --- Light models (Compressor, Post-Draft) ---
    "qwen/qwen3-7b": {"in": 0.03, "out": 0.05},
    "meta/llama-3.3-8b-instruct": {"in": 0.06, "out": 0.06},
    "meta/llama-3.3-70b-instruct": {"in": 0.59, "out": 0.79},
    "meta/llama-3.1-70b-instruct": {"in": 0.52, "out": 0.75},
    
    # --- Mistral family (Judge S) ---
    "mistral/mistral-large-2411": {"in": 2.00, "out": 6.00},
    "mistral/mistral-large": {"in": 2.00, "out": 6.00},
}


def cost_usd(model_id: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate USD cost for a model invocation.
    
    Args:
        model_id: Full model identifier (e.g., "anthropic/claude-opus-4-5")
        tokens_in: Input token count
        tokens_out: Output token count
        
    Returns:
        Cost in USD
        
    Raises:
        KeyError: If model_id not in MODEL_PRICING
    """
    if model_id not in MODEL_PRICING:
        raise KeyError(
            f"Model '{model_id}' not found in MODEL_PRICING. "
            f"Available models: {list(MODEL_PRICING.keys())}"
        )
    
    pricing = MODEL_PRICING[model_id]
    return (tokens_in * pricing["in"] + tokens_out * pricing["out"]) / 1_000_000


def get_model_pricing(model_id: str) -> Dict[str, float]:
    """Get pricing dict for a model (for reference/logging only)."""
    return MODEL_PRICING[model_id].copy()
