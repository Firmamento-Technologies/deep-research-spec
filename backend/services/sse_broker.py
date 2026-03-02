# SSEBroker — bridge between LangGraph pipeline and SSE clients.
# Publishes events to Redis pub/sub channels and persists run state.
# Spec: UI_BUILD_PLAN.md Section 10.

from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import redis.asyncio as aioredis


class SSEBroker:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def emit(self, doc_id: str, event_type: str, data: dict) -> None:
        """Publish one SSE event and update the persistent run state in Redis."""
        payload = json.dumps({
            "event": event_type,
            "data":  {**data, "ts": datetime.now(timezone.utc).isoformat()},
        })
        await self.redis.publish(f"run:{doc_id}:events", payload)
        await self._update_state(doc_id, event_type, data)

    async def _update_state(self, doc_id: str, event_type: str, data: dict) -> None:
        """Patch the relevant field in run:{doc_id}:state based on event type."""
        state_key = f"run:{doc_id}:state"
        raw = await self.redis.get(state_key)
        state: dict = json.loads(raw) if raw else {}

        match event_type:
            case "NODE_STARTED":
                nid = data.get("node")
                if nid:
                    state.setdefault("nodes", {})
                    state["nodes"][nid] = {
                        **state["nodes"].get(nid, {"id": nid}),
                        "status":     "running",
                        "started_at": data.get("ts"),
                    }

            case "NODE_COMPLETED":
                nid = data.get("node")
                if nid:
                    state.setdefault("nodes", {})
                    state["nodes"][nid] = {
                        **state["nodes"].get(nid, {"id": nid}),
                        "status":      "completed",
                        "duration_ms": int((data.get("duration_s") or 0) * 1_000),
                        "tokens_in":   data.get("tokens_in"),
                        "tokens_out":  data.get("tokens_out"),
                        "cost_usd":    data.get("cost_usd"),
                    }

            case "NODE_FAILED":
                nid = data.get("node")
                if nid:
                    state.setdefault("nodes", {})
                    state["nodes"][nid] = {
                        **state["nodes"].get(nid, {"id": nid}),
                        "status": "failed",
                        "error":  data.get("error"),
                    }

            case "CSS_UPDATE":
                state["css_scores"] = {
                    "content": data.get("content", 0.0),
                    "style":   data.get("style",   0.0),
                    "source":  data.get("source",  0.0),
                }

            case "BUDGET_UPDATE":
                state["budget_spent"]         = data.get("spent", 0.0)
                state["budget_remaining_pct"] = data.get("remaining_pct", 100.0)

            case "SECTION_APPROVED":
                idx = data.get("section_idx")
                for s in state.get("sections", []):
                    if s.get("idx") == idx:
                        s["approved"] = True
                        break

            case "OSCILLATION_DETECTED":
                state["oscillation_detected"] = True
                state["oscillation_type"]     = data.get("type")

            case "HARD_STOP":
                state["hard_stop_fired"] = True

            case "PIPELINE_STARTED":
                state["status"] = "running"

            case "PIPELINE_DONE":
                state["status"] = "completed"

            case "PIPELINE_FAILED":
                state["status"] = "failed"

            case "PIPELINE_CANCELLED":
                state["status"] = "cancelled"

        await self.redis.set(state_key, json.dumps(state), ex=86_400)
