"""Writer agent (§5.7) with §29.1 prompt caching + SHINE + RLM mode support.

Generates a section draft using one of three paths:
- **SHINE path** (``shine_active=True``): LoRA adapter provides knowledge,
  no corpus text in the prompt → 95% token reduction.
- **RLM path** (``rlm_mode=True``): raw corpus passed directly to writer;
  source_synthesizer and context_compressor are bypassed upstream;
  rlm.completion() handles recursive context internally.
- **Standard path** (fallback): compressed/synthesized corpus included
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


# ── Writer Node ─────────────────────────────────────────────

def writer_node(state: dict) -> dict:
    """Generate section draft from compressed corpus, RLM raw corpus, or SHINE LoRA.

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

    # ── §29.1 Prompt Caching: system as array with cache_control ──────
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

    # ── SHINE vs RLM vs standard corpus path ───────────────────────
    shine_active = state.get("shine_active", False)
    rlm_mode = state.get("rlm_mode", False)

    # Build citation map text
    current_sources = state.get("current_sources", [])
    citation_text = _format_sources_as_citations(current_sources)

    if shine_active:
        logger.info("Writer: SHINE LoRA path (no corpus in context)")
        user_prompt = _build_prompt_shine(
            style_profile_str, section_scope, target_words, citation_text,
        )
    elif rlm_mode:
        # RLM mode: raw corpus bypasses source_synthesizer + context_compressor.
        # Graceful fallback chain: sanitized_sources → research_results → synthesized_sources.
        corpus = (
            state.get("sanitized_sources", "")
            or state.get("research_results", "")
            or state.get("synthesized_sources", "")  # graceful fallback
        )
        logger.info("Writer: RLM mode (raw corpus, bypassing compression)")
        user_prompt = _build_prompt_corpus(
            style_profile_str, section_scope, target_words, citation_text, corpus,
        )
    else:
        corpus = (
            state.get("synthesized_sources", "")
            or state.get("compressed_corpus", "")
        )
        logger.info("Writer: standard corpus path (SHINE inactive, RLM inactive)")
        user_prompt = _build_prompt_corpus(
            style_profile_str, section_scope, target_words, citation_text, corpus,
        )

    # ── LLM call ─────────────────────────────────────────────
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


# ── Prompt builders ──────────────────────────────────────────

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


# ── Helpers ────────────────────────────────────────────────

def _get_style_profile_rules(style_profile: Any) -> str:
    """Load style rules from config/style_profiles.yaml (§26).

    Accepts:
        - str: profile name (e.g. "academic", "business")
        - dict with "name" key → profile name
        - dict with "rules" key → inline rules (legacy)
    """
    import yaml as _yaml
    from pathlib import Path as _Path

    # Determine profile name
    if isinstance(style_profile, str):
        profile_name = style_profile
    elif isinstance(style_profile, dict):
        # Legacy: inline rules take precedence
        inline_rules = style_profile.get("rules", [])
        if inline_rules:
            return "Style rules:\n" + "\n".join(f"- {r}" for r in inline_rules)
        profile_name = style_profile.get("name", "academic")
    else:
        profile_name = "academic"

    # Load from config file
    config_path = _Path(__file__).resolve().parents[3] / "config" / "style_profiles.yaml"
    if config_path.exists():
        try:
            with open(config_path) as f:
                profiles = _yaml.safe_load(f) or {}
            profile = profiles.get(profile_name, profiles.get("academic", {}))
            rules = profile.get("rules", [])
            if rules:
                return "Style rules:\n" + "\n".join(f"- {r}" for r in rules)
        except Exception:
            pass  # Fall through to default

    # Fallback
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
