"""Unit tests for LLM client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.llm.client import (
    LLMClient,
    get_llm_client,
    LLMError,
    BudgetExceededError,
    _check_budget,
    _update_budget,
)
from src.llm.pricing import cost_usd


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_client_successful_call():
    """Test successful LLM API call."""
    client = LLMClient(
        api_key="test-key",
        model_assignments={"planner": "gpt-4o"},
    )
    
    # Mock HTTP response
    mock_response = {
        "choices": [{
            "message": {"content": "Test response"},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
        },
        "model": "gpt-4o",
        "_latency_s": 0.5,
    }
    
    with patch.object(client._http, "post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
        )
        
        response = await client.chat(
            messages=[{"role": "user", "content": "test"}],
            node_id="planner",
        )
    
    assert response.content == "Test response"
    assert response.tokens_in == 100
    assert response.tokens_out == 50
    assert response.cost_usd > 0


@pytest.mark.unit
def test_budget_check_raises_when_exceeded():
    """Test budget guard raises BudgetExceededError."""
    state = {
        "budget_spent": 10.0,
        "max_budget": 10.0,
    }
    
    with pytest.raises(BudgetExceededError):
        _check_budget(state, "gpt-4o")


@pytest.mark.unit
def test_budget_update_increments_spent():
    """Test budget update adds cost to budget_spent."""
    state = {
        "budget_spent": 1.0,
        "max_budget": 10.0,
    }
    
    from src.llm.client import LLMResponse
    response = LLMResponse(
        content="test",
        model="gpt-4o",
        tokens_in=100,
        tokens_out=50,
        cost_usd=0.5,
        latency_s=1.0,
    )
    
    _update_budget(state, response)
    
    assert state["budget_spent"] == 1.5
    assert state["budget_remaining_pct"] < 100


@pytest.mark.unit
def test_cost_calculation():
    """Test USD cost calculation for various models."""
    # GPT-4o: $2.50 per 1M input, $10 per 1M output
    cost = cost_usd("openai/gpt-4o", tokens_in=1000, tokens_out=500)
    expected = (1000 * 2.50 / 1_000_000) + (500 * 10.00 / 1_000_000)
    assert abs(cost - expected) < 0.0001
