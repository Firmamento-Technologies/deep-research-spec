"""
TextChunker — splits long texts into SHINE-compatible chunks.

SHINE has a hard input limit of 1,150 tokens (Qwen3-8B tokenization, §5 paper).
Approved sections can easily exceed this (verbatim tier, distance 1–2).

Splitting strategy (in order of preference):
  1. Paragraph boundaries (double newline) — clean semantic splits
  2. Sentence boundaries (punctuation) — fallback for dense paragraphs
  3. Token-level truncation — last resort for very long single sentences

Overlap:
  CHUNK_OVERLAP_SENTENCES trailing sentences from each chunk are prepended
  to the next chunk to preserve local context across boundaries.
  This slightly reduces effective capacity per chunk but improves adapter
  quality on cross-boundary claims.

Load-bearing claim markers ([LBC:...]) are treated as sentence boundaries
to ensure they are never split mid-marker.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SHINE_MAX_TOKENS        = 1150
CHUNK_OVERLAP_SENTENCES = 2     # trailing sentences carried into next chunk
SAFETY_MARGIN           = 0.95  # use 95% of max to avoid off-by-one truncations


class TextChunker:
    """
    Splits text into SHINE-compatible chunks (each ≤ SHINE_MAX_TOKENS).

    Usage::

        chunker = TextChunker(tokenizer=shine.tokenizer)
        chunks  = chunker.split(long_approved_section)
        # Each chunk ≤ 1,150 tokens — safe to pass to SHINEHypernetwork

        # After generating adapters per chunk:
        adapters = [shine.generate_adapter(c) for c in chunks]
        merged   = shine.merge_adapters(adapters)  # recency-weighted merge
    """

    def __init__(self, tokenizer, max_tokens: int = SHINE_MAX_TOKENS):
        self.tokenizer = tokenizer
        self.max_tokens = int(max_tokens * SAFETY_MARGIN)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def split(self, text: str) -> list:
        """
        Split text into a list of chunks, each ≤ self.max_tokens.

        Returns:
            list[str] ordered as they appear in the source text.
            Single-element list if text already fits in one chunk.
        """
        if self._count(text) <= self.max_tokens:
            return [text]

        logger.debug(
            "[TextChunker] Text (%d tokens) exceeds limit (%d) — splitting",
            self._count(text), self.max_tokens,
        )

        chunks:  list = []
        current: str  = ""
        overlap: list = []

        for para in self._paragraphs(text):
            # Try appending paragraph to current chunk
            candidate = (current + "\n\n" + para).strip() if current else para

            if self._count(candidate) <= self.max_tokens:
                current = candidate
                continue

            # Paragraph alone exceeds limit → sentence-level split
            if self._count(para) > self.max_tokens:
                if current:
                    chunks.append(current)
                    overlap = self._sentences(current)[-CHUNK_OVERLAP_SENTENCES:]
                    current = " ".join(overlap)

                for sent in self._sentences(para):
                    candidate = (current + " " + sent).strip() if current else sent
                    if self._count(candidate) <= self.max_tokens:
                        current = candidate
                    else:
                        if current:
                            chunks.append(current)
                        overlap = self._sentences(current)[-CHUNK_OVERLAP_SENTENCES:]
                        current = " ".join(overlap) + " " + sent if overlap else sent
            else:
                # Paragraph fits alone but not with current — flush
                if current:
                    chunks.append(current)
                overlap = self._sentences(current)[-CHUNK_OVERLAP_SENTENCES:]
                current = (" ".join(overlap) + "\n\n" + para).strip() if overlap else para

        if current:
            chunks.append(current)

        logger.debug(
            "[TextChunker] Produced %d chunks (max %d tokens each)",
            len(chunks), self.max_tokens,
        )
        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _count(self, text: str) -> int:
        """Token count via SHINE tokenizer."""
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    @staticmethod
    def _paragraphs(text: str) -> list:
        """Split on double-newline paragraph boundaries."""
        return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    @staticmethod
    def _sentences(text: str) -> list:
        """Split on sentence-ending punctuation."""
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in parts if s.strip()]
