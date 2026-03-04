"""E2E test for complete pipeline."""

import pytest
import asyncio
from httpx import AsyncClient


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.slow
async def test_complete_pipeline_economy(async_client: AsyncClient, wait_for_status):
    """Test full pipeline with Economy preset (minimal rewrites)."""
    # Create run
    create_resp = await async_client.post(
        "/api/runs",
        json={
            "topic": "Machine Learning Basics",
            "quality_preset": "Economy",
            "target_words": 1500,
        },
    )
    
    assert create_resp.status_code == 201
    doc_id = create_resp.json()["doc_id"]
    
    # Wait for completion (or timeout)
    try:
        final_state = await wait_for_status(
            async_client,
            doc_id,
            target_status="complete",
            timeout=120.0,  # 2 minutes
        )
    except TimeoutError:
        # Pipeline didn't complete in time
        status_resp = await async_client.get(f"/api/runs/{doc_id}")
        pytest.fail(
            f"Pipeline did not complete. Final status: {status_resp.json()['status']}"
        )
    
    # Assertions
    assert final_state["status"] == "complete"
    assert "sections" in final_state
    assert len(final_state["sections"]) >= 4
    
    # Check budget tracking
    assert final_state["budget_spent"] > 0
    assert final_state["budget_spent"] <= final_state["max_budget"]
