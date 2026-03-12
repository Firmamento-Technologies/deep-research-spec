"""Unified LLM client with §29.1 prompt caching and RLM rate limiting.

Wraps Anthropic, OpenAI, Google, and OpenRouter APIs behind a single
``call()`` interface. Automatically tracks cost via ``cost_usd()``
from ``src.llm.pricing`` and reports Prometheus metrics.

RLM changes vs original:
  - Thread-safe SDK init: per-SDK threading.Lock eliminates race conditions
    with parallel jury execution (Priority 4)
  - Google model instance cache: keyed by (model_id, sys_hash, temperature,
    max_tokens) — eliminates N identical re-instantiations per section (Priority 13)
  - Per-model RLM rate limiter: replaces global 60-RPM singleton with
    independent per-model token buckets from src.llm.rate_limiter (Priority 5)
  - OpenRouter cache_control fix: list[dict] system prompts forwarded as
    content array instead of flattened to string (Priority 2)
  - OpenAI system prompt fix: correctly handles list[dict] in system field (Priority 11)
  - on_429 drain: RLM bucket for failed model is drained on HTTP 429

Usage::

    from src.llm.client import llm_client

    # Via OpenRouter (recommended - single API key)
    result = llm_client.call(
        model="openrouter/anthropic/claude-opus-4-5",
        messages=[{"role": "user", "content": "Hello"}],
    )

    # Direct Anthropic (with §29.1 Prompt Caching)
    result = llm_client.call(
        model="anthropic/claude-opus-4-5",
        system=[
            {"type": "text", "text": "Cached rules…", "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": "Write a section…"}],
    )
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Tuple

from src.llm.pricing import cost_usd
from src.llm.rate_limiter import rlm_rate_limiter, estimate_tokens
from src.llm.resilience import retry_with_backoff
from src.observability.metrics import observe_llm_call

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_SITE_URL = os.getenv(
    "OPENROUTER_SITE_URL",
    "https://github.com/lucadidomenicodopehubs/deep-research-spec",
)
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Deep Research System")


class LLMClient:
    """Unified LLM wrapper — OpenRouter, Anthropic, OpenAI, Google.

    RLM-integrated: per-model rate limiting, thread-safe lazy SDK init,
    Google model instance caching, Anthropic cache_control preservation.

    Model prefix convention:
        openrouter/<provider>/<model>  →  OpenRouter gateway (recommended)
        anthropic/<model>              →  Direct Anthropic API (prompt caching §29.1)
        openai/<model>                 →  Direct OpenAI API
        google/<model>                 →  Direct Google Gemini API
    """

    def __init__(self) -> None:
        # SDK client instances
        self._anthropic: Any = None
        self._openai: Any = None
        self._openrouter: Any = None
        self._google_sdk: Any = None

        # Per-SDK initialization locks — eliminates race conditions in parallel jury
        # (9 judges may all call _get_* concurrently on first section)
        self._anthropic_lock = threading.Lock()
        self._openai_lock = threading.Lock()
        self._openrouter_lock = threading.Lock()
        self._google_lock = threading.Lock()

        # Google model instance cache: (model_id, sys_hash, temperature, max_tokens) → model
        # Avoids repeated GenerativeModel() instantiation for identical configs.
        self._google_models: Dict[Tuple, Any] = {}
        self._google_models_lock = threading.Lock()

    # ── Thread-safe SDK accessors ────────────────────────────────────

    def _get_anthropic(self) -> Any:
        if self._anthropic is None:
            with self._anthropic_lock:
                if self._anthropic is None:  # double-checked locking
                    import anthropic  # type: ignore[import-untyped]
                    self._anthropic = anthropic.Anthropic()
        return self._anthropic

    def _get_openai(self) -> Any:
        if self._openai is None:
            with self._openai_lock:
                if self._openai is None:
                    import openai  # type: ignore[import-untyped]
                    self._openai = openai.OpenAI()
        return self._openai

    def _get_openrouter(self) -> Any:
        """OpenAI-compatible client pointed at OpenRouter."""
        if self._openrouter is None:
            with self._openrouter_lock:
                if self._openrouter is None:
                    import openai  # type: ignore[import-untyped]
                    api_key = os.getenv("OPENROUTER_API_KEY")
                    if not api_key:
                        raise RuntimeError(
                            "OPENROUTER_API_KEY not set. "
                            "Get one at https://openrouter.ai/keys"
                        )
                    self._openrouter = openai.OpenAI(
                        base_url=OPENROUTER_BASE_URL,
                        api_key=api_key,
                        default_headers={
                            "HTTP-Referer": OPENROUTER_SITE_URL,
                            "X-Title": OPENROUTER_SITE_NAME,
                        },
                    )
        return self._openrouter

    def _get_google_sdk(self) -> Any:
        if self._google_sdk is None:
            with self._google_lock:
                if self._google_sdk is None:
                    import google.generativeai as genai  # type: ignore[import-untyped]
                    genai.configure()
                    self._google_sdk = genai
        return self._google_sdk

    def _get_google_model(
        self,
        model_id: str,
        system_instruction: str | None,
        temperature: float,
        max_tokens: int,
    ) -> Any:
        """Return a cached Google GenerativeModel instance.

        Cache key: (model_id, hash(system_instruction), temperature, max_tokens).
        Avoids re-instantiation on every section iteration or jury retry.
        """
        sys_hash = hash(system_instruction or "")
        cache_key = (model_id, sys_hash, temperature, max_tokens)
        with self._google_models_lock:
            if cache_key not in self._google_models:
                genai = self._get_google_sdk()
                gen_config = {
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
                self._google_models[cache_key] = genai.GenerativeModel(
                    model_name=model_id,
                    system_instruction=system_instruction,
                    generation_config=gen_config,
                )
                logger.debug(
                    "LLMClient: cached Google model instance for %s", model_id
                )
            return self._google_models[cache_key]

    # ── Main call method ───────────────────────────────────────────

    def call(
        self,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        agent: str = "unknown",
        preset: str = "balanced",
        **kwargs: Any,
    ) -> dict:
        """Unified LLM call with RLM rate limiting, retry, and cost tracking.

        Args:
            model:       Provider-prefixed model id.
                         Examples:
                           "openrouter/anthropic/claude-opus-4-5"  (recommended)
                           "openrouter/google/gemini-2.5-flash"
                           "anthropic/claude-opus-4-5"  (direct, prompt caching)
            messages:    Chat messages list.
            system:      System prompt — str or Anthropic cache-control list[dict].
            temperature: Sampling temperature.
            max_tokens:  Max output tokens.
            agent:       Agent slot name (for Prometheus metrics).
            preset:      Quality preset (for Prometheus metrics).

        Returns:
            Dict: text, tokens_in, tokens_out, cost_usd,
            cache_creation_tokens, cache_read_tokens, model, latency_s.
        """
        provider = model.split("/")[0]

        # Estimate tokens for per-model RLM rate limiter
        all_text = " ".join(
            m.get("content", "") if isinstance(m.get("content"), str) else ""
            for m in messages
        )
        if isinstance(system, str):
            all_text += " " + system
        elif isinstance(system, list):
            all_text += " " + " ".join(
                b.get("text", "") for b in system if isinstance(b, dict)
            )
        estimated_tokens = estimate_tokens(all_text) + max_tokens

        # Per-model rate limiter — independent bucket per model string
        if not rlm_rate_limiter.acquire(
            model=model,
            estimated_tokens=estimated_tokens,
            timeout=120.0,
        ):
            raise RuntimeError(
                f"RLM rate limiter timeout: model={model}, agent={agent}"
            )

        t0 = time.perf_counter()
        try:
            result = self._dispatch_with_retry(
                provider, model, messages, system, temperature, max_tokens, **kwargs
            )
        except Exception as exc:
            # On HTTP 429, drain only this model's bucket
            err_str = str(exc).lower()
            if "429" in err_str or "rate limit" in err_str or "too many" in err_str:
                rlm_rate_limiter.on_429(model)
            raise

        latency_s = time.perf_counter() - t0
        result["latency_s"] = round(latency_s, 3)

        observe_llm_call(
            agent=agent,
            model=model,
            preset=preset,
            tokens_in=result["tokens_in"],
            tokens_out=result["tokens_out"],
            cost_usd=result["cost_usd"],
            latency_s=latency_s,
        )

        return result

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0)
    def _dispatch_with_retry(
        self,
        provider: str,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> dict:
        dispatch = {
            "openrouter": self._call_openrouter,
            "anthropic":  self._call_anthropic,
            "openai":     self._call_openai,
            "google":     self._call_google,
        }
        handler = dispatch.get(provider)
        if handler is None:
            raise ValueError(f"Unsupported provider: {provider!r} (model={model!r})")
        return handler(model, messages, system, temperature, max_tokens, **kwargs)

    # ── Provider implementations ───────────────────────────────────

    def _call_openrouter(
        self,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> dict:
        """Route call through OpenRouter (OpenAI-compatible API).

        Cache_control fix: Anthropic-style list[dict] system prompts are
        forwarded as a content array (NOT flattened to string) so OpenRouter
        can pass cache_control blocks natively to the Anthropic backend.
        For non-Anthropic models, cache_control fields are gracefully ignored.
        """
        client = self._get_openrouter()
        model_id = model[len("openrouter/"):]  # strip "openrouter/" prefix

        full_messages: list[dict] = []

        if system is not None:
            if isinstance(system, list):
                # Preserve cache_control blocks — pass as content array, not plain string.
                # OpenRouter forwards this to Anthropic backend natively.
                full_messages.append({"role": "system", "content": system})
            elif isinstance(system, str) and system:
                full_messages.append({"role": "system", "content": system})

        full_messages.extend(messages)

        response = client.chat.completions.create(
            model=model_id,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        text = (response.choices[0].message.content or "") if response.choices else ""
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0

        or_cost = None
        if response.usage and hasattr(response.usage, "cost"):
            or_cost = response.usage.cost

        return self._build_result(
            model, text, tokens_in, tokens_out, 0, 0,
            override_cost=or_cost,
        )

    def _call_anthropic(
        self,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> dict:
        client = self._get_anthropic()
        model_id = model.split("/", 1)[1]

        create_kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if system is not None:
            create_kwargs["system"] = system

        response = client.messages.create(**create_kwargs)

        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        text = response.content[0].text
        cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0

        return self._build_result(
            model, text, tokens_in, tokens_out, cache_creation, cache_read
        )

    def _call_openai(
        self,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> dict:
        client = self._get_openai()
        model_id = model.split("/", 1)[1]

        full_messages: list[dict] = []
        if system is not None:
            if isinstance(system, list):
                # OpenAI accepts list[dict] as multi-part system content
                full_messages.append({"role": "system", "content": system})
            elif isinstance(system, str) and system:
                full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        response = client.chat.completions.create(
            model=model_id,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0
        text = (response.choices[0].message.content or "") if response.choices else ""

        return self._build_result(model, text, tokens_in, tokens_out, 0, 0)

    def _call_google(
        self,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> dict:
        model_id = model.split("/", 1)[1]
        sys_instruction = system if isinstance(system, str) else None

        # Use cached model instance — avoids re-instantiation on every call
        gmodel = self._get_google_model(
            model_id, sys_instruction, temperature, max_tokens
        )

        contents = [
            {
                "role": "user" if m["role"] == "user" else "model",
                "parts": [m["content"]],
            }
            for m in messages
        ]
        response = gmodel.generate_content(contents)

        text = response.text
        tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return self._build_result(model, text, tokens_in, tokens_out, 0, 0)

    # ── Helpers ────────────────────────────────────────────────

    def _build_result(
        self,
        model: str,
        text: str,
        tokens_in: int,
        tokens_out: int,
        cache_creation: int,
        cache_read: int,
        override_cost: float | None = None,
    ) -> dict:
        cost = (
            override_cost
            if override_cost is not None
            else cost_usd(model, tokens_in, tokens_out)
        )
        logger.debug(
            "LLMClient: model=%s in=%d out=%d cost=$%.4f "
            "cache_create=%d cache_read=%d",
            model, tokens_in, tokens_out, cost, cache_creation, cache_read,
        )
        return {
            "text": text,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost,
            "cache_creation_tokens": cache_creation,
            "cache_read_tokens": cache_read,
            "model": model,
        }


# ── Singleton instance ─────────────────────────────────────────────
llm_client = LLMClient()
