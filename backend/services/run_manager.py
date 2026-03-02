import asyncio
import uuid
import json
from datetime import datetime, timezone
from services.sse_broker import SSEBroker


class RunManager:
    """
    Manages pipeline execution lifecycle.
    Bridges FastAPI API endpoints and LangGraph pipeline (src/graph/graph.py).
    TODO: STEP 5 — full LangGraph integration
    """

    def __init__(self, redis_client, sse_broker: SSEBroker):
        self.redis = redis_client
        self.broker = sse_broker

    async def start_run(self, params: dict) -> str:
        doc_id = str(uuid.uuid4())

        initial_state = {
            "docId": doc_id,
            "topic": params["topic"],
            "status": "initializing",
            "qualityPreset": params["quality_preset"],
            "targetWords": params["target_words"],
            "maxBudget": params["max_budget"],
            "budgetSpent": 0.0,
            "budgetRemainingPct": 100.0,
            "totalSections": 0,
            "currentSection": 0,
            "currentIteration": 0,
            "nodes": {},
            "cssScores": {"content": 0.0, "style": 0.0, "source": 0.0},
            "juryVerdicts": [],
            "sections": [],
            "shineActive": False,
            "rlmMode": False,
            "hardStopFired": False,
            "oscillationDetected": False,
            "forceApprove": False,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }

        await self.redis.set(f"run:{doc_id}:state", json.dumps(initial_state), ex=86400)
        await self.redis.sadd("runs:all", doc_id)

        # Start pipeline in background
        asyncio.create_task(self._run_pipeline(doc_id, params))
        return doc_id

    async def _run_pipeline(self, doc_id: str, params: dict):
        """
        TODO: STEP 5 — replace with actual LangGraph invocation:
            from src.graph.graph import build_graph
            graph = build_graph()
            await graph.ainvoke(initial_state)
        """
        await self.broker.emit(doc_id, "NODE_STARTED", {"node": "preflight"})
        await asyncio.sleep(0.5)
        await self.broker.emit(doc_id, "NODE_COMPLETED", {"node": "preflight", "duration_s": 0.5})
