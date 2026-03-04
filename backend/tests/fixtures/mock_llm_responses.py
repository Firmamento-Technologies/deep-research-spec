"""Mock LLM responses for testing."""

import json

# Planner outline
MOCK_OUTLINE = json.dumps({
    "sections": [
        {"title": "Introduction", "scope": "Context and objectives", "target_words": 600},
        {"title": "Background", "scope": "State of the art", "target_words": 1200},
        {"title": "Methods", "scope": "Research approach", "target_words": 1500},
        {"title": "Results", "scope": "Key findings", "target_words": 1000},
        {"title": "Conclusion", "scope": "Summary and future work", "target_words": 700},
    ]
})

# Writer content
MOCK_CONTENT = """
## Introduction

Machine learning represents a transformative approach to data analysis [1][2].
Recent advances in deep learning have enabled breakthrough applications [3][4].

Neural networks, inspired by biological systems, form the foundation of modern ML [5].
These systems learn patterns from data without explicit programming [6][7].
"""

# Critic feedback (approve)
MOCK_FEEDBACK_APPROVE = json.dumps({
    "score": 7.5,
    "scores_breakdown": {
        "citations": 8.0,
        "coherence": 7.5,
        "depth": 7.0,
        "accuracy": 8.0,
        "structure": 7.5,
        "completeness": 7.0,
        "originality": 7.5,
    },
    "verdict": "APPROVE",
    "issues": [],
    "suggestions": ["Consider adding more specific examples"],
    "strengths": ["Excellent citation coverage", "Clear structure"],
})

# Critic feedback (rewrite)
MOCK_FEEDBACK_REWRITE = json.dumps({
    "score": 5.5,
    "scores_breakdown": {
        "citations": 4.0,
        "coherence": 6.0,
        "depth": 5.0,
        "accuracy": 6.0,
        "structure": 6.0,
        "completeness": 5.0,
        "originality": 6.0,
    },
    "verdict": "REWRITE",
    "issues": [
        "Insufficient citations (only 2 sources)",
        "Content too superficial",
        "Missing key concepts",
    ],
    "suggestions": [
        "Add at least 5 more citations",
        "Expand on neural network architectures",
        "Include recent research (2024-2026)",
    ],
    "strengths": ["Clear writing style"],
})
