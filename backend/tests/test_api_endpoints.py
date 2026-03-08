"""Test REST API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_run_success(async_client: AsyncClient):
    """Test POST /api/runs creates a new run."""
    response = await async_client.post(
        "/api/runs",
        json={
            "topic": "Test Topic",
            "quality_preset": "Balanced",
            "target_words": 3000,
            "max_budget": 25.0,
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert "doc_id" in data
    assert data["status"] == "initializing"
    assert "message" in data


@pytest.mark.asyncio
async def test_create_run_validation_error(async_client: AsyncClient):
    """Test POST /api/runs with invalid data."""
    # Invalid quality preset
    response = await async_client.post(
        "/api/runs",
        json={
            "topic": "Test",
            "quality_preset": "Invalid",
            "target_words": 3000,
        },
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_runs(async_client: AsyncClient):
    """Test GET /api/runs returns list."""
    # Create a run first
    create_response = await async_client.post(
        "/api/runs",
        json={"topic": "Test", "quality_preset": "Economy"},
    )
    assert create_response.status_code == 201
    
    # List runs
    response = await async_client.get("/api/runs")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    
    # Verify structure
    run = data[0]
    assert "doc_id" in run
    assert "topic" in run
    assert "status" in run


@pytest.mark.asyncio
async def test_get_run_status(async_client: AsyncClient):
    """Test GET /api/runs/{doc_id} returns run status."""
    # Create run
    create_response = await async_client.post(
        "/api/runs",
        json={"topic": "Test", "quality_preset": "Balanced"},
    )
    doc_id = create_response.json()["doc_id"]
    
    # Get status
    response = await async_client.get(f"/api/runs/{doc_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["doc_id"] == doc_id
    assert data["topic"] == "Test"
    assert "status" in data
    assert "total_cost" in data
    assert "is_active" in data


@pytest.mark.asyncio
async def test_get_run_not_found(async_client: AsyncClient):
    """Test GET /api/runs/{doc_id} with non-existent doc_id."""
    response = await async_client.get("/api/runs/doc-nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_approve_outline(async_client: AsyncClient):
    """Test POST /api/runs/{doc_id}/approve-outline."""
    # Create run
    create_response = await async_client.post(
        "/api/runs",
        json={"topic": "Test"},
    )
    doc_id = create_response.json()["doc_id"]
    
    # Approve outline
    response = await async_client.post(
        f"/api/runs/{doc_id}/approve-outline",
        json={
            "approved": True,
            "sections": [
                {"title": "Introduction", "scope": "Overview"},
            ],
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_approve_section(async_client: AsyncClient):
    """Test POST /api/runs/{doc_id}/approve-section."""
    create_response = await async_client.post(
        "/api/runs",
        json={"topic": "Test"},
    )
    doc_id = create_response.json()["doc_id"]

    response = await async_client.post(
        f"/api/runs/{doc_id}/approve-section",
        json={
            "section_idx": 0,
            "approved": True,
            "content": "Edited section content",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"



@pytest.mark.asyncio
async def test_cancel_run(async_client: AsyncClient):
    """Test DELETE /api/runs/{doc_id} cancels run."""
    # Create run
    create_response = await async_client.post(
        "/api/runs",
        json={"topic": "Test"},
    )
    doc_id = create_response.json()["doc_id"]
    
    # Cancel run
    response = await async_client.delete(f"/api/runs/{doc_id}")
    assert response.status_code == 204
