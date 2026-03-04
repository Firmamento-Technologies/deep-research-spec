"""Unit tests for Planner node."""

import pytest
import json
from unittest.mock import AsyncMock, patch

from src.graph.nodes.planner_node import (
    planner_node,
    _parse_and_validate,
    _load_prompt,
)
from src.models.state import build_initial_state
from src.llm.client import LLMResponse


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planner_generates_valid_outline():
    """Test Planner generates 4-12 sections with correct structure."""
    # Mock LLM response
    outline_json = json.dumps({
        "sections": [
            {"title": "Introduction", "scope": "Context", "target_words": 800},
            {"title": "Background", "scope": "State of art", "target_words": 1200},
            {"title": "Methods", "scope": "Approach", "target_words": 1500},
            {"title": "Results", "scope": "Findings", "target_words": 1000},
            {"title": "Conclusion", "scope": "Summary", "target_words": 500},
        ]
    })
    
    mock_response = LLMResponse(
        content=outline_json,
        model="mock-model",
        tokens_in=100,
        tokens_out=200,
        cost_usd=0.002,
        latency_s=0.5,
    )
    
    # Build state
    state = build_initial_state(
        doc_id="test-doc",
        topic="AI Ethics",
        target_words=5000,
        quality_preset="Balanced",
    )
    
    # Mock LLM client
    with patch("src.graph.nodes.planner_node.get_llm_client") as mock_client:
        mock_client.return_value.chat = AsyncMock(return_value=mock_response)
        
        # Run planner
        result = await planner_node(state)
    
    # Assertions
    assert "outline" in result
    assert len(result["outline"]) == 5
    assert result["total_sections"] == 5
    
    # Check section structure
    section = result["outline"][0]
    assert section.title == "Introduction"
    assert section.scope == "Context"
    assert section.target_words == 800


@pytest.mark.unit
def test_parse_and_validate_correct_word_count():
    """Test outline word count validation and auto-adjustment."""
    outline_json = json.dumps({
        "sections": [
            {"title": "Intro", "scope": "...", "target_words": 1000},
            {"title": "Body", "scope": "...", "target_words": 2000},
            {"title": "Conclusion", "scope": "...", "target_words": 1000},
        ]
    })
    
    sections = _parse_and_validate(outline_json, target_words=3000, quality_preset="Balanced")
    
    # Total should be close to 3000 (within 15%)
    total = sum(s.target_words for s in sections)
    assert 2550 <= total <= 3450  # 3000 ± 15%


@pytest.mark.unit
def test_parse_and_validate_rejects_too_few_sections():
    """Test rejection of outlines with < 4 sections."""
    outline_json = json.dumps({
        "sections": [
            {"title": "Intro", "scope": "...", "target_words": 1500},
            {"title": "Body", "scope": "...", "target_words": 1500},
        ]
    })
    
    with pytest.raises(ValueError, match="sections"):
        _parse_and_validate(outline_json, target_words=3000, quality_preset="Balanced")


@pytest.mark.unit
def test_parse_and_validate_rejects_invalid_json():
    """Test rejection of malformed JSON."""
    with pytest.raises(ValueError, match="Invalid JSON"):
        _parse_and_validate("not valid json", target_words=3000, quality_preset="Balanced")
