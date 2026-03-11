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
from typing import AsyncGenerator, Dict, Deque, Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

APPROVAL_TTL_S = 3600

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
        # HITL approval waiters (in-process)
        self._outline_approvals: Dict[str, asyncio.Future] = {}
        self._section_approvals: Dict[str, Dict[int, asyncio.Future]] = {}
        self._waiters_lock = asyncio.Lock()
        logger.info("SSEBroker initialized")

    def _outline_approval_key(self, doc_id: str) -> str:
        return f"run:{doc_id}:approval:outline"

    def _section_approval_key(self, doc_id: str, section_idx: int) -> str:
        return f"run:{doc_id}:approval:section:{section_idx}"

    async def _store_pending_approval(self, key: str, payload: Dict[str, Any]) -> None:
        try:
            await self.redis.set(key, json.dumps(payload), ex=APPROVAL_TTL_S)
        except Exception as exc:
            logger.warning("Failed to persist pending approval %s: %s", key, exc)

    async def _consume_pending_approval(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            raw = await self.redis.get(key)
            if not raw:
                return None
            await self.redis.delete(key)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            if isinstance(raw, str):
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logger.warning("Failed to consume pending approval %s: %s", key, exc)
        return None

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
                    # Yield heartbeat when timer elapsed
                    if heartbeat_task.done():
                        try:
                            heartbeat = heartbeat_task.result()
                            yield heartbeat
                        finally:
                            # Recreate task for next heartbeat window
                            heartbeat_task = asyncio.create_task(self._heartbeat())

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


    async def wait_for_outline_approval(
        self,
        doc_id: str,
        default_sections: list,
        timeout_s: float = 600.0,
    ) -> list:
        """Wait for outline approval from API and return approved sections.

        Falls back to default sections on timeout.
        """
        persisted = await self._consume_pending_approval(self._outline_approval_key(doc_id))
        if persisted is not None:
            approved = bool(persisted.get("approved", True))
            if not approved:
                return default_sections
            sections = persisted.get("sections")
            return sections if sections else default_sections


        loop = asyncio.get_running_loop()
        future = loop.create_future()

        async with self._waiters_lock:
            prev = self._outline_approvals.get(doc_id)
            if prev and not prev.done():
                prev.cancel()
            self._outline_approvals[doc_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=timeout_s)
            approved = bool(result.get("approved", True))
            if not approved:
                return default_sections
            sections = result.get("sections")
            return sections if sections else default_sections
        except asyncio.TimeoutError:
            logger.warning("[%s] Outline approval timeout after %.1fs, auto-approving", doc_id, timeout_s)
            return default_sections
        finally:
            async with self._waiters_lock:
                current = self._outline_approvals.get(doc_id)
                if current is future:
                    self._outline_approvals.pop(doc_id, None)

    async def wait_for_section_approval(
        self,
        doc_id: str,
        section_idx: int,
        default_content: str,
        timeout_s: float = 600.0,
    ) -> str:
        """Wait for section approval from API and return approved content."""
        persisted = await self._consume_pending_approval(
            self._section_approval_key(doc_id, section_idx)
        )
        if persisted is not None:
            approved = bool(persisted.get("approved", True))
            if not approved:
                return default_content
            edited = persisted.get("content")
            return edited if isinstance(edited, str) and edited.strip() else default_content

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        async with self._waiters_lock:
            per_doc = self._section_approvals.setdefault(doc_id, {})
            prev = per_doc.get(section_idx)
            if prev and not prev.done():
                prev.cancel()
            per_doc[section_idx] = future

        try:
            result = await asyncio.wait_for(future, timeout=timeout_s)
            approved = bool(result.get("approved", True))
            if not approved:
                return default_content
            edited = result.get("content")
            return edited if isinstance(edited, str) and edited.strip() else default_content
        except asyncio.TimeoutError:
            logger.warning(
                "[%s] Section %d approval timeout after %.1fs, auto-approving",
                doc_id, section_idx, timeout_s,
            )
            return default_content
        finally:
            async with self._waiters_lock:
                per_doc = self._section_approvals.get(doc_id)
                if per_doc and per_doc.get(section_idx) is future:
                    per_doc.pop(section_idx, None)
                if per_doc == {}:
                    self._section_approvals.pop(doc_id, None)

    async def submit_outline_approval(self, doc_id: str, payload: Dict[str, Any]) -> None:
        """Resolve a pending outline waiter if present; otherwise persist it."""
        async with self._waiters_lock:
            fut = self._outline_approvals.get(doc_id)
            if fut and not fut.done():
                fut.set_result(payload)
                return

        await self._store_pending_approval(self._outline_approval_key(doc_id), payload)

    async def submit_section_approval(self, doc_id: str, section_idx: int, payload: Dict[str, Any]) -> None:
        """Resolve a pending section waiter if present; otherwise persist it."""
        async with self._waiters_lock:
            fut = self._section_approvals.get(doc_id, {}).get(section_idx)
            if fut and not fut.done():
                fut.set_result(payload)
                return

        await self._store_pending_approval(self._section_approval_key(doc_id, section_idx), payload)

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
