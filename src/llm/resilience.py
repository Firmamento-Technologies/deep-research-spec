"""Retry and rate-limiting utilities for LLM calls.

Provides:
- ``retry_with_backoff``: decorator for exponential backoff on transient errors
- ``TokenBucketRateLimiter``: thread-safe token bucket for request throttling
"""
from __future__ import annotations

import logging
import random
import threading
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Retryable exception detection ────────────────────────────────────────────

# HTTP status codes that indicate transient failures
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 529}

# Exception class names that indicate transient failures
_RETRYABLE_EXCEPTIONS = (
    "RateLimitError",
    "APIStatusError",
    "APIConnectionError",
    "InternalServerError",
    "ServiceUnavailableError",
    "APITimeoutError",
    "ResourceExhausted",
    "DeadlineExceeded",
)


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is retryable (transient)."""
    exc_name = type(exc).__name__

    # Match by class name (avoids importing each SDK)
    if exc_name in _RETRYABLE_EXCEPTIONS:
        return True

    # Check HTTP status code if present
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int) and status in _RETRYABLE_STATUS_CODES:
        return True

    # Check for "rate limit" in message
    msg = str(exc).lower()
    if "rate limit" in msg or "too many requests" in msg or "quota" in msg:
        return True

    return False


# ── Retry decorator ─────────────────────────────────────────────────────────

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> Callable:
    """Decorator: retry function on transient errors with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay:  Initial delay in seconds (doubles each retry).
        max_delay:   Maximum delay cap in seconds.
        jitter:      Add random jitter to prevent thundering herd.

    Non-retryable errors (ValueError, auth errors, etc.) are raised immediately.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc

                    if not _is_retryable(exc):
                        raise

                    if attempt >= max_retries:
                        logger.error(
                            "LLM call failed after %d retries: %s",
                            max_retries, exc,
                        )
                        raise

                    delay = min(base_delay * (2 ** attempt), max_delay)
                    if jitter:
                        delay *= 0.5 + random.random()

                    logger.warning(
                        "LLM call attempt %d/%d failed (%s: %s) — retrying in %.1fs",
                        attempt + 1, max_retries + 1,
                        type(exc).__name__, str(exc)[:100],
                        delay,
                    )
                    time.sleep(delay)

            raise last_exc  # type: ignore[misc]

        return wrapper
    return decorator


# ── Token Bucket Rate Limiter ────────────────────────────────────────────────

class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter.

    Controls request rate to avoid hitting API rate limits.
    Tokens replenish at a fixed rate; each request consumes one token.

    Args:
        requests_per_minute: Maximum sustained request rate.
        burst_size: Maximum burst capacity (defaults to requests_per_minute).
    """

    def __init__(
        self,
        requests_per_minute: float = 60.0,
        burst_size: int | None = None,
    ) -> None:
        self._rate = requests_per_minute / 60.0  # tokens per second
        self._capacity = float(burst_size or int(requests_per_minute))
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Block until a token is available, up to timeout seconds.

        Returns True if a token was acquired, False on timeout.
        """
        deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True

            # Wait before retrying
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.05, remaining))

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (approximate)."""
        with self._lock:
            self._refill()
            return self._tokens


# ── Default rate limiter instance ────────────────────────────────────────────

# 60 RPM default — safe for most LLM APIs
default_rate_limiter = TokenBucketRateLimiter(requests_per_minute=60, burst_size=10)
