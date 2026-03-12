"""Unit tests for Critic node."""

import pytest
import json
from unittest.mock import AsyncMock, patch

from src.graph.nodes.critic_node import (
    critic_node,
    _parse_feedback,
    APPROVAL_THRESHOLDS,
    MAX_ITERATIONS,
)
from src.models.state import build_initial_state, Section
from src.llm.client import LLMResponse


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_approves_high_score():
    """Test Critic approves section with score >= threshold."""
    # Build state with completed section
    state = build_initial_state(
        doc_id="test-doc",
        topic="Test",
        target_words=1000,
        quality_preset="Balanced",
    )
    state["sections"] = [
        Section(
            title="Introduction",
            scope="Context",
            target_words=1000,
            content="Test content [1][2].",
            word_count=1000,
        )
    ]
    state["current_section"] = 0
    
    # Mock Critic feedback (score 7.5 >= 7.0 threshold)
    feedback_json = json.dumps({
        "score": 7.5,
        "scores_breakdown": {"citations": 8, "coherence": 7},
        "verdict": "APPROVE",
        "issues": [],
        "suggestions": [],
        "strengths": ["Good citations"],
    })
    
    mock_response = LLMResponse(
        content=feedback_json,
        model="mock-model",
        tokens_in=500,
        tokens_out=100,
        cost_usd=0.005,
        latency_s=1.0,
    )
    
    with patch("src.graph.nodes.critic_node.get_llm_client") as mock_client:
        mock_client.return_value.chat = AsyncMock(return_value=mock_response)
        
        result = await critic_node(state)
    
    # Assertions
    assert result["sections"][0].status == "complete"
    assert result["sections"][0].final_score == 7.5
    assert "rewrite_required" not in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_critic_requests_rewrite_low_score():
    """Test Critic requests rewrite when score < threshold."""
    state = build_initial_state(
        doc_id="test-doc",
        topic="Test",
        target_words=1000,
        quality_preset="Balanced",
    )
    state["sections"] = [
        Section(
            title="Introduction",
            scope="Context",
            target_words=1000,
            content="Bad content.",
            word_count=50,
        )
    ]
    state["current_section"] = 0
    
    # Mock feedback (score 5.5 < 7.0 threshold)
    feedback_json = json.dumps({
        "score": 5.5,
        "verdict": "REWRITE",
        "issues": ["Too short", "No citations"],
        "suggestions": ["Add more content"],
        "strengths": [],
    })
    
    mock_response = LLMResponse(
        content=feedback_json,
        model="mock-model",
        tokens_in=500,
        tokens_out=100,
        cost_usd=0.005,
        latency_s=1.0,
    )
    
    with patch("src.graph.nodes.critic_node.get_llm_client") as mock_client:
        mock_client.return_value.chat = AsyncMock(return_value=mock_response)
        
        result = await critic_node(state)
    
    # Assertions
    assert result["rewrite_required"] is True
    assert result["sections"][0].iterations == 1
    assert result["sections"][0].feedback["score"] == 5.5


@pytest.mark.unit
def test_parse_feedback_valid_json():
    """Test parsing of valid Critic feedback JSON."""
    feedback_json = json.dumps({
        "score": 8.0,
        "verdict": "APPROVE",
        "issues": [],
        "suggestions": [],
        "strengths": ["Excellent"],
    })
    
    feedback = _parse_feedback(feedback_json)
    
    assert feedback["score"] == 8.0
    assert feedback["verdict"] == "APPROVE"


@pytest.mark.unit
def test_parse_feedback_invalid_score():
    """Test rejection of invalid score (outside 0-10)."""
    feedback_json = json.dumps({
        "score": 15.0,  # Invalid
        "verdict": "APPROVE",
        "issues": [],
        "suggestions": [],
    })
    
    with pytest.raises(ValueError, match="Invalid score"):
        _parse_feedback(feedback_json)
