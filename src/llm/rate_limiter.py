"""RLM Rate Limiter — per-model token-aware token bucket.

Replaces the global singleton rate limiter with independent buckets
per model string. Each bucket tracks both RPM and TPM independently,
allowing full parallelism across different model providers without
cross-model interference.

Key design decision: a single global 60-RPM bucket serializes all 9 jury
judges even when they use completely different providers. Per-model buckets
allow 3 OpenAI + 3 Google + 3 Anthropic calls to run concurrently, limited
only by per-provider caps.

Priority 5 fix from RLM cost analysis (arXiv:2512.24601 integration plan).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider limit table
# Format: model_string -> (rpm, tpm)   [conservative, safe defaults]
# ---------------------------------------------------------------------------
_MODEL_LIMITS: Dict[str, Tuple[int, int]] = {
    # Anthropic direct
    "anthropic/claude-opus-4-5":            (50,   40_000),
    "anthropic/claude-sonnet-4":            (100,  80_000),
    # OpenAI direct
    "openai/o3":                            (20,   30_000),
    "openai/o3-mini":                       (500,  200_000),
    # Google direct
    "google/gemini-2.5-pro":               (60,   300_000),
    "google/gemini-2.5-flash":             (1000, 1_000_000),
    # OpenRouter shared gateway (aggregate limits across all models)
    "_openrouter_default":                  (500,  500_000),
}
_DEFAULT_LIMITS: Tuple[int, int] = (60, 100_000)

# Conservative tokens-per-word ratio (accounts for prompt markup + JSON overhead)
_TOKENS_PER_WORD: float = 1.35


@dataclass
class _ModelBucket:
    """Thread-safe token bucket for a single model.

    Implements token bucket algorithm with continuous refill based on
    monotonic clock. Both RPM (requests per minute) and TPM (tokens per
    minute) are tracked independently.
    """
    rpm: int
    tpm: int
    _rpm_available: float = field(init=False)
    _tpm_available: float = field(init=False)
    _last_ts: float = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        self._rpm_available = float(self.rpm)
        self._tpm_available = float(self.tpm)
        self._last_ts = time.monotonic()

    def _refill(self) -> None:
        """Refill bucket based on elapsed time. Must be called under self._lock."""
        now = time.monotonic()
        elapsed = now - self._last_ts
        self._rpm_available = min(
            float(self.rpm),
            self._rpm_available + elapsed * (self.rpm / 60.0),
        )
        self._tpm_available = min(
            float(self.tpm),
            self._tpm_available + elapsed * (self.tpm / 60.0),
        )
        self._last_ts = now

    def acquire(self, estimated_tokens: int, timeout: float) -> bool:
        """Block until capacity available or timeout expires.

        Returns True if capacity acquired, False on timeout.
        Polls every 50ms to avoid busy-waiting.
        """
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if (
                    self._rpm_available >= 1.0
                    and self._tpm_available >= float(estimated_tokens)
                ):
                    self._rpm_available -= 1.0
                    self._tpm_available -= float(estimated_tokens)
                    return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.05, remaining))

    def drain(self) -> None:
        """Zero the bucket. Called on HTTP 429 to prevent further requests."""
        with self._lock:
            self._rpm_available = 0.0
            self._tpm_available = 0.0

    def update_limits(self, rpm: int, tpm: int) -> None:
        """Runtime limit update (e.g. from upgraded API plan)."""
        with self._lock:
            self.rpm = rpm
            self.tpm = tpm


class PerModelRateLimiter:
    """RLM rate limiter: independent token bucket per model. Thread-safe singleton.

    Usage:
        from src.llm.rate_limiter import rlm_rate_limiter, estimate_tokens

        tokens = estimate_tokens(prompt_text) + max_tokens
        if not rlm_rate_limiter.acquire(model=model, estimated_tokens=tokens):
            raise RuntimeError(f"Rate limit timeout for {model}")
    """

    def __init__(self) -> None:
        self._buckets: Dict[str, _ModelBucket] = {}
        self._meta_lock = threading.Lock()

    def _resolve_limits(self, model: str) -> Tuple[int, int]:
        """Return (rpm, tpm) for a model string."""
        if model in _MODEL_LIMITS:
            return _MODEL_LIMITS[model]
        provider = model.split("/")[0]
        if provider == "openrouter":
            return _MODEL_LIMITS["_openrouter_default"]
        return _DEFAULT_LIMITS

    def _get_bucket(self, model: str) -> _ModelBucket:
        with self._meta_lock:
            if model not in self._buckets:
                rpm, tpm = self._resolve_limits(model)
                self._buckets[model] = _ModelBucket(rpm=rpm, tpm=tpm)
                logger.debug(
                    "RLM RateLimiter: created bucket for %s (rpm=%d, tpm=%d)",
                    model, rpm, tpm,
                )
            return self._buckets[model]

    def acquire(
        self,
        model: str,
        estimated_tokens: int = 1_000,
        timeout: float = 120.0,
    ) -> bool:
        """Acquire capacity for one request with estimated_tokens.

        Blocks up to `timeout` seconds. Returns False on timeout.
        Each model has its own independent bucket — acquiring for model A
        never blocks model B.
        """
        bucket = self._get_bucket(model)
        acquired = bucket.acquire(estimated_tokens, timeout)
        if not acquired:
            logger.warning(
                "RLM RateLimiter: timeout waiting for model=%s estimated_tokens=%d timeout=%.1fs",
                model, estimated_tokens, timeout,
            )
        return acquired

    def on_429(
        self,
        model: str,
        retry_after_s: Optional[float] = None,
    ) -> None:
        """Callback on HTTP 429. Drains only the affected model's bucket.

        Other models continue unaffected. Natural token refill resumes
        after drain, proportional to elapsed time.
        """
        self._get_bucket(model).drain()
        logger.warning(
            "RLM RateLimiter: 429 for %s — bucket drained. retry_after=%.1fs",
            model,
            retry_after_s or 0.0,
        )

    def update_model_limits(
        self,
        model: str,
        rpm: int,
        tpm: int,
    ) -> None:
        """Adjust limits at runtime (e.g. after API plan upgrade)."""
        self._get_bucket(model).update_limits(rpm, tpm)
        logger.info(
            "RLM RateLimiter: updated %s → rpm=%d tpm=%d",
            model, rpm, tpm,
        )


def estimate_tokens(text: str) -> int:
    """Fast token count estimation without full tokenizer overhead.

    Primary: tiktoken cl100k_base (accurate, ~1ms per 1K tokens).
    Fallback: whitespace word count * 1.35 ratio (if tiktoken unavailable).

    Used by client.py before each LLM call to size the rate limiter acquire.
    """
    try:
        import tiktoken  # type: ignore[import-untyped]
        enc = tiktoken.get_encoding("cl100k_base")
        return max(1, len(enc.encode(text, disallowed_special=())))
    except Exception:
        return max(1, int(len(text.split()) * _TOKENS_PER_WORD))


# ---------------------------------------------------------------------------
# Module-level singleton
# Import: from src.llm.rate_limiter import rlm_rate_limiter, estimate_tokens
# ---------------------------------------------------------------------------
rlm_rate_limiter = PerModelRateLimiter()
