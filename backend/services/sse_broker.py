"""SSE Broker for real-time event streaming.

Provides pub/sub infrastructure for Server-Sent Events (SSE) to stream
research pipeline events to frontend clients.

Architecture:

    Graph Node
        ↓
    broker.emit(doc_id, event_type, payload)
        ↓
    Redis pub/sub channel: "run:{doc_id}:events"
        ↓
    API endpoint: /api/runs/{doc_id}/stream
        ↓
    broker.subscribe(doc_id) → AsyncGenerator
        ↓
    SSE stream to frontend

Features:
- Event buffer: stores last 10 events per doc_id for late subscribers
- Heartbeat: sends keep-alive comments every 30s
- Multi-instance: Redis pub/sub enables horizontal scaling
- State persistence: updates Redis state for backward compatibility
- Graceful cleanup: unsubscribes on client disconnect

Usage:
    from services.sse_broker import get_broker
    
    broker = get_broker()
    
    # In graph node:
    await broker.emit(doc_id, "NODE_STARTED", {"node": "planner"})
    
    # In API endpoint:
    async def stream_events(doc_id: str):
        async for event in broker.subscribe(doc_id):
            yield f"data: {json.dumps(event)}\\n\\n"

Spec: §10 SSE streaming, §20 Real-time updates
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Deque

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSEBroker class
# ---------------------------------------------------------------------------

class SSEBroker:
    """Broker for publishing and subscribing to SSE events via Redis."""

    def __init__(self, redis_client: aioredis.Redis):
        """Initialize SSE broker.

        Args:
            redis_client: Async Redis client instance.
        """
        self.redis = redis_client
        # Event buffer: {doc_id: deque([event, ...], maxlen=10)}
        self._event_buffers: Dict[str, Deque[dict]] = {}
        logger.info("SSEBroker initialized")

    async def emit(
        self,
        doc_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        """Publish an SSE event to all subscribers.

        Args:
            doc_id:     Document ID (channel identifier).
            event_type: Event type (e.g., "NODE_STARTED").
            payload:    Event data dict.
        """
        # Build event object
        event = {
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "doc_id": doc_id,
        }

        # Buffer event (for late subscribers)
        if doc_id not in self._event_buffers:
            self._event_buffers[doc_id] = deque(maxlen=10)
        self._event_buffers[doc_id].append(event)

        # Publish to Redis pub/sub
        channel = f"run:{doc_id}:events"
        try:
            await self.redis.publish(channel, json.dumps(event))
            logger.debug("[%s] Emitted event: %s", doc_id, event_type)
        except Exception as exc:
            logger.error(
                "[%s] Failed to publish event %s: %s",
                doc_id, event_type, exc,
            )

        # Update Redis state (backward compatibility)
        await self._update_state(doc_id, event_type, payload)

    async def subscribe(self, doc_id: str) -> AsyncGenerator[dict, None]:
        """Subscribe to SSE events for a document.

        Yields buffered events first (last 10), then real-time events.
        Includes heartbeat keep-alive comments every 30s.

        Args:
            doc_id: Document ID to subscribe to.

        Yields:
            Event dicts with keys: type, payload, timestamp, doc_id.
        """
        logger.info("[%s] New SSE subscription", doc_id)

        # 1. Yield buffered events (replay last 10)
        if doc_id in self._event_buffers:
            for event in self._event_buffers[doc_id]:
                yield event

        # 2. Subscribe to Redis pub/sub
        pubsub = self.redis.pubsub()
        channel = f"run:{doc_id}:events"

        try:
            await pubsub.subscribe(channel)
            logger.debug("[%s] Subscribed to channel: %s", doc_id, channel)

            # 3. Stream real-time events with heartbeat
            heartbeat_task = asyncio.create_task(self._heartbeat())

            try:
                async for message in pubsub.listen():
                    # Yield heartbeat if available
                    if not heartbeat_task.done():
                        try:
                            heartbeat = heartbeat_task.result()
                            yield heartbeat
                            # Recreate task for next heartbeat
                            heartbeat_task = asyncio.create_task(self._heartbeat())
                        except asyncio.InvalidStateError:
                            pass  # Task not done yet

                    # Yield real event
                    if message["type"] == "message":
                        try:
                            event = json.loads(message["data"])
                            yield event
                        except json.JSONDecodeError as exc:
                            logger.error(
                                "[%s] Failed to parse event: %s",
                                doc_id, exc,
                            )

            finally:
                heartbeat_task.cancel()

        except Exception as exc:
            logger.error(
                "[%s] Subscription error: %s",
                doc_id, exc, exc_info=True,
            )

        finally:
            # Cleanup
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.info("[%s] SSE subscription closed", doc_id)

    async def _heartbeat(self) -> dict:
        """Generate heartbeat event after 30s delay.

        Returns:
            Heartbeat event dict.
        """
        await asyncio.sleep(30)
        return {
            "type": "HEARTBEAT",
            "payload": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _update_state(
        self,
        doc_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        """Update Redis state based on event type.

        Provides backward compatibility with old state management.

        Args:
            doc_id:     Document ID.
            event_type: Event type.
            payload:    Event payload.
        """
        state_key = f"run:{doc_id}:state"

        try:
            raw = await self.redis.get(state_key)
            state: dict = json.loads(raw) if raw else {}

            # Update state based on event type
            match event_type:
                case "NODE_STARTED":
                    nid = payload.get("node")
                    if nid:
                        state.setdefault("nodes", {})
                        state["nodes"][nid] = {
                            **state["nodes"].get(nid, {"id": nid}),
                            "status": "running",
                            "started_at": payload.get("timestamp"),
                        }

                case "NODE_COMPLETED":
                    nid = payload.get("node")
                    if nid:
                        state.setdefault("nodes", {})
                        state["nodes"][nid] = {
                            **state["nodes"].get(nid, {"id": nid}),
                            "status": "completed",
                            "duration_ms": int((payload.get("duration_s") or 0) * 1_000),
                            "tokens_in": payload.get("tokens_in"),
                            "tokens_out": payload.get("tokens_out"),
                            "cost_usd": payload.get("cost_usd"),
                        }

                case "NODE_FAILED":
                    nid = payload.get("node")
                    if nid:
                        state.setdefault("nodes", {})
                        state["nodes"][nid] = {
                            **state["nodes"].get(nid, {"id": nid}),
                            "status": "failed",
                            "error": payload.get("error"),
                        }

                case "BUDGET_UPDATE":
                    state["budget_spent"] = payload.get("spent", 0.0)
                    state["budget_remaining_pct"] = payload.get("remaining_pct", 100.0)

                case "SECTION_APPROVED":
                    idx = payload.get("section_idx")
                    for s in state.get("sections", []):
                        if s.get("idx") == idx:
                            s["approved"] = True
                            break

                case "PIPELINE_STARTED":
                    state["status"] = "running"

                case "PIPELINE_COMPLETED" | "DOCUMENT_COMPLETED":
                    state["status"] = "completed"

                case "PIPELINE_FAILED":
                    state["status"] = "failed"

                case "PIPELINE_CANCELLED":
                    state["status"] = "cancelled"

            # Save state back to Redis
            await self.redis.set(state_key, json.dumps(state), ex=86_400)

        except Exception as exc:
            logger.warning(
                "[%s] Failed to update state for event %s: %s",
                doc_id, event_type, exc,
            )


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

_broker_instance: SSEBroker | None = None


def get_broker() -> SSEBroker:
    """Get the global SSEBroker instance.

    Lazily creates the broker on first call using the shared Redis client.

    Returns:
        SSEBroker singleton.
    """
    global _broker_instance

    if _broker_instance is None:
        from services.redis_client import redis as redis_client
        _broker_instance = SSEBroker(redis_client)
        logger.info("Global SSEBroker instance created")

    return _broker_instance
