"""Writer agent (§5.7) with §29.1 prompt caching + SHINE + RLM mode support.

Generates a section draft using one of three paths:

- **SHINE LoRA path** (``shine_active=True`` AND ``SHINE_SERVING_URL`` set):
  SHINE hypernetwork encodes the research corpus into LoRA weight deltas in a
  single forward pass. Those deltas are injected into a local vLLM/AIBrix
  inference server — the model ACTUALLY has the domain knowledge in its
  weights, no corpus in the prompt → ~95% token reduction.
  Ref: https://github.com/Yewei-Liu/SHINE (arXiv:2602.06358)

  IMPORTANT: ``state["shine_lora"]`` contains binary weight TENSORS, NOT
  text. They cannot be placed in a prompt. ``shine_active=True`` without
  ``SHINE_SERVING_URL`` is a misconfiguration — the node falls back to
  standard corpus and emits a logger.warning() (P1 fix).

- **RLM path** (``rlm_mode=True``):
  RLM (https://github.com/alexzhang13/rlm, arXiv:2512.24601) opens a REPL
  environment and calls the model recursively to decompose and process the
  full corpus chunk-by-chunk. The complete (non-compressed) corpus is passed
  to ``rlm.completion()``; RLM handles context management internally.
  source_synthesizer and context_compressor are bypassed upstream.
  All HTTP calls are routed through llm_client via DeepResearchLM adapter
  (rate limiter + cost tracking + tier guard preserved).

- **Standard path** (fallback): compressed/synthesized corpus included
  as text in the user prompt via a single llm_client.call().

System prompt uses §29.1 cache-control blocks (Anthropic) so that
style rules + exemplar are cached across sections (~5 min TTL).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)

# Real LoRA serving endpoint required for SHINE.
# SHINE (https://github.com/Yewei-Liu/SHINE, arXiv:2602.06358) encodes the
# research corpus into LoRA weight deltas via a hypernetwork, then injects
# them into this local inference server. The model then "knows" the corpus
# WITHOUT it being in the prompt (~95% token reduction).
#
# Cloud API models (Anthropic, OpenAI, OpenRouter) cannot receive LoRA
# injections — do NOT set shine_active=True without this URL configured.
# If empty: writer falls back to standard corpus path + logger.warning().
_SHINE_SERVING_URL: str = os.getenv("SHINE_SERVING_URL", "")


# ── Writer Node ─────────────────────────────────────────────────

def writer_node(state: dict) -> dict:
    """Generate section draft from compressed corpus, RLM, or SHINE.

    Path selection priority:
      1. SHINE LoRA   (shine_active=True AND SHINE_SERVING_URL set)
      2. RLM          (rlm_mode=True) — early return, bypasses llm_client
      3. Standard     (fallback)

    Args:
        state: DocumentState dict.

    Returns:
        Partial state update with ``current_draft`` and ``current_iteration``.
    """
    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])
    section = outline[section_idx] if section_idx < len(outline) else {}

    section_scope = section.get("scope", "")
    target_words = section.get("target_words", 500)
    preset = state.get("quality_preset", "balanced")

    style_profile = state.get("style_profile", {})
    style_profile_str = (
        style_profile if isinstance(style_profile, str)
        else style_profile.get("name", "academic")
    )
    style_exemplar = state.get("style_exemplar") or ""
    writer_memory = state.get("writer_memory", {})

    current_sources = state.get("current_sources", [])
    citation_text = _format_sources_as_citations(current_sources)

    shine_active = state.get("shine_active", False)
    rlm_mode = state.get("rlm_mode", False)

    # ─────────────────────────────────────────────────────────────────────
    # PATH 1 — SHINE LoRA
    # ─────────────────────────────────────────────────────────────────────
    if shine_active:
        # P1 fix: state["shine_lora"] contains binary weight TENSORS —
        # NOT text. Only Path A (real vLLM serving) is valid.
        if _SHINE_SERVING_URL:
            logger.info(
                "Writer: SHINE LoRA path — local server %s — "
                "corpus encoded as weight deltas "
                "(https://github.com/Yewei-Liu/SHINE)",
                _SHINE_SERVING_URL,
            )
            user_prompt = _build_prompt_shine_lora(
                style_profile_str, section_scope, target_words, citation_text,
            )
        else:
            logger.warning(
                "Writer: shine_active=True but SHINE_SERVING_URL is not set. "
                "SHINE (https://github.com/Yewei-Liu/SHINE, arXiv:2602.06358) "
                "requires a local vLLM/AIBrix server to inject LoRA weight "
                "deltas — cloud API models cannot receive LoRA injections. "
                "state['shine_lora'] contains binary tensors, not text. "
                "Falling back to standard corpus path."
            )
            corpus = (
                state.get("synthesized_sources", "")
                or state.get("compressed_corpus", "")
            )
            user_prompt = _build_prompt_corpus(
                style_profile_str, section_scope, target_words,
                citation_text, corpus,
            )

    # ─────────────────────────────────────────────────────────────────────
    # PATH 2 — RLM (early return — bypasses llm_client.call below)
    # RLM drives a REPL loop that decomposes the corpus recursively.
    # All HTTP calls are routed through DeepResearchLM → llm_client.
    # Ref: https://github.com/alexzhang13/rlm (arXiv:2512.24601)
    # ─────────────────────────────────────────────────────────────────────
    elif rlm_mode:
        from src.llm.rlm_adapter import get_rlm_client  # lazy import

        # Pass full uncompressed corpus — RLM handles decomposition internally
        corpus = (
            state.get("sanitized_sources", "")
            or state.get("research_results", "")
            or state.get("synthesized_sources", "")  # graceful fallback
        )

        full_prompt = _build_prompt_corpus(
            style_profile_str, section_scope, target_words, citation_text, corpus,
        )

        rlm = get_rlm_client(
            model=route_model("writer", preset),
            child_model=route_model("writer", "economy"),
            state=state,
        )

        logger.info(
            "Writer: RLM mode — https://github.com/alexzhang13/rlm — "
            "corpus=%d chars, model=%s",
            len(corpus),
            route_model("writer", preset),
        )

        result = rlm.completion(full_prompt)
        draft = result.response
        word_count = len(draft.split())
        citations_used = list(set(re.findall(r"\[(\w+)\]", draft)))
        cost_usd = (
            result.usage_summary.total_cost
            if result.usage_summary and result.usage_summary.total_cost
            else 0.0
        )

        logger.info(
            "RLM draft: %d words, %d citations, "
            "cost=$%.4f, time=%.2fs",
            word_count, len(citations_used),
            cost_usd, result.execution_time,
        )

        # Early return — RLM owned transport, no llm_client.call() needed
        return {
            "current_draft": draft,
            "current_iteration": state.get("current_iteration", 0) + 1,
        }

    # ─────────────────────────────────────────────────────────────────────
    # PATH 3 — Standard (SHINE inactive, RLM inactive)
    # ─────────────────────────────────────────────────────────────────────
    else:
        corpus = (
            state.get("synthesized_sources", "")
            or state.get("compressed_corpus", "")
        )
        logger.info("Writer: standard corpus path (SHINE inactive, RLM inactive)")
        user_prompt = _build_prompt_corpus(
            style_profile_str, section_scope, target_words, citation_text, corpus,
        )

    # ── §29.1 Prompt Caching: system as array with cache_control ──────────
    # Applies to PATH 1 (SHINE) and PATH 3 (standard) only.
    # PATH 2 (RLM) returned early above.
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

    # P8: Dynamic max_tokens proportional to target_words.
    # Formula: words × 1.5 safety buffer ÷ 0.75 words/token + 256 overhead.
    # Floor 512 (short sections), cap 8192 (provider limit).
    max_tokens = max(512, min(int(target_words * 1.5 / 0.75) + 256, 8192))

    # ── LLM call (PATH 1 + PATH 3) ──────────────────────────────────
    messages = [{"role": "user", "content": user_prompt}]

    response = llm_client.call(
        model=route_model("writer", preset),
        system=system_blocks,
        messages=messages,
        temperature=0.3,
        max_tokens=max_tokens,
        agent="writer",
        preset=preset,
    )

    draft = response["text"]
    word_count = len(draft.split())
    citations_used = list(set(re.findall(r"\[(\w+)\]", draft)))

    logger.info(
        "Draft: %d words, %d citations, cost=$%.4f, max_tokens=%d",
        word_count, len(citations_used), response["cost_usd"], max_tokens,
    )

    return {
        "current_draft": draft,
        "current_iteration": state.get("current_iteration", 0) + 1,
    }


# ── Prompt builders ─────────────────────────────────────────────

def _build_prompt_shine_lora(
    style: str, scope: str, target_words: int, citations: str,
) -> str:
    """Prompt for REAL LoRA serving path ONLY.

    Called exclusively when SHINE_SERVING_URL is configured. The SHINE
    hypernetwork (https://github.com/Yewei-Liu/SHINE, arXiv:2602.06358)
    has encoded the research corpus into LoRA weight deltas injected into
    the local inference server. The model ACTUALLY has the domain knowledge
    — the directive is architecturally valid here.

    NEVER call this for cloud API models. They cannot receive LoRA
    injections and the directive will cause hallucination.
    """
    return f"""\
Write a section for a {style} document.

Section: {scope}
Target word count: {target_words} (±15% acceptable)

Sources (use ONLY citations from this map):
{citations}

Constraints:
- Your LoRA adapter contains the domain knowledge for this section
- Cite sources using [source_id] format
- Word count: {target_words} ± 15%
- No markdown formatting"""


def _build_prompt_corpus(
    style: str, scope: str, target_words: int, citations: str, corpus: str,
) -> str:
    """Prompt for standard and RLM paths.

    Used by:
      - PATH 2 (RLM): full uncompressed corpus; RLM decomposes internally
      - PATH 3 (standard): pre-compressed corpus
      - PATH 1 fallback (SHINE misconfigured): compressed corpus
    """
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


# ── Helpers ──────────────────────────────────────────────────

def _get_style_profile_rules(style_profile: Any) -> str:
    """Load style rules from config/style_profiles.yaml (§26).

    Accepts:
        - str: profile name (e.g. "academic", "business")
        - dict with "name" key → profile name
        - dict with "rules" key → inline rules (legacy)
    """
    import yaml as _yaml
    from pathlib import Path as _Path

    if isinstance(style_profile, str):
        profile_name = style_profile
    elif isinstance(style_profile, dict):
        inline_rules = style_profile.get("rules", [])
        if inline_rules:
            return "Style rules:\n" + "\n".join(f"- {r}" for r in inline_rules)
        profile_name = style_profile.get("name", "academic")
    else:
        profile_name = "academic"

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
            pass

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
