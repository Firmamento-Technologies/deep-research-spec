"""Post-Draft Analyzer node (§5.7) — extract claims and evidence gaps.

Analyses the writer's draft to produce:
- Extracted claims (for jury verification)
- Evidence gap list (for researcher_targeted)
- Citation check results
"""
from __future__ import annotations

import logging
import re

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


def post_draft_analyzer_node(state: dict) -> dict:
    """Analyse draft to extract claims and identify evidence gaps.

    Returns:
        Partial state with ``extracted_claims``, ``evidence_gaps``,
        and ``draft_citations``.
    """
    draft = state.get("current_draft", "")
    sources = state.get("sources", [])

    if not draft:
        return {
            "extracted_claims": [],
            "evidence_gaps": [],
            "draft_citations": [],
        }

    # Extract inline citations (e.g., [Source 1], [Author, 2024])
    citations = _extract_citations(draft)

    # Use LLM to extract claims and find evidence gaps
    claims, gaps = _analyse_draft(draft, sources, state.get("quality_preset", "balanced"))

    logger.info(
        "PostDraftAnalyzer: %d claims, %d evidence gaps, %d citations",
        len(claims), len(gaps), len(citations),
    )

    return {
        "extracted_claims": claims,
        "evidence_gaps": gaps,
        "draft_citations": citations,
    }


def _extract_citations(draft: str) -> list[dict]:
    """Extract citation references from draft text."""
    # Match patterns like [Source 1], [Author, 2024], [1], etc.
    patterns = [
        r'\[Source\s+\d+\]',
        r'\[\d+\]',
        r'\[[A-Z][a-z]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-z]+))?,\s*\d{4}\]',
    ]

    citations = []
    for pattern in patterns:
        for match in re.finditer(pattern, draft):
            citations.append({
                "ref": match.group(),
                "position": match.start(),
            })

    return citations


def _analyse_draft(draft: str, sources: list, quality_preset: str = "balanced") -> tuple[list[dict], list[dict]]:
    """Use LLM to extract claims and identify evidence gaps."""
    try:
        source_summary = ""
        if sources:
            source_summary = "\n".join(
                f"- {s.get('title', s.get('id', '?'))}: {s.get('snippet', '')[:100]}"
                for s in sources[:10]
            )

        response = llm_client.call(
            model=route_model("post_draft_analyzer", quality_preset),
            messages=[{
                "role": "user",
                "content": f"""\
Analyse this draft. Extract key claims and identify evidence gaps.

Draft (first 3000 chars):
{draft[:3000]}

Available sources:
{source_summary or 'None provided'}

Return in this format:
CLAIMS:
1. [claim text] | [supported/unsupported/partially_supported]
2. ...

EVIDENCE_GAPS:
1. [description of what evidence is missing]
2. ...""",
            }],
            temperature=0.1,
            max_tokens=2048,
            agent="post_draft_analyzer",
            preset=quality_preset,
        )

        return _parse_analysis(response["text"])

    except Exception as exc:
        logger.warning("PostDraftAnalyzer LLM analysis failed: %s", exc)
        return [], []


def _parse_analysis(text: str) -> tuple[list[dict], list[dict]]:
    """Parse claim/gap analysis from LLM response."""
    claims = []
    gaps = []
    section = None

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("CLAIMS:"):
            section = "claims"
            continue
        elif line.startswith("EVIDENCE_GAPS:"):
            section = "gaps"
            continue

        if not line or not (line[0].isdigit() or line.startswith("-")):
            continue

        content = line.lstrip("0123456789.-) ")
        if section == "claims" and content:
            parts = content.split("|")
            claims.append({
                "text": parts[0].strip()[:200],
                "status": parts[1].strip().lower() if len(parts) > 1 else "unknown",
            })
        elif section == "gaps" and content:
            gaps.append({
                "description": content[:200],
                "priority": "medium",
            })

    return claims[:20], gaps[:10]
