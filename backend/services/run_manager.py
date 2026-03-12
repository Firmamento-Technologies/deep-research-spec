# run_manager — bridge between FastAPI background tasks and the LangGraph
# pipeline in src/. Called by POST /api/runs via BackgroundTasks.

import asyncio
import json
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.sse_broker import SSEBroker

# Make src/ importable: add /app (parent of src/) to sys.path so that the
# `from src.graph.X import Y` absolute imports used in graph.py and all node
# files resolve correctly inside the Docker container.
_app_path = os.path.join(os.path.dirname(__file__), "..")
if _app_path not in sys.path:
    sys.path.insert(0, _app_path)


async def run_pipeline(doc_id: str, params: dict, broker: "SSEBroker") -> None:
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

    except asyncio.CancelledError:
        await broker.emit(doc_id, "PIPELINE_CANCELLED", {"doc_id": doc_id})
    except Exception as exc:
        await broker.emit(doc_id, "PIPELINE_FAILED", {"doc_id": doc_id, "error": str(exc)})
