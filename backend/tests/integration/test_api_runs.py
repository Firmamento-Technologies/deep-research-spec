"""Integration tests for /api/runs endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_run(async_client: AsyncClient):
    """Test POST /api/runs creates new run."""
    response = await async_client.post(
        "/api/runs",
        json={
            "topic": "Quantum Computing",
            "quality_preset": "Economy",
            "target_words": 2000,
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "doc_id" in data
    assert data["status"] == "pending"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_run_status(async_client: AsyncClient):
    """Test GET /api/runs/{doc_id} returns status."""
    # Create run first
    create_resp = await async_client.post(
        "/api/runs",
        json={"topic": "Test", "quality_preset": "Economy"},
    )
    doc_id = create_resp.json()["doc_id"]
    
    # Get status
    response = await async_client.get(f"/api/runs/{doc_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["doc_id"] == doc_id
    assert "status" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_run_invalid_input(async_client: AsyncClient):
    """Test POST /api/runs rejects invalid input."""
    response = await async_client.post(
        "/api/runs",
        json={
            "topic": "",  # Empty topic
            "quality_preset": "Invalid",  # Invalid preset
        },
    )
    
    assert response.status_code == 422  # Unprocessable Entity


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_nonexistent_run(async_client: AsyncClient):
    """Test GET /api/runs/{doc_id} returns 404 for missing run."""
    response = await async_client.get("/api/runs/nonexistent-doc-id")
    
    assert response.status_code == 404
