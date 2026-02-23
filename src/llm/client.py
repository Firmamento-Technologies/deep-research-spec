"""Unified LLM client with §29.1 prompt caching support.

Wraps Anthropic, OpenAI, and Google (Gemini) APIs behind a single
``call()`` interface.  Automatically tracks cost via ``cost_usd()``
from ``src.llm.pricing`` and reports Prometheus metrics.

Client objects are initialised lazily so importing this module never
crashes — failures surface only when a call is actually made without
the required API key / SDK installed.

Usage::

    from src.llm.client import llm_client

    # Simple call
    result = llm_client.call(
        model="anthropic/claude-sonnet-4",
        messages=[{"role": "user", "content": "Hello"}],
    )

    # §29.1 Prompt Caching (Anthropic only)
    result = llm_client.call(
        model="anthropic/claude-opus-4-5",
        system=[
            {"type": "text", "text": "Cached rules…", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "Non-cached part"},
        ],
        messages=[{"role": "user", "content": "Write a section…"}],
    )
"""
from __future__ import annotations

import logging
import time
from typing import Any

from src.llm.pricing import cost_usd
from src.observability.metrics import observe_llm_call

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM wrapper — Anthropic, OpenAI, Google."""

    def __init__(self) -> None:
        # Lazy-init: SDK clients created on first use
        self._anthropic: Any = None
        self._openai: Any = None
        self._google: Any = None

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

    def _get_google(self) -> Any:
        if self._google is None:
            import google.generativeai as genai  # type: ignore[import-untyped]
            genai.configure()  # reads GOOGLE_API_KEY env var
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
        """Unified LLM call with automatic cost tracking.

        Args:
            model:       Provider-prefixed model id (e.g. ``"anthropic/claude-sonnet-4"``).
            messages:    Chat messages (``[{"role": "user", "content": "…"}]``).
            system:      System prompt — string or list of cache-control blocks
                         (§29.1, Anthropic only).
            temperature: Sampling temperature.
            max_tokens:  Max output tokens.
            agent:       Agent slot name (for metrics labeling).
            preset:      Quality preset (for metrics labeling).

        Returns:
            Dict with keys: ``text``, ``tokens_in``, ``tokens_out``,
            ``cost_usd``, ``cache_creation_tokens``, ``cache_read_tokens``,
            ``model``, ``latency_s``.
        """
        provider = model.split("/")[0]
        t0 = time.perf_counter()

        if provider == "anthropic":
            result = self._call_anthropic(model, messages, system, temperature, max_tokens, **kwargs)
        elif provider == "openai":
            result = self._call_openai(model, messages, system, temperature, max_tokens, **kwargs)
        elif provider == "google":
            result = self._call_google(model, messages, system, temperature, max_tokens, **kwargs)
        else:
            raise ValueError(f"Unsupported model provider: {provider!r} (model={model!r})")

        latency_s = time.perf_counter() - t0
        result["latency_s"] = round(latency_s, 3)

        # Prometheus metrics
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

    # ── Provider implementations ─────────────────────────────────────────

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

        # §29.1: system as list[dict] with cache_control
        if isinstance(system, list):
            create_kwargs["system"] = system
        elif system:
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

        gen_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        sys_instruction = system if isinstance(system, str) else None
        gmodel = genai.GenerativeModel(
            model_name=model_id,
            system_instruction=sys_instruction,
            generation_config=gen_config,
        )

        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [msg["content"]]})

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
    ) -> dict:
        cost = cost_usd(model, tokens_in, tokens_out)
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

