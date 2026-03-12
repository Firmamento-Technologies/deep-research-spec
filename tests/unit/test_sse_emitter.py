"""Tests for SSE emitter bridge."""
import pytest


def test_import_succeeds():
    """SSE emitter module should be importable without error."""
    from src.sse.emitter import emit
    assert callable(emit)


def test_emit_does_not_raise():
    """emit() should be fire-and-forget — never raise."""
    from src.sse.emitter import emit
    # Should not raise even without Redis/broker
    emit("TEST_EVENT", {"doc_id": "test-123", "data": "hello"})


def test_emit_with_no_data():
    """emit() should work with no data dict."""
    from src.sse.emitter import emit
    emit("TEST_EVENT")
