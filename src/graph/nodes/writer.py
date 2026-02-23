"""Writer agent (§5.7) with §29.1 prompt caching + SHINE support.

Generates a section draft using either:
- **SHINE path** (``shine_active=True``): LoRA adapter provides knowledge,
  no corpus text in the prompt → 95% token reduction.
- **Fallback path** (``shine_active=False``): compressed corpus included
  as text in the user prompt.

System prompt uses §29.1 cache-control blocks (Anthropic) so that
style rules + exemplar are cached across sections (~5 min TTL).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


# ── Writer Node ──────────────────────────────────────────────────────────────

def writer_node(state: dict) -> dict:
    """Generate section draft from compressed corpus or SHINE LoRA.

    Args:
        state: DocumentState dict.

    Returns:
        Partial state update with ``current_draft``, ``current_iteration``,
        and extracted citation info.
    """
    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])
    section = outline[section_idx] if section_idx < len(outline) else {}

    section_scope = section.get("scope", "")
    target_words = section.get("target_words", 500)

    # Style info
    style_profile = state.get("style_profile", {})
    style_profile_str = (
        style_profile if isinstance(style_profile, str)
        else style_profile.get("name", "academic")
    )
    style_exemplar = state.get("style_exemplar") or ""
    writer_memory = state.get("writer_memory", {})

    # ── §29.1 Prompt Caching: system as array with cache_control ─────
    system_blocks = [
        {
            "type": "text",
            "text": _get_style_profile_rules(style_profile),
            "cache_control": {"type": "ephemeral"},  # CACHED ~5 min
        },
        {
            "type": "text",
            "text": f"Style Exemplar:\n{style_exemplar}" if style_exemplar else "",
            "cache_control": {"type": "ephemeral"},  # CACHED ~5 min
        },
        {
            "type": "text",
            "text": _format_writer_memory(writer_memory),
            # NOT cached — changes per section
        },
    ]

    # ── SHINE vs corpus path ─────────────────────────────────────────
    shine_active = state.get("shine_active", False)

    # Build citation map text
    current_sources = state.get("current_sources", [])
    citation_text = _format_sources_as_citations(current_sources)

    if shine_active:
        logger.info("Writer using SHINE LoRA (no corpus in context)")
        user_prompt = _build_prompt_shine(
            style_profile_str, section_scope, target_words, citation_text,
        )
    else:
        corpus = (
            state.get("synthesized_sources", "")
            or state.get("compressed_corpus", "")
        )
        logger.info("Writer using text corpus (SHINE inactive)")
        user_prompt = _build_prompt_corpus(
            style_profile_str, section_scope, target_words, citation_text, corpus,
        )

    # ── LLM call ─────────────────────────────────────────────────────
    messages = [{"role": "user", "content": user_prompt}]

    response = llm_client.call(
        model=route_model("writer", state.get("quality_preset", "balanced")),
        system=system_blocks,
        messages=messages,
        temperature=0.3,
        max_tokens=8192,
        agent="writer",
        preset=state.get("quality_preset", "balanced"),
    )

    draft = response["text"]
    word_count = len(draft.split())
    citations_used = list(set(re.findall(r"\[(\w+)\]", draft)))

    logger.info(
        "Draft generated: %d words, %d citations, cost=$%.4f",
        word_count, len(citations_used), response["cost_usd"],
    )

    return {
        "current_draft": draft,
        "current_iteration": state.get("current_iteration", 0) + 1,
    }


# ── Prompt builders ──────────────────────────────────────────────────────────

def _build_prompt_shine(
    style: str, scope: str, target_words: int, citations: str,
) -> str:
    return f"""\
Write a section for a {style} document.

Section: {scope}
Target word count: {target_words} (±15% acceptable)

Sources (use ONLY citations from this map):
{citations}

Constraints:
- Use ONLY facts from your knowledge (LoRA adapter active)
- Cite sources using [source_id] format
- Word count: {target_words} ± 15%
- No markdown formatting"""


def _build_prompt_corpus(
    style: str, scope: str, target_words: int, citations: str, corpus: str,
) -> str:
    return f"""\
Write a section for a {style} document.

Section: {scope}
Target word count: {target_words} (±15% acceptable)

Sources (use ONLY citations from this map):
{citations}

Research corpus:
{corpus}

Constraints:
- Use ONLY facts from the corpus above
- Cite sources using [source_id] format
- Word count: {target_words} ± 15%
- No markdown formatting"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_style_profile_rules(style_profile: Any) -> str:
    """Load L1/L2 rules from §26 style profiles.

    TODO: implement full style profile loader from config/.
    """
    if isinstance(style_profile, dict):
        rules = style_profile.get("rules", [])
        if rules:
            return "Style rules:\n" + "\n".join(f"- {r}" for r in rules)
    return "Follow academic writing conventions. Be precise and well-sourced."


def _format_sources_as_citations(sources: list[dict]) -> str:
    """Format current_sources into a citation map string."""
    if not sources:
        return "(no sources available)"
    lines = []
    for s in sources:
        sid = s.get("source_id", "?")
        title = s.get("title", "Untitled")
        snippet = (s.get("abstract") or s.get("full_text_snippet") or "")[:200]
        lines.append(f"[{sid}] {title}: {snippet}")
    return "\n".join(lines)


def _format_writer_memory(writer_memory: dict) -> str:
    """Format recurring errors from writer memory (§5.18)."""
    recurring = writer_memory.get("recurring_errors", [])
    if not recurring:
        return ""
    return "Previous errors to avoid:\n" + "\n".join(f"- {err}" for err in recurring)
