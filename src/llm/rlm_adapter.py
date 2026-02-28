"""DeepResearchLM: BaseLM adapter bridging RLM → our llm_client stack.

RLM (https://github.com/alexzhang13/rlm, arXiv:2512.24601) runs its own
REPL loop and spawns sub-calls via BaseLM subclasses. By default it
instantiates its own HTTP clients, which bypass:
  - our per-model rate limiter (P5)
  - our cost tracking / budget_controller
  - our tier upgrade guard (P9 / RLM_ALLOW_TIER_UPGRADE)
  - our retry and fallback logic

This module provides ``DeepResearchLM``, a ``BaseLM`` subclass whose
``completion()`` method delegates every call — root AND recursive
sub-calls — to our ``llm_client``. RLM drives the REPL orchestration;
our stack owns transport, rate limiting, and cost accounting.

Usage (from writer_node)::

    from src.llm.rlm_adapter import get_rlm_client

    rlm = get_rlm_client(
        model=route_model("writer", preset),
        child_model=route_model("writer", "economy"),
        state=state,
    )
    result = rlm.completion(full_prompt)
    draft = result.response
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from rlm import RLM
from rlm.clients import BaseLM
from rlm.core.types import UsageSummary
from rlm.logger import RLMLogger

from src.llm.client import llm_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Env-driven RLM settings
# ---------------------------------------------------------------------------
_RLM_ENVIRONMENT: str = os.getenv("RLM_ENVIRONMENT", "local")
_RLM_LOG_DIR: str = os.getenv("RLM_LOG_DIR", "./logs/rlm")
_RLM_MAX_ITERATIONS: int = int(os.getenv("RLM_MAX_ITERATIONS", "30"))
_RLM_MAX_DEPTH: int = int(os.getenv("RLM_MAX_DEPTH", "2"))


# ---------------------------------------------------------------------------
# BaseLM adapter
# ---------------------------------------------------------------------------

class DeepResearchLM(BaseLM):
    """BaseLM subclass that routes every RLM call through our llm_client.

    RLM passes this object to its internal ``LMHandler``, which calls
    ``completion()`` for each REPL iteration. By delegating here we
    guarantee that rate limiting, cost tracking, and tier-upgrade
    enforcement apply to ALL calls, including recursive sub-calls.

    Args:
        model_name: Provider-prefixed model string (e.g.
            ``"openrouter/google/gemini-2.5-pro"``). Must match the
            format expected by ``llm_client.call()``.
        agent: Agent tag passed to the rate limiter and cost tracker.
        preset: Quality preset (``"economy"``/``"balanced"``/``"premium"``).
    """

    def __init__(
        self,
        model_name: str,
        agent: str = "writer_rlm",
        preset: str = "balanced",
    ) -> None:
        self._model_name = model_name
        self._agent = agent
        self._preset = preset
        self._last_usage: dict[str, Any] = {}

    # ---- BaseLM interface --------------------------------------------------

    @property
    def model_name(self) -> str:
        return self._model_name

    def completion(
        self,
        prompt: str | list[dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        """Delegate to llm_client, returning plain text for RLM's REPL loop.

        RLM calls this for every iteration: root turns and recursive
        sub-calls at depth > 0. Rate limiter and cost tracker apply to all.
        """
        start = time.perf_counter()

        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = prompt

        response = llm_client.call(
            model=self._model_name,
            messages=messages,
            agent=self._agent,
            preset=self._preset,
        )

        elapsed = time.perf_counter() - start
        self._last_usage = {
            "input_tokens": response.get("input_tokens", 0),
            "output_tokens": response.get("output_tokens", 0),
            "cost_usd": response.get("cost_usd", 0.0),
            "latency_s": elapsed,
        }

        logger.debug(
            "DeepResearchLM: model=%s agent=%s "
            "in=%d out=%d cost=$%.5f latency=%.2fs",
            self._model_name, self._agent,
            self._last_usage["input_tokens"],
            self._last_usage["output_tokens"],
            self._last_usage["cost_usd"],
            elapsed,
        )

        return response["text"]

    def get_last_usage(self) -> UsageSummary:
        """Return usage wrapped in RLM's UsageSummary for budget tracking."""
        return UsageSummary(
            model_usage_summaries={
                self._model_name: {
                    "total_input_tokens": self._last_usage.get("input_tokens", 0),
                    "total_output_tokens": self._last_usage.get("output_tokens", 0),
                    "total_cost": self._last_usage.get("cost_usd", 0.0),
                }
            }
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_rlm_client(
    model: str,
    child_model: str | None = None,
    state: dict | None = None,
) -> RLM:
    """Build a fully-wired RLM instance backed by our llm_client.

    Args:
        model:       Root model (from ``route_model('writer', preset)``).
        child_model: Model for recursive sub-calls. Defaults to
                     ``route_model('writer', 'economy')`` to keep sub-call
                     costs low. Pass the same as ``model`` to use a single
                     backbone.
        state:       DocumentState dict. Used to read
                     ``state['section_budget_usd']`` for per-section budget
                     cap and ``state['quality_preset']`` for agent tagging.

    Returns:
        A configured :class:`RLM` instance ready for ``rlm.completion()``.

    Example::

        from src.llm.rlm_adapter import get_rlm_client
        from src.llm.routing import route_model

        rlm = get_rlm_client(
            model=route_model("writer", preset),
            child_model=route_model("writer", "economy"),
            state=state,
        )
        result = rlm.completion(full_prompt)
        draft = result.response
    """
    state = state or {}
    preset = state.get("quality_preset", "balanced")
    budget_usd: float | None = state.get("section_budget_usd")

    if child_model is None:
        # Sub-calls default to economy tier to avoid runaway costs during
        # recursive decomposition.  Caller can override if needed.
        from src.llm.routing import route_model as _route
        child_model = _route("writer", "economy")

    root_lm = DeepResearchLM(model_name=model, agent="writer_rlm", preset=preset)
    child_lm = DeepResearchLM(
        model_name=child_model, agent="writer_rlm_sub", preset="economy"
    )

    rlm_logger = RLMLogger(log_dir=_RLM_LOG_DIR)

    logger.info(
        "RLM client: root=%s child=%s env=%s max_depth=%d max_iter=%d budget=$%s",
        model, child_model, _RLM_ENVIRONMENT,
        _RLM_MAX_DEPTH, _RLM_MAX_ITERATIONS,
        f"{budget_usd:.4f}" if budget_usd else "none",
    )

    return RLM(
        backend="openai",           # backend is overridden by custom_client below
        backend_kwargs={"model_name": model},
        environment=_RLM_ENVIRONMENT,
        max_depth=_RLM_MAX_DEPTH,
        max_iterations=_RLM_MAX_ITERATIONS,
        max_budget=budget_usd,
        logger=rlm_logger,
        # Route all HTTP through our stack
        custom_client=root_lm,          # root turns
        custom_sub_client=child_lm,     # recursive sub-calls
    )
