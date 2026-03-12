# run_manager — bridge between FastAPI background tasks and the LangGraph
# pipeline in src/. Called by POST /api/runs via BackgroundTasks.

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.sse_broker import SSEBroker

# Make src/ importable: add /app (parent of src/) to sys.path so that the
# `from src.graph.X import Y` absolute imports used in graph.py and all node
# files resolve correctly inside the Docker container.
_app_path = os.path.join(os.path.dirname(__file__), "..")
if _app_path not in sys.path:
    sys.path.insert(0, _app_path)

# Also add project root (parent of backend/) for src/ imports in local dev
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logger = logging.getLogger(__name__)


class RunManager:
    """Manages active pipeline runs, bridging API requests to LangGraph execution."""

    def __init__(self) -> None:
        self._active_runs: Dict[str, asyncio.Task] = {}
        self._run_states: Dict[str, Dict[str, Any]] = {}

    async def start_run(
        self,
        doc_id: str,
        topic: str,
        quality_preset: str = "Balanced",
        target_words: int = 5000,
        max_budget: float = 50.0,
        style_profile: str = "academic",
        knowledge_space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a new pipeline run as a background task."""
        from services.sse_broker import get_broker

        if doc_id in self._active_runs and not self._active_runs[doc_id].done():
            raise ValueError(f"Run {doc_id} is already active")

        broker = get_broker()
        params = {
            "topic": topic,
            "quality_preset": quality_preset,
            "target_words": target_words,
            "max_budget": max_budget,
            "style_profile": style_profile,
            "knowledge_space_id": knowledge_space_id,
        }

        self._run_states[doc_id] = {
            "doc_id": doc_id,
            "topic": topic,
            "status": "initializing",
            "quality_preset": quality_preset,
            "target_words": target_words,
            "max_budget": max_budget,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_cost": 0.0,
        }

        task = asyncio.create_task(self._execute_run(doc_id, params, broker))
        self._active_runs[doc_id] = task

        return self._run_states[doc_id]

    async def _execute_run(
        self, doc_id: str, params: dict, broker: "SSEBroker"
    ) -> None:
        """Execute the pipeline and update state on completion."""
        try:
            self._run_states[doc_id]["status"] = "running"
            await _run_pipeline(doc_id, params, broker)
            self._run_states[doc_id]["status"] = "completed"
            self._run_states[doc_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        except asyncio.CancelledError:
            self._run_states[doc_id]["status"] = "cancelled"
        except Exception as exc:
            logger.error("[%s] Pipeline failed: %s", doc_id, exc, exc_info=True)
            self._run_states[doc_id]["status"] = "failed"
            self._run_states[doc_id]["error"] = str(exc)

    async def get_run_status(self, doc_id: str) -> Dict[str, Any]:
        """Get current status of a run."""
        if doc_id not in self._run_states:
            raise ValueError(f"Run {doc_id} not found")
        return self._run_states[doc_id]

    async def cancel_run(self, doc_id: str) -> None:
        """Cancel an active run."""
        task = self._active_runs.get(doc_id)
        if task and not task.done():
            task.cancel()
            self._run_states[doc_id]["status"] = "cancelling"
            logger.info("[%s] Run cancellation requested", doc_id)
        else:
            raise ValueError(f"Run {doc_id} is not active")

    async def resume_run(
        self, doc_id: str, payload: dict, approval_type: str = "outline"
    ) -> None:
        """Resume a paused run by submitting HITL approval."""
        from services.sse_broker import get_broker

        broker = get_broker()
        if approval_type == "outline":
            await broker.submit_outline_approval(doc_id, payload)
        elif approval_type == "section":
            section_idx = payload.get("section_idx", 0)
            await broker.submit_section_approval(doc_id, section_idx, payload)
        else:
            raise ValueError(f"Unknown approval type: {approval_type}")


async def _run_pipeline(doc_id: str, params: dict, broker: "SSEBroker") -> None:
    """
    Start the LangGraph pipeline for a given run.
    Emits SSE events via broker throughout execution.

    Invokes build_graph().ainvoke() from src/graph/graph.py.
    Falls back to a stub HUMAN_REQUIRED (outline approval) only if the
    import fails (e.g. during local development without src/ mounted).
    """
    try:
        await broker.emit(doc_id, "PIPELINE_STARTED", {"doc_id": doc_id})

        try:
            from src.graph.graph import build_graph  # src/graph/graph.py
            graph = build_graph()
            initial = {
                "doc_id":          doc_id,
                "topic":           params["topic"],
                "quality_preset":  params.get("quality_preset", "Balanced"),
                "target_words":    params.get("target_words", 5_000),
                "max_budget":      params.get("max_budget", 50.0),
                "broker":          broker,
            }
            await graph.ainvoke(initial)

        except ImportError:
            # src/ not available — run a minimal stub sequence so the
            # frontend can exercise layout and HITL without the full pipeline.
            await asyncio.sleep(0.5)
            await broker.emit(doc_id, "NODE_STARTED",   {"node": "preflight"})
            await asyncio.sleep(0.8)
            await broker.emit(doc_id, "NODE_COMPLETED", {"node": "preflight", "duration_s": 0.8})

            await broker.emit(doc_id, "NODE_STARTED",   {"node": "planner"})
            await asyncio.sleep(1.2)
            await broker.emit(doc_id, "NODE_COMPLETED", {"node": "planner",   "duration_s": 1.2})

            # Trigger outline HITL
            await broker.emit(doc_id, "HUMAN_REQUIRED", {
                "type": "outline_approval",
                "payload": {
                    "sections": [
                        {"title": "Introduzione",     "scope": "Contesto e obiettivi",    "target_words": 800},
                        {"title": "Background",        "scope": "Stato dell'arte",          "target_words": 1500},
                        {"title": "Metodologia",       "scope": "Approccio scelto",         "target_words": 1200},
                        {"title": "Risultati",         "scope": "Dati e analisi",           "target_words": 2000},
                        {"title": "Conclusioni",       "scope": "Implicazioni e limiti",   "target_words": 500},
                    ]
                },
            })

        await broker.emit(doc_id, "PIPELINE_COMPLETED", {"doc_id": doc_id})

    except asyncio.CancelledError:
        await broker.emit(doc_id, "PIPELINE_CANCELLED", {"doc_id": doc_id})
    except Exception as exc:
        await broker.emit(doc_id, "PIPELINE_FAILED", {"doc_id": doc_id, "error": str(exc)})
        raise


# Singleton instance
run_manager = RunManager()
