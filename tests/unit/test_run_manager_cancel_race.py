import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import importlib

pytest.importorskip("sqlalchemy")
run_manager_module = importlib.import_module("services.run_manager")


class FakeDB:
    async def execute(self, _query):
        return None

    async def commit(self):
        return None


async def fake_get_db():
    yield FakeDB()


@pytest.mark.asyncio
async def test_cancel_run_handles_cleanup_race(monkeypatch):
    manager = run_manager_module.RunManager()
    doc_id = "doc-race-1"

    async def task_body():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Simulate _run_graph_task finally cleanup winning the race.
            run_manager_module.active_runs.pop(doc_id, None)
            raise

    task = asyncio.create_task(task_body())
    run_manager_module.active_runs[doc_id] = {"task": task}

    monkeypatch.setattr(run_manager_module, "get_db", fake_get_db)

    await manager.cancel_run(doc_id)

    assert doc_id not in run_manager_module.active_runs
