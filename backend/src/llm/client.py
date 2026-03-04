"""Unified LLM client for the DRS research pipeline.

All LLM calls in the pipeline go through this module. It provides:
- Async OpenRouter API calls (OpenAI-compatible endpoint)
- Automatic model selection from settings (node_id → model)
- Token counting and USD cost tracking via pricing.py
- Exponential backoff retry on transient errors
- Optional token streaming for SSE delivery to the frontend
- Budget guard: raises BudgetExceededError before making a call
  when projected cost would push budget_spent over max_budget

Usage
-----
    client = await get_llm_client(db_session)

    response = await client.chat(
        messages=[
            {"role": "system", "content": "You are a research assistant."},
            {"role": "user",   "content": "Summarise quantum computing."},
        ],
        node_id="planner",          # resolved to model via settings
        state=state,                # ResearchState — budget is checked + updated
    )

    print(response.content)        # LLM output text
    print(response.cost_usd)       # e.g. 0.0034

Spec: §28 Model assignments, §19 Budget tracking
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from src.llm.pricing import MODEL_PRICING, cost_usd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT_S   = 120.0   # seconds before httpx raises TimeoutException
SETTINGS_TTL_S      = 300     # re-read DB settings every 5 minutes

# Fallback model when node_id not in settings assignments
FALLBACK_MODEL = "google/gemini-2.5-flash"

# Retry config
MAX_RETRIES   = 3
BASE_DELAY_S  = 1.0   # initial back-off
MAX_DELAY_S   = 30.0  # cap

# HTTP status codes that are transient and worth retrying
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""
    def __init__(self, message: str, status_code: int = 0, raw: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.raw = raw


class BudgetExceededError(Exception):
    """Raised before a call when it would push budget_spent over max_budget."""
    def __init__(self, spent: float, max_budget: float, projected: float):
        super().__init__(
            f"Budget exceeded: spent=${spent:.4f}, max=${max_budget:.4f}, "
            f"projected=${projected:.4f}"
        )
        self.spent = spent
        self.max_budget = max_budget
        self.projected = projected


# ---------------------------------------------------------------------------
# Response type
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    """Result of a single LLM call.

    All cost figures are in USD. Plug `cost_usd` directly into
    ResearchState.budget_spent after the call.
    """
    content: str                    # Generated text
    model: str                      # Actual model used (may differ from requested)
    tokens_in: int                  # Prompt tokens
    tokens_out: int                 # Completion tokens
    cost_usd: float                 # Calculated from pricing.py
    latency_s: float                # Wall-clock seconds for the call
    node_id: Optional[str] = None   # Which pipeline node made the call
    finish_reason: str = "stop"     # "stop" | "length" | "content_filter"

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out


# ---------------------------------------------------------------------------
# Settings loader  (caches DB settings in-process)
# ---------------------------------------------------------------------------

class _SettingsCache:
    """Thin cache around the DB settings row.

    Re-reads from the database at most once per SETTINGS_TTL_S seconds.
    Falls back to environment variables when the DB is unavailable.
    """

    def __init__(self):
        self._api_key: str = ""
        self._model_assignments: dict = {}
        self._loaded_at: float = 0.0

    async def get_api_key(self, db=None) -> str:
        await self._refresh(db)
        return self._api_key

    async def get_assignments(self, db=None) -> dict:
        await self._refresh(db)
        return self._model_assignments

    async def _refresh(self, db=None) -> None:
        now = time.monotonic()
        if now - self._loaded_at < SETTINGS_TTL_S:
            return

        # Try DB first
        if db is not None:
            try:
                from sqlalchemy import select
                from database.models import Settings
                result = await db.execute(select(Settings).limit(1))
                row = result.scalars().first()
                if row:
                    api_keys = row.api_keys or {}
                    self._api_key = api_keys.get("openrouter", "") or os.getenv("OPENROUTER_API_KEY", "")
                    self._model_assignments = row.model_assignments or {}
                    self._loaded_at = now
                    return
            except Exception as exc:
                logger.warning("Failed to load settings from DB: %s", exc)

        # Env-var fallback
        self._api_key = os.getenv("OPENROUTER_API_KEY", "")
        self._model_assignments = {}
        self._loaded_at = now


_settings_cache = _SettingsCache()


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------

class LLMClient:
    """Async OpenRouter client used by all pipeline nodes.

    Instantiate via `get_llm_client()` rather than directly so that the
    API key and model assignments are loaded from the database.
    """

    def __init__(
        self,
        api_key: str,
        model_assignments: dict | None = None,
    ):
        if not api_key:
            raise LLMError("OPENROUTER_API_KEY is not set. Configure it in Settings.")

        self.api_key = api_key
        self.model_assignments: dict = model_assignments or {}

        self._http = httpx.AsyncClient(
            base_url=OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://drs.local",
                "X-Title": "DRS Deep Research System",
                "Content-Type": "application/json",
            },
            timeout=DEFAULT_TIMEOUT_S,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def model_for(self, node_id: str) -> str:
        """Resolve the model ID for a given pipeline node.

        Looks up node_id in the DB model_assignments (cached). Falls back
        to FALLBACK_MODEL if the node is not configured.

        Args:
            node_id: e.g. "planner", "writer_a", "r1", "s1", etc.

        Returns:
            Full model ID, e.g. "google/gemini-2.5-pro"
        """
        model = self.model_assignments.get(node_id, "")
        if not model:
            logger.warning("No model assignment for node '%s', using %s", node_id, FALLBACK_MODEL)
            return FALLBACK_MODEL
        return model

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        node_id: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4_096,
        state: Any | None = None,   # ResearchState for budget check+update
        max_retries: int = MAX_RETRIES,
    ) -> LLMResponse:
        """Send a chat completion request.

        Exactly one of `model` or `node_id` must be provided. If `node_id`
        is given the model is resolved via model_for(). If both are given,
        `model` takes precedence.

        Args:
            messages:     OpenAI-format message list.
            model:        Explicit model ID (overrides node_id).
            node_id:      Pipeline node name — resolved to model via settings.
            temperature:  Sampling temperature (0–1).
            max_tokens:   Maximum output tokens.
            state:        If provided, budget is checked before and
                          budget_spent is updated after the call.
            max_retries:  Override default retry count.

        Returns:
            LLMResponse with content, token counts, cost, latency.

        Raises:
            LLMError:           After all retries are exhausted.
            BudgetExceededError: If state.budget_spent >= state.max_budget.
        """
        resolved_model = model or self.model_for(node_id or "")
        _check_budget(state, resolved_model)

        payload = {
            "model":       resolved_model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }

        response = await _call_with_retry(
            self._http, "/chat/completions", payload, max_retries
        )

        llm_resp = _parse_response(response, resolved_model, node_id)
        _update_budget(state, llm_resp)
        return llm_resp

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        node_id: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4_096,
        state: Any | None = None,
    ) -> AsyncIterator[str]:
        """Stream token chunks from the LLM.

        Yields individual text deltas as they arrive. Useful for
        forwarding tokens to the frontend via SSE.

        Usage::

            async for chunk in client.stream(messages, node_id="writer_a"):
                await broker.emit(doc_id, "TOKEN", {"delta": chunk})

        Note: budget update happens at stream end (on `finish_reason`).
        """
        resolved_model = model or self.model_for(node_id or "")
        _check_budget(state, resolved_model)

        payload = {
            "model":       resolved_model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
            "stream":      True,
        }

        tokens_in  = _estimate_prompt_tokens(messages)
        tokens_out = 0
        t0 = time.monotonic()

        async with self._http.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    import json as _json
                    chunk = _json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        tokens_out += 1  # approx; real count at stream end
                        yield delta
                except Exception:
                    continue

        # Approximate cost update at stream end
        approx_cost = cost_usd(resolved_model, tokens_in, tokens_out)
        if state is not None:
            state["budget_spent"] = state.get("budget_spent", 0.0) + approx_cost
            max_b = state.get("max_budget", 1.0)
            spent  = state["budget_spent"]
            state["budget_remaining_pct"] = max(0.0, (max_b - spent) / max_b * 100)

    async def aclose(self) -> None:
        """Close the underlying HTTP client. Call on shutdown."""
        await self._http.aclose()

    # Context-manager support
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.aclose()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

async def get_llm_client(db=None) -> LLMClient:
    """Create an LLMClient loaded from DB settings (or env vars).

    Call this inside every node that needs LLM access::

        client = await get_llm_client(db_session)
        response = await client.chat(messages, node_id="planner", state=state)

    Args:
        db: AsyncSession from SQLAlchemy. Pass None to use env vars only.

    Returns:
        Configured LLMClient instance.

    Raises:
        LLMError: If OPENROUTER_API_KEY is not set anywhere.
    """
    api_key     = await _settings_cache.get_api_key(db)
    assignments = await _settings_cache.get_assignments(db)
    return LLMClient(api_key=api_key, model_assignments=assignments)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _check_budget(state: Any | None, model: str) -> None:
    """Raise BudgetExceededError if the run has already hit its hard cap."""
    if state is None:
        return
    spent     = state.get("budget_spent", 0.0)
    max_b     = state.get("max_budget",   0.0)
    hard_stop = state.get("hard_stop_fired", False)
    if hard_stop or (max_b > 0 and spent >= max_b):
        raise BudgetExceededError(spent=spent, max_budget=max_b, projected=spent)


def _update_budget(state: Any | None, response: LLMResponse) -> None:
    """Add call cost to ResearchState.budget_spent and recompute pct."""
    if state is None:
        return
    state["budget_spent"] = state.get("budget_spent", 0.0) + response.cost_usd
    max_b  = state.get("max_budget", 0.0)
    spent  = state["budget_spent"]
    state["budget_remaining_pct"] = (
        max(0.0, (max_b - spent) / max_b * 100) if max_b > 0 else 0.0
    )
    if max_b > 0 and spent >= max_b:
        state["hard_stop_fired"] = True
        logger.warning(
            "Hard stop fired: budget_spent=%.4f >= max_budget=%.4f",
            spent, max_b,
        )


async def _call_with_retry(
    http: httpx.AsyncClient,
    path: str,
    payload: dict,
    max_retries: int,
) -> dict:
    """POST to OpenRouter with exponential-backoff retry."""
    delay = BASE_DELAY_S
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.monotonic()
            resp = await http.post(path, json=payload)
            resp.raise_for_status()
            data = resp.json()
            data["_latency_s"] = time.monotonic() - t0
            return data

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raw    = exc.response.text[:500]
            logger.warning(
                "LLM attempt %d/%d failed: HTTP %d  %.120s",
                attempt, max_retries, status, raw,
            )
            if status not in RETRYABLE_STATUS:
                raise LLMError(
                    f"Non-retryable HTTP {status}: {raw}", status_code=status, raw=raw
                ) from exc
            last_error = exc

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning("LLM attempt %d/%d network error: %s", attempt, max_retries, exc)
            last_error = exc

        if attempt < max_retries:
            logger.info("Retrying in %.1fs ...", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY_S)

    raise LLMError(
        f"LLM call failed after {max_retries} attempts: {last_error}"
    ) from last_error


def _parse_response(data: dict, model: str, node_id: str | None) -> LLMResponse:
    """Extract content and usage from an OpenRouter response dict."""
    try:
        choice  = data["choices"][0]
        content = choice["message"]["content"] or ""
        finish  = choice.get("finish_reason", "stop")
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected response shape: {exc}  raw={str(data)[:300]}")

    usage      = data.get("usage") or {}
    tokens_in  = usage.get("prompt_tokens",     0)
    tokens_out = usage.get("completion_tokens", 0)
    latency    = data.get("_latency_s", 0.0)

    # Determine actual model used (OpenRouter may reroute)
    actual_model = data.get("model", model)

    # Calculate cost (fall back to 0 if model not in pricing table)
    try:
        call_cost = cost_usd(actual_model, tokens_in, tokens_out)
    except KeyError:
        logger.warning("Model '%s' not in pricing table, cost set to 0", actual_model)
        call_cost = 0.0

    logger.info(
        "[%s] model=%s  in=%d  out=%d  cost=$%.5f  %.2fs",
        node_id or "?", actual_model, tokens_in, tokens_out, call_cost, latency,
    )

    return LLMResponse(
        content=content,
        model=actual_model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=call_cost,
        latency_s=latency,
        node_id=node_id,
        finish_reason=finish,
    )


def _estimate_prompt_tokens(messages: list[dict]) -> int:
    """Rough token estimate for prompt messages (streaming only).

    Uses a simple 4-chars-per-token heuristic. The exact count is
    unavailable until the stream completes, so this is only used to
    approximate budget consumption during streaming.
    """
    total_chars = sum(len(m.get("content") or "") for m in messages)
    return max(1, total_chars // 4)
