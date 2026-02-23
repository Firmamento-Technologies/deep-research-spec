"""Judge S — Style quality evaluator (§8.3).

Evaluates: adherence to style profile rules, tone consistency,
readability, formatting compliance, and vocabulary appropriateness.
"""
from __future__ import annotations

from typing import Any

from src.graph.nodes.jury_base import Judge, VERDICT_SCHEMA


STYLE_RUBRIC = """\
You are a Style Judge evaluating whether a document section follows
the required writing style and conventions.

Evaluate these dimensions (score each 0.0-1.0):
- **tone_consistency**: Maintains consistent voice throughout
- **vocabulary_level**: Appropriate for target audience
- **sentence_variety**: Mix of sentence structures
- **readability**: Clear and comprehensible prose
- **formatting_compliance**: Follows document conventions
- **rule_adherence**: Follows specific style rules provided

VETO if you find:
- Plagiarism (copied text without attribution)

Be precise about rule violations. A score ≥0.80 = pass (style is stricter)."""


class JudgeS(Judge):
    """Style quality judge (§8.3)."""

    def __init__(self, slot: str, model: str, style_rules: str = "") -> None:
        super().__init__(slot, model)
        self.style_rules = style_rules

    def evaluate(self, draft: str, sources: list[dict], section_scope: str) -> dict:
        system_blocks = [
            {
                "type": "text",
                "text": VERDICT_SCHEMA,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": STYLE_RUBRIC,
                "cache_control": {"type": "ephemeral"},
            },
        ]

        # Inject style rules if available
        rules_text = self.style_rules or "Follow academic writing conventions."

        user_prompt = f"""\
Evaluate the STYLE quality of this draft section.

Section scope: {section_scope}

Style rules to enforce:
{rules_text}

Draft:
---
{draft[:6000]}
---

Instructions:
1. Check adherence to style rules above
2. Evaluate tone consistency throughout
3. Assess readability and sentence variety
4. Note any formatting violations
5. Flag any potential plagiarism

Return your evaluation as the JSON structure specified in the system prompt."""

        response = self._call_llm_with_cache(system_blocks, user_prompt)
        verdict = self._parse_verdict(response["text"])

        # Enrich dimension_scores
        verdict["dimension_scores"].setdefault("tone_consistency", verdict.get("css_contribution", 0.7))
        verdict["dimension_scores"].setdefault("readability", verdict.get("css_contribution", 0.7))

        return verdict
