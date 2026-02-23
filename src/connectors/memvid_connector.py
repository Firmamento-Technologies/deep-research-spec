"""MemvidConnector — RAG on local knowledge base (§RAG_SHINE_INTEGRATION §1).

Provides local-first retrieval over a Memvid video-encoded vector store,
using bge-m3 embeddings for multilingual similarity search.  Designed as
first-priority connector in the Researcher cascade: results from this
connector reduce external API calls (sonar-pro / Tavily / Brave).

Dependencies (install via ``pip install -r requirements-shine.txt``):
    - langchain-memvid   (Memvid vector store integration)
    - FlagEmbedding      (bge-m3 multilingual embeddings)

If the knowledge-base file is missing or dependencies are not installed the
connector degrades gracefully — ``search()`` returns ``[]`` and the
Researcher cascades to the next connector.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.connectors.base import SourceConnector, SourceType

logger = logging.getLogger(__name__)


class MemvidConnector(SourceConnector):
    """RAG on local knowledge base (specs, uploaded PDFs, SHINE paper).

    Implements the ``SourceConnector`` ABC so it can be used transparently
    in the Researcher connector cascade alongside academic / web connectors.

    Attributes:
        connector_id:    ``"memvid_local"``
        source_type:     ``"upload"``  (matches existing SourceType literal)
        reliability_base: ``0.90``     (local docs are highly trusted)
    """

    connector_id: str = "memvid_local"
    source_type: SourceType = "upload"
    reliability_base: float = 0.90
    enabled: bool = True

    def __init__(
        self,
        knowledge_path: str = "drs_knowledge.mp4",
        *,
        use_fp16: bool = True,
    ) -> None:
        self.knowledge_path = knowledge_path
        self._use_fp16 = use_fp16

        # Lazy-loaded heavy dependencies
        self._encoder: Any | None = None
        self._store: Any | None = None

    # ── Private helpers ──────────────────────────────────────────────────

    def _get_encoder(self) -> Any:
        """Lazy-load bge-m3 encoder (FlagEmbedding)."""
        if self._encoder is None:
            try:
                from FlagEmbedding import FlagModel  # type: ignore[import-untyped]
                self._encoder = FlagModel("BAAI/bge-m3", use_fp16=self._use_fp16)
                logger.info("bge-m3 encoder loaded (fp16=%s)", self._use_fp16)
            except ImportError:
                logger.warning(
                    "FlagEmbedding not installed — MemvidConnector disabled. "
                    "Install with: pip install FlagEmbedding"
                )
                raise
        return self._encoder

    def _get_store(self) -> Any:
        """Lazy-load Memvid knowledge base from disk."""
        if self._store is None:
            try:
                from langchain.vectorstores import Memvid  # type: ignore[import-untyped]
                self._store = Memvid.load(self.knowledge_path)
                logger.info("Memvid KB loaded: %s", self.knowledge_path)
            except ImportError:
                logger.warning(
                    "langchain-memvid not installed — MemvidConnector disabled. "
                    "Install with: pip install langchain-memvid"
                )
                raise
            except FileNotFoundError:
                logger.warning(
                    "Knowledge base not found at '%s' — MemvidConnector will "
                    "return empty results. Build with: "
                    "python scripts/build_memvid_kb.py --input docs/ --output %s",
                    self.knowledge_path,
                    self.knowledge_path,
                )
                raise
        return self._store

    # ── SourceConnector ABC implementation ───────────────────────────────

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search local knowledge base via Memvid similarity search.

        Args:
            query:       Natural-language search query (section scope or
                         targeted research question).
            max_results: Maximum chunks to return (default 5).

        Returns:
            List of source dicts compatible with ``SourceRanker.rank()``.
            Empty list on any failure (missing KB, missing deps, etc.).
        """
        try:
            store = self._get_store()
            chunks = store.similarity_search(query, k=max_results)
            sources = [self._chunk_to_source(chunk) for chunk in chunks]
            logger.info(
                "memvid_local: %d results for query '%.60s…'",
                len(sources),
                query,
            )
            return sources
        except (ImportError, FileNotFoundError):
            # Graceful degradation — cascade to external connectors
            return []
        except Exception:
            logger.exception("MemvidConnector.search() unexpected error")
            return []

    async def health_check(self) -> bool:
        """Return True if Memvid KB and encoder are loadable."""
        try:
            self._get_encoder()
            self._get_store()
            return True
        except Exception:
            return False

    # ── Source conversion ────────────────────────────────────────────────

    def _chunk_to_source(self, chunk: Any) -> dict:
        """Convert a Memvid/LangChain ``Document`` chunk to a source dict.

        The returned dict matches the field names expected by
        ``SourceRanker.rank()`` (see ``RankedSource`` in ``base.py``).
        """
        meta = getattr(chunk, "metadata", {})
        doc_id = meta.get("doc_id", "unknown")
        chunk_id = meta.get("chunk_id", 0)
        identifier = f"local:{doc_id}:{chunk_id}"

        return {
            "source_id": SourceConnector.make_source_id(identifier),
            "url": meta.get("url"),
            "doi": None,
            "isbn": None,
            "title": meta.get("title", "Local Document"),
            "authors": ["local_kb"],
            "publisher": "memvid_local",
            "year": None,
            "abstract": getattr(chunk, "page_content", "")[:500],
            "full_text_snippet": getattr(chunk, "page_content", "")[:500],
            "source_type": "upload",
            "reliability_score": self.reliability_base,
            "http_verified": False,
            "language": meta.get("language", "en"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            # Extra metadata for traceability
            "_memvid_doc_id": doc_id,
            "_memvid_chunk_id": chunk_id,
        }
