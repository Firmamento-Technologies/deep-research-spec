"""Base class for Judge agents (§8).

Each judge evaluates a draft on a specific dimension (Reasoning,
Factual, or Style) and returns a ``JudgeVerdict`` dict.

Provides ``_call_llm_with_cache()`` so that the verdict schema and
rubric are cached via §29.1 across evaluations.
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from src.llm.client import llm_client

logger = logging.getLogger(__name__)


class Judge(ABC):
    """Abstract base for all jury judges (§8)."""

    def __init__(self, slot: str, model: str) -> None:
        self.slot = slot    # R1/R2/R3 / F1/F2/F3 / S1/S2/S3
        self.model = model

    @abstractmethod
    def evaluate(self, draft: str, sources: list[dict], section_scope: str) -> dict:
        """Evaluate the draft and return a JudgeVerdict dict."""
        ...

    def _call_llm_with_cache(
        self, system_blocks: list[dict], user_prompt: str
    ) -> dict:
        """§29.1: Reuse cached system prompt (verdict schema + rubric)."""
        return llm_client.call(
            model=self.model,
            system=system_blocks,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.1,
            max_tokens=2048,
        )

    def _parse_verdict(self, response_text: str) -> dict:
        """Parse JSON verdict from LLM response, with graceful fallback."""
        try:
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", response_text.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
            verdict = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Judge %s: JSON parse error — returning safe fallback", self.slot)
            verdict = {
                "pass_fail": True,
                "css_contribution": 0.70,
                "veto_category": None,
                "confidence": "low",
                "motivation": f"[JSON parse error in {self.slot}]",
                "failed_claims": [],
                "missing_evidence": [],
            }

        # Always inject judge metadata
        verdict["judge_slot"] = self.slot
        verdict["model"] = self.model
        verdict.setdefault("dimension_scores", {})
        verdict.setdefault("external_sources_consulted", [])
        verdict.setdefault("failed_claims", [])
        verdict.setdefault("missing_evidence", [])
        return verdict


# ── Shared constants ─────────────────────────────────────────────────────────

VERDICT_SCHEMA = """\
Return your evaluation as valid JSON with this exact structure:
{
  "pass_fail": true or false,
  "css_contribution": 0.0 to 1.0 (quality score),
  "veto_category": null or one of "fabricated_source", "factual_error", "logical_contradiction", "plagiarism",
  "confidence": "low" or "medium" or "high",
  "motivation": "1-3 sentence justification",
  "failed_claims": ["list of specific claims that fail"],
  "missing_evidence": ["list of claims lacking sources"],
  "dimension_scores": {"key": 0.0-1.0}
}
Do NOT wrap in markdown code fences. Return ONLY the JSON object."""
