"""UserUploadConnector — local-only processing — §17.7."""
from __future__ import annotations

import logging

from src.connectors.base import SourceConnector, SourceType

logger = logging.getLogger(__name__)


class UserUploadConnector(SourceConnector):
    """Process user-uploaded files locally. §17.7.

    INVARIANT: No content is EVER sent to external providers.
    reliability_score = 1.0 (user content = ground truth).
    """

    connector_id: str = "user_upload"
    source_type: SourceType = "upload"
    reliability_base: float = 1.0
    enabled: bool = True

    def __init__(
        self,
        chunk_size_tokens: int = 512,
        chunk_overlap_tokens: int = 64,
        similarity_threshold: float = 0.75,
    ):
        self.chunk_size = chunk_size_tokens
        self.chunk_overlap = chunk_overlap_tokens
        self.similarity_threshold = similarity_threshold
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers required for UserUploadConnector. "
                    "Local-only constraint: no fallback available."
                )
        return self._embedder

    def _chunk_text(self, text: str) -> list[str]:
        """Chunk text at ~chunk_size tokens with overlap."""
        words = text.split()
        chunks = []
        step = max(1, self.chunk_size - self.chunk_overlap)
        for i in range(0, len(words), step):
            chunk = " ".join(words[i : i + self.chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    async def search(self, query: str, max_results: int) -> list[dict]:
        """Not used directly — use process_uploads() instead."""
        return []

    async def process_uploads(
        self,
        query: str,
        uploaded_texts: dict[str, str],  # file_id → text content
        max_results: int = 10,
    ) -> list[dict]:
        """Process uploaded files locally, return relevant chunks as sources. §17.7."""
        if not uploaded_texts:
            return []

        embedder = self._get_embedder()
        from sentence_transformers.util import cos_sim

        q_emb = embedder.encode(query, convert_to_tensor=True)
        candidates: list[tuple[float, dict]] = []

        for file_id, text in uploaded_texts.items():
            chunks = self._chunk_text(text)
            if not chunks:
                continue
            chunk_embs = embedder.encode(chunks, convert_to_tensor=True)
            sims = cos_sim(q_emb, chunk_embs)[0]

            for i, sim_val in enumerate(sims):
                score = float(sim_val)
                if score >= self.similarity_threshold:
                    candidates.append((score, {
                        "source_id": SourceConnector.make_source_id(f"{file_id}:{i}"),
                        "url": None,
                        "doi": None,
                        "isbn": None,
                        "title": f"Upload: {file_id} (chunk {i})",
                        "authors": ["user_upload"],
                        "publisher": None,
                        "year": None,
                        "abstract": chunks[i][:500],
                        "full_text_snippet": chunks[i][:500],
                        "source_type": "upload",
                        "reliability_score": 1.0,
                        "http_verified": False,
                        "language": "en",
                    }))

        # Sort by similarity descending, take top max_results
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in candidates[:max_results]]

    async def health_check(self) -> bool:
        try:
            self._get_embedder()
            return True
        except Exception:
            return False
