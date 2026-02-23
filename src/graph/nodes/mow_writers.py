"""Mixture-of-Writers node (§7) — 3 parallel writers with diverse angles.

Internal to the writer pipeline. Activated when:
- Quality preset ≠ Economy
- Section ≥ 400 target words
- Iteration = 1 (first draft only)
- No human intervention pending

Produces 3 drafts for JuryMultiDraft → Fusor pipeline.
"""
from __future__ import annotations

import asyncio
import logging

from src.llm.client import llm_client

logger = logging.getLogger(__name__)

# ── Writer angles (§7.1) ────────────────────────────────────────────────────
_ANGLES = [
    {
        "id": "W-A",
        "label": "Coverage",
        "instruction": "Focus on BREADTH: cover all key subtopics comprehensively. "
                       "Prioritize completeness over depth.",
        "temperature": 0.3,
    },
    {
        "id": "W-B",
        "label": "Argumentation",
        "instruction": "Focus on LOGIC: build a strong argumentative chain. "
                       "Prioritize causal reasoning and evidence-backed claims.",
        "temperature": 0.6,
    },
    {
        "id": "W-C",
        "label": "Readability",
        "instruction": "Focus on CLARITY: write for a broad audience. "
                       "Use concrete examples, analogies, and smooth transitions.",
        "temperature": 0.8,
    },
]


def should_activate_mow(state: dict) -> bool:
    """Check MoW activation conditions (§7.1)."""
    config = state.get("config", {})
    preset = state.get("budget", {}).get("quality_preset", config.get("quality_preset", "balanced"))
    if preset.lower() == "economy":
        return False

    outline = state.get("outline", [])
    idx = state.get("current_section_idx", 0)
    if idx < len(outline):
        target_words = outline[idx].get("target_words", 500)
        if target_words < 400:
            return False

    if state.get("current_iteration", 1) > 1:
        return False

    if state.get("human_review_pending"):
        return False

    return True


def mow_writers_node(state: dict) -> dict:
    """Generate 3 diverse drafts in parallel.

    Returns:
        Partial state with ``mow_drafts`` (list of 3 draft dicts)
        and ``mow_active`` flag.
    """
    if not should_activate_mow(state):
        logger.info("MoW: skipped (activation conditions not met)")
        return {"mow_active": False, "mow_drafts": []}

    outline = state.get("outline", [])
    idx = state.get("current_section_idx", 0)
    section = outline[idx] if idx < len(outline) else {}
    section_scope = section.get("scope", section.get("title", ""))
    target_words = section.get("target_words", 1000)
    corpus = state.get("compressed_corpus", "")
    citation_map = state.get("citation_map", {})

    citation_text = "\n".join(
        f"[{sid}] {cite}" for sid, cite in citation_map.items()
    ) if citation_map else "No citations available"

    # Run 3 writers in parallel
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                futures = [
                    pool.submit(_generate_draft, angle, section_scope, target_words, corpus, citation_text)
                    for angle in _ANGLES
                ]
                drafts = [f.result() for f in futures]
        else:
            drafts = loop.run_until_complete(
                asyncio.gather(*[
                    asyncio.to_thread(
                        _generate_draft, angle, section_scope, target_words, corpus, citation_text
                    )
                    for angle in _ANGLES
                ])
            )
    except RuntimeError:
        # No event loop — run synchronously
        drafts = [
            _generate_draft(angle, section_scope, target_words, corpus, citation_text)
            for angle in _ANGLES
        ]

    logger.info(
        "MoW: generated %d drafts — %s",
        len(drafts),
        ", ".join(f"{d['angle']}:{len(d['draft'].split())}w" for d in drafts),
    )

    return {
        "mow_active": True,
        "mow_drafts": drafts,
    }


def _generate_draft(
    angle: dict, section_scope: str, target_words: int,
    corpus: str, citation_text: str,
) -> dict:
    """Generate a single draft with a specific angle."""
    try:
        response = llm_client.call(
            model="anthropic/claude-opus-4-5",
            system=[{
                "type": "text",
                "text": (
                    f"You are Writer {angle['id']} ({angle['label']}). "
                    f"{angle['instruction']}"
                ),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": f"""\
Write a section draft.

Section: {section_scope}
Target word count: {target_words} (±15%)

Sources (cite using [source_id] format):
{citation_text}

Research corpus:
{corpus[:4000] if corpus else 'No corpus available'}

Constraints:
- Use ONLY facts from the corpus
- Cite sources using [source_id] format
- Target: {target_words} words ±15%""",
            }],
            temperature=angle["temperature"],
            max_tokens=8192,
        )

        draft = response["text"]
        return {
            "angle": angle["id"],
            "label": angle["label"],
            "draft": draft,
            "word_count": len(draft.split()),
            "cost_usd": response.get("cost_usd", 0),
        }

    except Exception as exc:
        logger.warning("MoW %s failed: %s", angle["id"], exc)
        return {
            "angle": angle["id"],
            "label": angle["label"],
            "draft": "",
            "word_count": 0,
            "cost_usd": 0,
            "error": str(exc),
        }
