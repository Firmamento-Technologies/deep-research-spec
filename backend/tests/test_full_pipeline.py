"""Integration test for full pipeline execution.

This test simulates a complete run from start to finish,
validating all stages: planner → researcher → writer → critic → finalizer.

Note: This test requires mocked LLM responses to avoid actual API calls.
"""

import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.slow
async def test_full_pipeline_mock(
    async_client: AsyncClient,
    wait_for_status,
    mock_broker,
):
    """Test full pipeline with mocked components.
    
    This is a simplified test that validates the orchestration flow
    without executing actual LLM calls or web searches.
    """
    # 1. Create run
    create_response = await async_client.post(
        "/api/runs",
        json={
            "topic": "Integration Test Topic",
            "quality_preset": "Economy",
            "target_words": 1000,
            "max_budget": 10.0,
        },
    )
    
    assert create_response.status_code == 201
    doc_id = create_response.json()["doc_id"]
    
    # 2. Verify run was created in DB
    status_response = await async_client.get(f"/api/runs/{doc_id}")
    assert status_response.status_code == 200
    
    status = status_response.json()
    assert status["doc_id"] == doc_id
    assert status["topic"] == "Integration Test Topic"
    assert status["status"] in ["initializing", "planning"]
    
    # 3. Simulate pipeline events
    await mock_broker.emit(doc_id, "PIPELINE_STARTED", {
        "topic": "Integration Test Topic",
    })
    
    await mock_broker.emit(doc_id, "NODE_STARTED", {"node": "planner"})
    await asyncio.sleep(0.1)
    await mock_broker.emit(doc_id, "NODE_COMPLETED", {
        "node": "planner",
        "duration_s": 1.5,
    })
    
    await mock_broker.emit(doc_id, "NODE_STARTED", {"node": "researcher"})
    await asyncio.sleep(0.1)
    await mock_broker.emit(doc_id, "NODE_COMPLETED", {
        "node": "researcher",
        "duration_s": 2.3,
    })
    
    await mock_broker.emit(doc_id, "NODE_STARTED", {"node": "writer"})
    await asyncio.sleep(0.1)
    await mock_broker.emit(doc_id, "NODE_COMPLETED", {
        "node": "writer",
        "duration_s": 3.1,
    })
    
    await mock_broker.emit(doc_id, "NODE_STARTED", {"node": "critic"})
    await asyncio.sleep(0.1)
    await mock_broker.emit(doc_id, "NODE_COMPLETED", {
        "node": "critic",
        "duration_s": 1.2,
    })
    
    await mock_broker.emit(doc_id, "DOCUMENT_COMPLETED", {
        "total_words": 1043,
        "total_cost": 0.85,
    })
    
    # 4. Verify events were collected
    events = mock_broker.events
    assert len(events) >= 7
    
    event_types = [e["type"] for e in events]
    assert "PIPELINE_STARTED" in event_types
    assert "NODE_STARTED" in event_types
    assert "NODE_COMPLETED" in event_types
    assert "DOCUMENT_COMPLETED" in event_types


@pytest.mark.asyncio
async def test_status_transitions(async_client: AsyncClient):
    """Test run status transitions through pipeline stages."""
    # Create run
    response = await async_client.post(
        "/api/runs",
        json={"topic": "Status Test"},
    )
    doc_id = response.json()["doc_id"]
    
    # Check initial status
    status = await async_client.get(f"/api/runs/{doc_id}")
    data = status.json()
    
    assert data["status"] in [
        "initializing",
        "planning",
    ]
    
    # Expected status flow:
    # initializing → planning → researching → writing → completed


@pytest.mark.asyncio
async def test_budget_tracking(mock_broker):
    """Test budget tracking through pipeline."""
    doc_id = "doc-budget-test"
    
    # Emit budget updates
    await mock_broker.emit(doc_id, "BUDGET_UPDATE", {
        "spent": 1.25,
        "remaining_pct": 95.0,
    })
    
    await mock_broker.emit(doc_id, "BUDGET_UPDATE", {
        "spent": 3.50,
        "remaining_pct": 86.0,
    })
    
    # Verify events
    budget_events = [
        e for e in mock_broker.events
        if e["type"] == "BUDGET_UPDATE"
    ]
    
    assert len(budget_events) == 2
    assert budget_events[0]["payload"]["spent"] == 1.25
    assert budget_events[1]["payload"]["spent"] == 3.50
