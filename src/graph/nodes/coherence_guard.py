"""Coherence Guard node (§5.17) — cross-section consistency check.

After a section is approved, checks for contradictions between
the newly approved section and all previously approved sections.

Routing (via ``route_after_coherence``):
- no_conflict → context_compressor
- soft_conflict → context_compressor (with warning logged)
- hard_conflict → await_human
"""
from __future__ import annotations

import logging
from typing import Any

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


def coherence_guard_node(state: dict) -> dict:
    """Check cross-section coherence.

    Args:
        state: DocumentState dict with ``current_draft``,
               ``approved_sections``, ``current_section_idx``.

    Returns:
        Partial state update with ``coherence_conflicts``.
    """
    current_draft = state.get("current_draft", "")
    approved = state.get("approved_sections", [])
    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])

    # Skip on first section (nothing to compare against)
    if not approved or section_idx == 0:
        logger.info("CoherenceGuard: section %d — no prior sections, skipping", section_idx)
        return {"coherence_conflicts": []}

    current_title = (
        outline[section_idx]["title"]
        if section_idx < len(outline)
        else f"Section {section_idx}"
    )

    # Check against recent approved sections (last 3 for efficiency)
    recent = approved[-3:]
    conflicts = []

    for prev in recent:
        prev_idx = prev.get("section_idx", prev.get("idx", 0))
        prev_title = prev.get("title", f"Section {prev_idx}")
        prev_content = prev.get("content", prev.get("draft", ""))

        if not prev_content:
            continue

        result = _check_pair_coherence(
            section_a_idx=prev_idx,
            section_a_title=prev_title,
            section_a_content=prev_content,
            section_b_idx=section_idx,
            section_b_title=current_title,
            section_b_content=current_draft,
            quality_preset=state.get("quality_preset", "balanced"),
        )

        conflicts.extend(result)

    logger.info(
        "CoherenceGuard: section %d vs %d prior sections → %d conflicts (%d HARD)",
        section_idx,
        len(recent),
        len(conflicts),
        sum(1 for c in conflicts if c.get("level") == "HARD"),
    )

    return {"coherence_conflicts": conflicts}


def _check_pair_coherence(
    section_a_idx: int,
    section_a_title: str,
    section_a_content: str,
    section_b_idx: int,
    section_b_title: str,
    section_b_content: str,
    quality_preset: str = "balanced",
) -> list[dict]:
    """Check coherence between two sections via LLM."""
    try:
        system_blocks = [
            {
                "type": "text",
                "text": """\
You are a coherence checker. Compare two document sections and identify
any contradictions or inconsistencies between them.

For each conflict found, classify it:
- SOFT: Minor inconsistency (different emphasis, slight tension)
- HARD: Direct contradiction (mutually exclusive claims)

Return results in this format (one per line):
CONFLICT: SOFT|HARD | claim_a | claim_b | description

If no conflicts found, return: NO_CONFLICTS""",
                "cache_control": {"type": "ephemeral"},
            },
        ]

        response = llm_client.call(
            model=route_model("coherence_guard", quality_preset),
            system=system_blocks,
            messages=[{
                "role": "user",
                "content": f"""\
Check for contradictions between these two sections:

Section A: "{section_a_title}" (Section {section_a_idx})
{section_a_content[:2000]}

Section B: "{section_b_title}" (Section {section_b_idx})
{section_b_content[:2000]}

Report any contradictions or inconsistencies.""",
            }],
            temperature=0.1,
            max_tokens=1024,
        )

        return _parse_coherence_response(
            response["text"], section_a_idx, section_b_idx,
        )

    except Exception as exc:
        logger.warning(
            "CoherenceGuard LLM check failed for sections %d↔%d: %s",
            section_a_idx, section_b_idx, exc,
        )
        return []


def _parse_coherence_response(
    text: str, section_a_idx: int, section_b_idx: int,
) -> list[dict]:
    """Parse coherence check response into conflict dicts."""
    if "NO_CONFLICTS" in text.upper():
        return []

    conflicts = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("CONFLICT:"):
            parts = line[len("CONFLICT:"):].split("|")
            if len(parts) >= 3:
                level = parts[0].strip().upper()
                if level not in ("SOFT", "HARD"):
                    level = "SOFT"
                conflicts.append({
                    "level": level,
                    "section_a_idx": section_a_idx,
                    "section_b_idx": section_b_idx,
                    "claim_a": parts[1].strip()[:200] if len(parts) > 1 else "",
                    "claim_b": parts[2].strip()[:200] if len(parts) > 2 else "",
                    "description": parts[3].strip()[:300] if len(parts) > 3 else "",
                })

    return conflicts
