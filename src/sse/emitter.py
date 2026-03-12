"""SSE emitter bridge — fire-and-forget event emission for graph nodes.

Bridges src/ graph nodes to the backend SSE broker (backend/services/sse_broker.py).
Non-blocking: failures are logged and silently ignored so pipeline is never blocked.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_broker = None


def _get_broker():
    """Lazy-load the SSE broker singleton."""
    global _broker
    if _broker is None:
        try:
            from backend.services.sse_broker import get_broker
            _broker = get_broker()
        except ImportError:
            logger.debug("SSE broker not available (backend not in path)")
            return None
    return _broker


def emit(event: str, data: dict[str, Any] | None = None) -> None:
    """Emit an SSE event. Fire-and-forget — never raises."""
    try:
        broker = _get_broker()
        if broker is None:
            logger.debug("SSE emit skipped (no broker): %s", event)
            return

        doc_id = (data or {}).get("doc_id", "unknown")

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(broker.emit(doc_id, event, data or {}))
        except RuntimeError:
            # No running event loop — skip async emission
            logger.debug("SSE emit skipped (no event loop): %s", event)
    except Exception as e:
        logger.warning("SSE emit failed (non-blocking): %s — %s", event, e)
