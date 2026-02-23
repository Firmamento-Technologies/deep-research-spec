"""WriterMemory node (§5.18) — deterministic error accumulator.

Tracks recurring errors, technical glossary, and citation tendencies
across sections. Injected into Writer prompt as proactive warnings.
No LLM calls — purely deterministic analysis.
"""
from __future__ import annotations

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)


def writer_memory_node(state: dict) -> dict:
    """Update writer memory after section approval.

    Analyzes the approved draft + jury verdicts to accumulate:
    - `recurring_errors`: patterns that appear 2+ times
    - `technical_glossary`: term → canonical form
    - `citation_tendency`: under/normal/over

    Returns:
        Partial state with updated ``writer_memory``.
    """
    memory = dict(state.get("writer_memory", {}))
    draft = state.get("current_draft", "")
    verdicts = state.get("jury_verdicts", [])
    citations_used = state.get("citations_used", [])
    citation_map = state.get("citation_map", {})

    # 1. Accumulate recurring errors from jury feedback
    error_counts = dict(memory.get("error_counts", {}))
    for verdict in verdicts:
        if not verdict.get("pass_fail", True):
            failed = verdict.get("failed_claims", [])
            for claim in failed:
                category = _classify_error(claim)
                error_counts[category] = error_counts.get(category, 0) + 1

    recurring_errors = [
        err for err, count in error_counts.items() if count >= 2
    ]

    # 2. Build technical glossary from draft
    glossary = dict(memory.get("technical_glossary", {}))
    glossary.update(_extract_terms(draft))

    # 3. Citation tendency
    n_citations = len(citations_used) if citations_used else _count_citations(draft)
    n_available = len(citation_map) if citation_map else 1
    ratio = n_citations / max(n_available, 1)

    if ratio < 0.3:
        citation_tendency = "under"
    elif ratio > 0.8:
        citation_tendency = "over"
    else:
        citation_tendency = "normal"

    # 4. Generate proactive warnings
    warnings = _generate_warnings(recurring_errors, citation_tendency)

    memory.update({
        "error_counts": error_counts,
        "recurring_errors": recurring_errors,
        "technical_glossary": glossary,
        "citation_tendency": citation_tendency,
        "proactive_warnings": warnings,
        "sections_analyzed": memory.get("sections_analyzed", 0) + 1,
    })

    logger.info(
        "WriterMemory: %d recurring errors, %d glossary terms, citations=%s",
        len(recurring_errors), len(glossary), citation_tendency,
    )

    return {"writer_memory": memory}


def _classify_error(claim: str) -> str:
    """Classify a failed claim into an error category."""
    claim_lower = claim.lower() if isinstance(claim, str) else ""
    if any(w in claim_lower for w in ("logic", "reasoning", "argument", "causal")):
        return "weak_reasoning"
    if any(w in claim_lower for w in ("source", "citation", "reference", "fabricat")):
        return "citation_error"
    if any(w in claim_lower for w in ("contradict", "inconsist")):
        return "contradiction"
    if any(w in claim_lower for w in ("vague", "imprecise", "unclear")):
        return "vague_claims"
    return "general_quality"


def _extract_terms(draft: str) -> dict[str, str]:
    """Extract technical terms from draft for glossary."""
    terms = {}
    # Match capitalized multi-word terms (likely technical)
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', draft):
        term = match.group()
        if len(term) > 5:
            terms[term.lower()] = term  # canonical form preserves casing

    # Match acronyms with definitions
    for match in re.finditer(r'([A-Z]{2,6})\s*\(([^)]+)\)', draft):
        acronym, definition = match.groups()
        terms[acronym] = f"{acronym} ({definition})"

    return terms


def _count_citations(draft: str) -> int:
    """Count citation references in draft."""
    return len(re.findall(r'\[\w+\]', draft))


def _generate_warnings(recurring_errors: list[str], citation_tendency: str) -> list[str]:
    """Generate proactive warnings for Writer prompt."""
    warnings = []

    for err in recurring_errors[:5]:
        if err == "weak_reasoning":
            warnings.append("RECURRING: Strengthen logical arguments with explicit causal chains")
        elif err == "citation_error":
            warnings.append("RECURRING: Double-check all citations exist in the citation map")
        elif err == "contradiction":
            warnings.append("RECURRING: Check for self-contradictions before submitting")
        elif err == "vague_claims":
            warnings.append("RECURRING: Replace vague language with specific, quantified claims")
        else:
            warnings.append(f"RECURRING: Previous drafts had {err} issues — address proactively")

    if citation_tendency == "under":
        warnings.append("TENDENCY: Under-citation detected — increase source references")
    elif citation_tendency == "over":
        warnings.append("TENDENCY: Over-citation detected — reduce redundant citations")

    return warnings
