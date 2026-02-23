"""Tests for LLM client resilience (retry + rate limiting) and FastAPI API."""
from __future__ import annotations

import time
import unittest

from src.llm.resilience import (
    TokenBucketRateLimiter,
    _is_retryable,
    retry_with_backoff,
)


# ── Retry Tests ──────────────────────────────────────────────────────────────

class TestRetryableDetection(unittest.TestCase):
    """Test transient error detection."""

    def test_rate_limit_by_name(self):
        exc = type("RateLimitError", (Exception,), {})()
        self.assertTrue(_is_retryable(exc))

    def test_api_connection_error(self):
        exc = type("APIConnectionError", (Exception,), {})()
        self.assertTrue(_is_retryable(exc))

    def test_429_status_code(self):
        exc = type("HTTPError", (Exception,), {"status_code": 429})()
        self.assertTrue(_is_retryable(exc))

    def test_500_status_code(self):
        exc = type("ServerError", (Exception,), {"status_code": 500})()
        self.assertTrue(_is_retryable(exc))

    def test_rate_limit_in_message(self):
        exc = Exception("rate limit exceeded, please retry")
        self.assertTrue(_is_retryable(exc))

    def test_non_retryable(self):
        exc = ValueError("invalid model name")
        self.assertFalse(_is_retryable(exc))

    def test_auth_error_not_retryable(self):
        exc = type("AuthenticationError", (Exception,), {"status_code": 401})()
        self.assertFalse(_is_retryable(exc))


class TestRetryDecorator(unittest.TestCase):
    """Test retry_with_backoff decorator."""

    def test_succeeds_first_try(self):
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def ok():
            return "success"

        self.assertEqual(ok(), "success")

    def test_retries_on_transient_then_succeeds(self):
        attempts = [0]

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def flaky():
            attempts[0] += 1
            if attempts[0] < 3:
                exc = type("RateLimitError", (Exception,), {})()
                raise exc
            return "recovered"

        result = flaky()
        self.assertEqual(result, "recovered")
        self.assertEqual(attempts[0], 3)

    def test_raises_non_retryable_immediately(self):
        attempts = [0]

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def bad():
            attempts[0] += 1
            raise ValueError("not retryable")

        with self.assertRaises(ValueError):
            bad()
        self.assertEqual(attempts[0], 1)  # No retries

    def test_exhausts_retries(self):
        attempts = [0]

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fails():
            attempts[0] += 1
            exc = type("RateLimitError", (Exception,), {})()
            raise exc

        with self.assertRaises(Exception):
            always_fails()
        self.assertEqual(attempts[0], 3)  # 1 initial + 2 retries


# ── Rate Limiter Tests ───────────────────────────────────────────────────────

class TestTokenBucketRateLimiter(unittest.TestCase):
    """Test token bucket rate limiter."""

    def test_burst_capacity(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=600, burst_size=5)
        # Should allow burst_size requests immediately
        for _ in range(5):
            self.assertTrue(limiter.acquire(timeout=0.01))

    def test_available_tokens(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=60, burst_size=10)
        initial = limiter.available_tokens
        self.assertGreater(initial, 0)
        limiter.acquire(timeout=0.01)
        after = limiter.available_tokens
        self.assertLess(after, initial)

    def test_refill(self):
        limiter = TokenBucketRateLimiter(requests_per_minute=6000, burst_size=1)
        limiter.acquire(timeout=0.01)
        # Wait for refill (100 RPSec → refills in ~10ms)
        time.sleep(0.02)
        self.assertTrue(limiter.acquire(timeout=0.01))


# ── FastAPI Tests ────────────────────────────────────────────────────────────

