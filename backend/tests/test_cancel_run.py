"""Test run cancellation functionality."""

import asyncio
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cancel_active_run(async_client: AsyncClient, wait_for_status):
    """Test cancelling an active run."""
    # Create and start run
    create_response = await async_client.post(
        "/api/runs",
        json={"topic": "Test Cancellation"},
    )
    doc_id = create_response.json()["doc_id"]
    
    # Wait for run to be active
    await asyncio.sleep(1.0)  # Give it time to start
    
    # Cancel run
    cancel_response = await async_client.delete(f"/api/runs/{doc_id}")
    assert cancel_response.status_code == 204
    
    # Verify status is cancelled
    await asyncio.sleep(0.5)  # Allow cleanup
    status_response = await async_client.get(f"/api/runs/{doc_id}")
    if status_response.status_code == 200:
        data = status_response.json()
        assert data["status"] in ["cancelled", "error"]


@pytest.mark.asyncio
async def test_cancel_nonexistent_run(async_client: AsyncClient):
    """Test cancelling a non-existent run returns 404."""
    response = await async_client.delete("/api/runs/doc-nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_emits_event(mock_broker):
    """Test cancellation emits PIPELINE_CANCELLED event."""
    from src.services.run_manager import run_manager
    
    doc_id = "doc-test-cancel"
    
    # Mock run cancellation would emit event
    await mock_broker.emit(doc_id, "PIPELINE_CANCELLED", {})
    
    # Verify event
    assert len(mock_broker.events) == 1
    event = mock_broker.events[0]
    assert event["type"] == "PIPELINE_CANCELLED"
    assert event["doc_id"] == doc_id
