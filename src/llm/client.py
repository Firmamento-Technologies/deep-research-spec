"""Unified LLM client with §29.1 prompt caching support.

Wraps Anthropic, OpenAI, Google, and OpenRouter APIs behind a single
``call()`` interface.  Automatically tracks cost via ``cost_usd()``
from ``src.llm.pricing`` and reports Prometheus metrics.

OpenRouter is the recommended provider: one API key for all models.

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
import time
from typing import Any

from src.llm.pricing import cost_usd
from src.llm.resilience import default_rate_limiter, retry_with_backoff
from src.observability.metrics import observe_llm_call

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "https://github.com/lucadidomenicodopehubs/deep-research-spec")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Deep Research System")


class LLMClient:
    """Unified LLM wrapper — OpenRouter, Anthropic, OpenAI, Google.

    Features:
    - OpenRouter as single-key gateway for all models
    - Automatic retry with exponential backoff on transient errors
    - Token bucket rate limiting (default 60 RPM)
    - Prometheus metrics (cost, latency, tokens)
    - Provider-prefixed model routing

    Model prefix convention:
        openrouter/<provider>/<model>  →  OpenRouter gateway (recommended)
        anthropic/<model>              →  Direct Anthropic API
        openai/<model>                 →  Direct OpenAI API
        google/<model>                 →  Direct Google Gemini API
    """

    def __init__(self, rate_limiter=None) -> None:
        self._anthropic: Any = None
        self._openai: Any = None
        self._openrouter: Any = None
        self._google: Any = None
        self._rate_limiter = rate_limiter or default_rate_limiter

    # ── Lazy SDK accessors ───────────────────────────────────────────────

    def _get_anthropic(self) -> Any:
        if self._anthropic is None:
            import anthropic  # type: ignore[import-untyped]
            self._anthropic = anthropic.Anthropic()
        return self._anthropic

    def _get_openai(self) -> Any:
        if self._openai is None:
            import openai  # type: ignore[import-untyped]
            self._openai = openai.OpenAI()
        return self._openai

    def _get_openrouter(self) -> Any:
        """OpenAI-compatible client pointed at OpenRouter."""
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

    def _get_google(self) -> Any:
        if self._google is None:
            import google.generativeai as genai  # type: ignore[import-untyped]
            genai.configure()
            self._google = genai
        return self._google

    # ── Main call method ─────────────────────────────────────────────────

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
        """Unified LLM call with retry, rate limiting, and cost tracking.

        Args:
            model:       Provider-prefixed model id.
                         Examples:
                           "openrouter/anthropic/claude-opus-4-5"  (recommended)
                           "openrouter/google/gemini-2.5-flash"
                           "openrouter/openai/gpt-4o"
                           "anthropic/claude-opus-4-5"  (direct)
            messages:    Chat messages.
            system:      System prompt (string or Anthropic cache-control list).
            temperature: Sampling temperature.
            max_tokens:  Max output tokens.
            agent:       Agent slot name (for metrics).
            preset:      Quality preset (for metrics).

        Returns:
            Dict: text, tokens_in, tokens_out, cost_usd,
                  cache_creation_tokens, cache_read_tokens, model, latency_s.
        """
        provider = model.split("/")[0]

        if not self._rate_limiter.acquire(timeout=60.0):
            raise RuntimeError(f"Rate limiter timeout for {agent}/{model}")

        t0 = time.perf_counter()

        result = self._dispatch_with_retry(
            provider, model, messages, system, temperature, max_tokens, **kwargs
        )

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
        self, provider: str, model: str, messages: list[dict],
        system: str | list[dict] | None,
        temperature: float, max_tokens: int, **kwargs: Any,
    ) -> dict:
        if provider == "openrouter":
            return self._call_openrouter(model, messages, system, temperature, max_tokens, **kwargs)
        elif provider == "anthropic":
            return self._call_anthropic(model, messages, system, temperature, max_tokens, **kwargs)
        elif provider == "openai":
            return self._call_openai(model, messages, system, temperature, max_tokens, **kwargs)
        elif provider == "google":
            return self._call_google(model, messages, system, temperature, max_tokens, **kwargs)
        else:
            raise ValueError(f"Unsupported provider: {provider!r} (model={model!r})")

    # ── Provider implementations ─────────────────────────────────────────

    def _call_openrouter(
        self, model: str, messages: list[dict],
        system: str | list[dict] | None,
        temperature: float, max_tokens: int, **kwargs: Any,
    ) -> dict:
        """Route call through OpenRouter (OpenAI-compatible API).

        model format: "openrouter/<provider>/<model>"
        e.g. "openrouter/anthropic/claude-opus-4-5"
             "openrouter/google/gemini-2.5-flash"
             "openrouter/openai/gpt-4o-mini"
        """
        client = self._get_openrouter()
        # Strip the "openrouter/" prefix → pass e.g. "anthropic/claude-opus-4-5"
        model_id = model[len("openrouter/"):]

        sys_content = ""
        if isinstance(system, str):
            sys_content = system
        elif isinstance(system, list):
            # Flatten Anthropic-style cache-control blocks to plain text
            sys_content = " ".join(
                block.get("text", "") for block in system
                if isinstance(block, dict)
            )

        full_messages = []
        if sys_content:
            full_messages.append({"role": "system", "content": sys_content})
        full_messages.extend(messages)

        response = client.chat.completions.create(
            model=model_id,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        text = response.choices[0].message.content or ""
        tokens_in = response.usage.prompt_tokens if response.usage else 0
        tokens_out = response.usage.completion_tokens if response.usage else 0

        # OpenRouter returns actual cost in usage (when available)
        or_cost = None
        if response.usage and hasattr(response.usage, "cost"):
            or_cost = response.usage.cost

        return self._build_result(
            model, text, tokens_in, tokens_out, 0, 0,
            override_cost=or_cost,
        )

    def _call_anthropic(
        self, model: str, messages: list[dict],
        system: str | list[dict] | None,
        temperature: float, max_tokens: int, **kwargs: Any,
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

        return self._build_result(model, text, tokens_in, tokens_out, cache_creation, cache_read)

    def _call_openai(
        self, model: str, messages: list[dict],
        system: str | list[dict] | None,
        temperature: float, max_tokens: int, **kwargs: Any,
    ) -> dict:
        client = self._get_openai()
        model_id = model.split("/", 1)[1]

        sys_content = system if isinstance(system, str) else ""
        full_messages = [{"role": "system", "content": sys_content}, *messages]

        response = client.chat.completions.create(
            model=model_id,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens
        text = response.choices[0].message.content

        return self._build_result(model, text, tokens_in, tokens_out, 0, 0)

    def _call_google(
        self, model: str, messages: list[dict],
        system: str | list[dict] | None,
        temperature: float, max_tokens: int, **kwargs: Any,
    ) -> dict:
        genai = self._get_google()
        model_id = model.split("/", 1)[1]

        gen_config = {"temperature": temperature, "max_output_tokens": max_tokens}
        sys_instruction = system if isinstance(system, str) else None
        gmodel = genai.GenerativeModel(
            model_name=model_id,
            system_instruction=sys_instruction,
            generation_config=gen_config,
        )

        contents = [
            {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
            for m in messages
        ]
        response = gmodel.generate_content(contents)

        text = response.text
        tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return self._build_result(model, text, tokens_in, tokens_out, 0, 0)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _build_result(
        self, model: str, text: str,
        tokens_in: int, tokens_out: int,
        cache_creation: int, cache_read: int,
        override_cost: float | None = None,
    ) -> dict:
        cost = override_cost if override_cost is not None else cost_usd(model, tokens_in, tokens_out)
        logger.debug(
            "LLM call: model=%s in=%d out=%d cost=$%.4f cache_create=%d cache_read=%d",
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


# ── Singleton instance ───────────────────────────────────────────────────────
llm_client = LLMClient()