class TestAPIModels(unittest.TestCase):
    """Test API Pydantic models."""

    def test_run_create_request(self):
        from src.api.models import RunCreateRequest
        req = RunCreateRequest(topic="Test topic about AI")
        self.assertEqual(req.topic, "Test topic about AI")
        self.assertEqual(req.target_words, 5000)
        self.assertEqual(req.quality_preset.value, "balanced")

    def test_run_create_validation(self):
        from src.api.models import RunCreateRequest
        with self.assertRaises(Exception):
            RunCreateRequest(topic="ab")  # min_length=3

    def test_health_response(self):
        from src.api.models import HealthResponse
        h = HealthResponse(uptime_s=42.5, runs_active=2)
        self.assertEqual(h.status, "ok")

    def test_run_response(self):
        from src.api.models import RunResponse, RunStatus
        from datetime import datetime, timezone
        r = RunResponse(
            run_id="abc",
            topic="Test",
            status=RunStatus.running,
            quality_preset="balanced",
            target_words=5000,
            created_at=datetime.now(timezone.utc),
        )
        self.assertEqual(r.status, RunStatus.running)


class TestAPIEndpoints(unittest.TestCase):
    """Test FastAPI endpoints with TestClient."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
            from src.api.server import app
            cls.client = TestClient(app)
            cls.has_testclient = True
        except ImportError:
            cls.has_testclient = False

    def test_health(self):
        if not self.has_testclient:
            self.skipTest("TestClient not available")
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("uptime_s", data)

    def test_create_run(self):
        if not self.has_testclient:
            self.skipTest("TestClient not available")
        r = self.client.post("/api/v1/runs", json={
            "topic": "Testing the Deep Research System",
            "target_words": 3000,
        })
        self.assertEqual(r.status_code, 202)
        data = r.json()
        self.assertIn("run_id", data)
        self.assertEqual(data["topic"], "Testing the Deep Research System")
        self.assertEqual(data["status"], "queued")
        return data["run_id"]

    def test_get_run(self):
        if not self.has_testclient:
            self.skipTest("TestClient not available")
        # Create first
        r1 = self.client.post("/api/v1/runs", json={"topic": "Get test topic"})
        run_id = r1.json()["run_id"]
        # Get
        r2 = self.client.get(f"/api/v1/runs/{run_id}")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["run_id"], run_id)

    def test_get_run_not_found(self):
        if not self.has_testclient:
            self.skipTest("TestClient not available")
        r = self.client.get("/api/v1/runs/nonexistent-id")
        self.assertEqual(r.status_code, 404)

    def test_list_runs(self):
        if not self.has_testclient:
            self.skipTest("TestClient not available")
        r = self.client.get("/api/v1/runs")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_cancel_run(self):
        if not self.has_testclient:
            self.skipTest("TestClient not available")
        r1 = self.client.post("/api/v1/runs", json={"topic": "Cancel test topic"})
        run_id = r1.json()["run_id"]
        r2 = self.client.delete(f"/api/v1/runs/{run_id}")
        self.assertEqual(r2.status_code, 204)

    def test_cancel_nonexistent(self):
        if not self.has_testclient:
            self.skipTest("TestClient not available")
        r = self.client.delete("/api/v1/runs/fake-id")
        self.assertEqual(r.status_code, 404)

    def test_openapi_docs(self):
        if not self.has_testclient:
            self.skipTest("TestClient not available")
        r = self.client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)
        schema = r.json()
        self.assertEqual(schema["info"]["title"], "Deep Research System")


class TestLLMClientResilience(unittest.TestCase):
    """Test LLMClient has retry and rate limiter."""

    def test_client_has_rate_limiter(self):
        from src.llm.client import LLMClient
        client = LLMClient()
        self.assertIsNotNone(client._rate_limiter)

    def test_client_unsupported_provider_still_raises(self):
        from src.llm.client import LLMClient
        client = LLMClient()
        with self.assertRaises(ValueError):
            client.call(model="unsupported/model", messages=[])

    def test_dispatch_method_exists(self):
        from src.llm.client import LLMClient
        self.assertTrue(hasattr(LLMClient, "_dispatch_with_retry"))


if __name__ == "__main__":
    unittest.main()
