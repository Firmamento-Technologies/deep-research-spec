import json
from datetime import datetime, timezone


class SSEBroker:
    """
    Bridge between LangGraph pipeline nodes and SSE clients.
    Publishes events to Redis pub/sub: run:{doc_id}:events
    Updates persistent state in Redis: run:{doc_id}:state

    Usage in every LangGraph node:
        await broker.emit(doc_id, "NODE_STARTED", {"node": "researcher"})
        # ... node logic ...
        await broker.emit(doc_id, "NODE_COMPLETED", {"node": "researcher", "duration_s": elapsed})
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def emit(self, doc_id: str, event_type: str, data: dict):
        payload = json.dumps({
            "event": event_type,
            "data": {**data, "ts": datetime.now(timezone.utc).isoformat()},
        })
        await self.redis.publish(f"run:{doc_id}:events", payload)
        await self._update_state(doc_id, event_type, data)

    async def _update_state(self, doc_id: str, event_type: str, data: dict):
        state_key = f"run:{doc_id}:state"
        raw = await self.redis.get(state_key)
        if not raw:
            return
        state = json.loads(raw)

        if event_type == "NODE_STARTED":
            node_id = data.get("node")
            if node_id:
                state.setdefault("nodes", {})[node_id] = {
                    **state["nodes"].get(node_id, {}),
                    "status": "running",
                    "startedAt": data.get("ts"),
                }
        elif event_type == "NODE_COMPLETED":
            node_id = data.get("node")
            if node_id:
                state["nodes"][node_id] = {
                    **state["nodes"].get(node_id, {}),
                    "status": "completed",
                    "completedAt": data.get("ts"),
                    "durationMs": int(data.get("duration_s", 0) * 1000),
                    "tokensIn": data.get("tokens_in"),
                    "tokensOut": data.get("tokens_out"),
                    "costUsd": data.get("cost_usd"),
                }
        elif event_type == "NODE_FAILED":
            node_id = data.get("node")
            if node_id:
                state["nodes"][node_id] = {
                    **state["nodes"].get(node_id, {}),
                    "status": "failed",
                    "error": data.get("error"),
                }
        elif event_type == "CSS_UPDATE":
            state["cssScores"] = data
        elif event_type == "BUDGET_UPDATE":
            state["budgetSpent"] = data.get("spent", 0)
            state["budgetRemainingPct"] = data.get("remaining_pct", 100)
        elif event_type == "SECTION_APPROVED":
            state["currentSection"] = data.get("section_idx", 0) + 1
        elif event_type == "OSCILLATION_DETECTED":
            state["oscillationDetected"] = True
            state["oscillationType"] = data.get("type")
        elif event_type == "PIPELINE_DONE":
            state["status"] = "completed"
            state["outputPaths"] = data.get("output_paths", {})

        await self.redis.set(state_key, json.dumps(state), ex=86400)
