"""Judge R — Reasoning quality evaluator (§8.1).

Evaluates: logical consistency, argument structure, causality claims,
contradictions, and overall reasoning quality of the draft.
"""
from __future__ import annotations

from src.graph.nodes.jury_base import Judge, VERDICT_SCHEMA


REASONING_RUBRIC = """\
You are a Reasoning Judge evaluating the logical quality of a document section.

Evaluate these dimensions (score each 0.0-1.0):
- **logical_consistency**: No contradictions within the text
- **argument_structure**: Claims follow logically from premises
- **causality_validity**: Cause-effect claims are properly supported
- **completeness**: Key aspects of the scope are addressed
- **nuance**: Appropriate hedging, limitations acknowledged

VETO if you find:
- A logical contradiction (claim A directly contradicts claim B)
- A fabricated logical chain (conclusion doesn't follow from premises)

Be strict but fair. A score ≥0.75 = pass."""


class JudgeR(Judge):
    """Reasoning quality judge (§8.1)."""

    def evaluate(self, draft: str, sources: list[dict], section_scope: str) -> dict:
        system_blocks = [
            {
                "type": "text",
                "text": VERDICT_SCHEMA,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": REASONING_RUBRIC,
                "cache_control": {"type": "ephemeral"},
            },
        ]

        source_titles = "\n".join(
            f"- [{s.get('source_id', '?')}] {s.get('title', 'Untitled')}"
            for s in (sources or [])[:20]
        )

        user_prompt = f"""\
Evaluate the REASONING quality of this draft section.

Section scope: {section_scope}

Available sources:
{source_titles}

Draft:
---
{draft[:6000]}
---

Return your evaluation as the JSON structure specified in the system prompt."""

        response = self._call_llm_with_cache(system_blocks, user_prompt)
        verdict = self._parse_verdict(response["text"])

        # Enrich dimension_scores if LLM didn't provide them
        verdict["dimension_scores"].setdefault("logical_consistency", verdict.get("css_contribution", 0.7))
        verdict["dimension_scores"].setdefault("argument_structure", verdict.get("css_contribution", 0.7))

        return verdict
