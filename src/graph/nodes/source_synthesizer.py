"""SourceSynthesizer node — §5.6. Compress verified sources before Writer."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_DEFAULT_COMPRESSION_RATIO = 0.40  # retain 40% of original token count


class SourceSynthesizerNode:
    """§5.6 — Compress verified source corpus before Writer call.

    Deduplicates claims, tags with [src:id], and clears targeted_research_active.
    Output written to ``synthesized_sources`` field (C08).
    """

    def __init__(self, llm=None):
        self.llm = llm  # LLM client for compression (injected at runtime)

    async def run(self, state: dict) -> dict:
        """Compress sources into synthesized corpus. Returns partial state update."""
        sources = state.get("current_sources", [])

        # §5.6 CONSTRAINT: skip if ≤ 2 sources → pass through unchanged
        if len(sources) <= 2:
            corpus = self._passthrough_corpus(sources)
            return {
                "synthesized_sources": corpus,
                "targeted_research_active": False,  # always clear (§5.6)
            }

        # Build raw corpus with source tagging
        tagged_claims: list[str] = []
        for src in sources:
            sid = src.get("source_id", "unknown")
            content = (
                src.get("sanitized_xml")
                or src.get("abstract")
                or src.get("full_text_snippet")
                or ""
            )
            if content:
                # Tag each claim with source_id inline: "claim [src:id]"
                tagged_claims.append(f"{content} [src:{sid}]")

        raw_corpus = "\n\n".join(tagged_claims)

        # Attempt LLM compression if available
        compressed = await self._compress_with_llm(raw_corpus, sources)
        if compressed is None:
            # Graceful degradation: truncate to ~40% token estimate
            compressed = self._truncate_corpus(raw_corpus)

        return {
            "synthesized_sources": compressed,
            "targeted_research_active": False,  # MUST clear (§5.6)
        }

    async def _compress_with_llm(self, raw_corpus: str, sources: list[dict]) -> str | None:
        """Use LLM to compress and deduplicate claims. §5.6."""
        if self.llm is None:
            return None
        try:
            prompt = (
                "Compress the following source corpus. Deduplicate semantically "
                "equivalent claims, merging confirmed_by into lists. Preserve all "
                "source_ids referenced. Tag each retained claim with [src:id]. "
                "Target 40% of original length.\n\n"
                f"{raw_corpus}"
            )
            result = await self.llm.generate(prompt, max_tokens=2048, temperature=0.1)
            return result
        except Exception as e:
            logger.warning("LLM compression failed: %s — using truncation fallback", e)
            return None

    def _passthrough_corpus(self, sources: list[dict]) -> str:
        """Pass through when ≤ 2 sources. §5.6."""
        parts = []
        for src in sources:
            sid = src.get("source_id", "unknown")
            content = src.get("abstract") or src.get("full_text_snippet") or ""
            if content:
                parts.append(f"{content} [src:{sid}]")
        return "\n\n".join(parts)

    def _truncate_corpus(self, raw_corpus: str) -> str:
        """Graceful degradation: truncate to ~40% of content. §5.6."""
        target_chars = int(len(raw_corpus) * _DEFAULT_COMPRESSION_RATIO)
        if len(raw_corpus) <= target_chars:
            return raw_corpus
        # Truncate at word boundary
        truncated = raw_corpus[:target_chars]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        return truncated + "\n[TRUNCATED: compression fallback]"


# ── Node function for graph registration ──────────────────────────────

_default_node = SourceSynthesizerNode()


async def source_synthesizer_node(state: dict) -> dict:
    """Graph-compatible node function."""
    # RLM bypass: raw corpus propagated directly — no compression needed
    if state.get("rlm_mode", False):
        return state  # no-op: rlm.completion() handles context recursively
    return await _default_node.run(state)
