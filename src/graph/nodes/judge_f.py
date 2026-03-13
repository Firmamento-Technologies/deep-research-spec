"""Judge F — Factual accuracy evaluator (§8.2).

Evaluates: source attribution, factual correctness, ghost sources,
and claim verification.  Includes micro-search capability via
Perplexity Sonar for falsification attempts.
"""
from __future__ import annotations

import logging
from typing import Any

from src.llm.client import llm_client
from src.graph.nodes.jury_base import Judge, VERDICT_SCHEMA

logger = logging.getLogger(__name__)


FACTUAL_RUBRIC = """\
You are a Factual Accuracy Judge evaluating whether claims in a document
section are properly sourced and factually correct.

Evaluate these dimensions (score each 0.0-1.0):
- **source_attribution**: Every major claim cites a source
- **factual_correctness**: Claims match the source material
- **ghost_sources**: No citations to non-existent sources
- **claim_verification**: Key claims could withstand external verification
- **data_accuracy**: Numbers, dates, statistics are correct

VETO if you find:
- A fabricated source (citation to a non-existent paper/article)
- A clearly false factual claim (contradicted by well-known facts)

Be rigorous on source attribution. A score ≥0.75 = pass."""


class JudgeF(Judge):
    """Factual accuracy judge with micro-search (§8.2)."""

    def evaluate(self, draft: str, sources: list[dict], section_scope: str) -> dict:
        system_blocks = [
            {
                "type": "text",
                "text": VERDICT_SCHEMA,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": FACTUAL_RUBRIC,
                "cache_control": {"type": "ephemeral"},
            },
        ]

        # Build source evidence context
        source_evidence = self._format_source_evidence(sources or [])

        user_prompt = f"""\
Evaluate the FACTUAL ACCURACY of this draft section.

Section scope: {section_scope}

Source evidence:
{source_evidence}

Draft:
---
{draft[:6000]}
---

Instructions:
1. Check every cited source against the evidence above
2. Flag any claims without proper attribution
3. Identify any fabricated or ghost sources
4. Note claims that seem factually dubious

Return your evaluation as the JSON structure specified in the system prompt."""

        response = self._call_llm_with_cache(system_blocks, user_prompt)
        verdict = self._parse_verdict(response["text"])

        # Attempt micro-search falsification on suspicious claims
        failed_claims = verdict.get("failed_claims", [])
        if failed_claims:
            micro_results = self._micro_search(failed_claims[:3])
            verdict["external_sources_consulted"] = micro_results

        # Enrich dimension_scores
        verdict["dimension_scores"].setdefault("source_attribution", verdict.get("css_contribution", 0.7))
        verdict["dimension_scores"].setdefault("factual_correctness", verdict.get("css_contribution", 0.7))

        return verdict

    def _format_source_evidence(self, sources: list[dict]) -> str:
        """Format sources into evidence context for the judge."""
        if not sources:
            return "(no source evidence provided)"
        lines = []
        for s in sources[:15]:
            sid = s.get("source_id", "?")
            title = s.get("title", "Untitled")
            abstract = (s.get("abstract") or "")[:300]
            lines.append(f"[{sid}] {title}\n  {abstract}")
        return "\n\n".join(lines)

    def _micro_search(self, claims: list[str]) -> list[str]:
        """§8.2 micro-search: verify suspicious claims via LLM.

        Returns list of consulted source URLs/descriptions.
        """
        from src.llm.routing import route_model

        consulted: list[str] = []
        for claim in claims:
            try:
                model = route_model("jury_f", getattr(self, "preset", "balanced"))
                response = llm_client.call(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": f"Is this claim true or false? Provide evidence: {claim}",
                    }],
                    temperature=0.0,
                    max_tokens=512,
                    agent="judge_f",
                    preset="balanced",
                )
                consulted.append(f"[sonar] Claim: {claim[:80]}… → {response['text'][:200]}")
                logger.info("JudgeF micro-search: verified claim '%.60s…'", claim)
            except Exception as exc:
                logger.warning("JudgeF micro-search failed for claim: %s", exc)
                consulted.append(f"[sonar] Claim: {claim[:80]}… → (verification failed)")
        return consulted
