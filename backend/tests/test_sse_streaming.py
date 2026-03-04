"""Test SSE streaming functionality."""

import asyncio
import json
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sse_stream_connection(async_client: AsyncClient):
    """Test SSE stream connects successfully."""
    # Create run
    create_response = await async_client.post(
        "/api/runs",
        json={"topic": "Test"},
    )
    doc_id = create_response.json()["doc_id"]
    
    # Connect to SSE stream
    async with async_client.stream(
        "GET",
        f"/api/runs/{doc_id}/stream",
        timeout=5.0,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"


@pytest.mark.asyncio
async def test_sse_stream_receives_events(async_client: AsyncClient, mock_broker):
    """Test SSE stream receives emitted events."""
    doc_id = "doc-test-123"
    
    # Emit test events
    await mock_broker.emit(doc_id, "TEST_EVENT_1", {"data": "test1"})
    await mock_broker.emit(doc_id, "TEST_EVENT_2", {"data": "test2"})
    
    # Subscribe and collect events
    events = []
    async for event in mock_broker.subscribe(doc_id):
        events.append(event)
        if len(events) >= 2:
            break
    
    assert len(events) == 2
    assert events[0]["type"] == "TEST_EVENT_1"
    assert events[1]["type"] == "TEST_EVENT_2"


@pytest.mark.asyncio
async def test_sse_buffered_events(mock_broker):
    """Test SSE buffer replays events for late subscribers."""
    doc_id = "doc-test-buffer"
    
    # Emit events before subscription
    await mock_broker.emit(doc_id, "EVENT_1", {})
    await mock_broker.emit(doc_id, "EVENT_2", {})
    
    # Subscribe (should receive buffered events)
    events = []
    async for event in mock_broker.subscribe(doc_id):
        events.append(event)
        if len(events) >= 2:
            break
    
    assert len(events) == 2
    assert events[0]["type"] == "EVENT_1"
    assert events[1]["type"] == "EVENT_2"


@pytest.mark.asyncio
async def test_sse_event_format():
    """Test SSE events have correct format."""
    from services.sse_broker import get_broker
    
    broker = get_broker()
    doc_id = "doc-test-format"
    
    # Emit event
    await broker.emit(doc_id, "NODE_STARTED", {"node": "planner"})
    
    # Check buffer
    assert doc_id in broker._event_buffers
    events = list(broker._event_buffers[doc_id])
    assert len(events) >= 1
    
    event = events[0]
    assert "type" in event
    assert "payload" in event
    assert "timestamp" in event
    assert "doc_id" in event
    assert event["type"] == "NODE_STARTED"
    assert event["payload"]["node"] == "planner"
