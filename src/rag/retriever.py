"""RAG retriever — query pgvector chunks per Knowledge Spaces.

Modulo autonomo usato dal researcher node (TH.3) per recuperare chunk
indicizzati da file/URL caricati negli spazi selezionati dall'utente.

Embedder: sentence-transformers/all-MiniLM-L6-v2 (stesso di space_service.py).
DB: pgvector via SQLAlchemy async (backend/database/connection.py).
"""

from __future__ import annotations

import logging
from typing import Any

import torch
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Import async engine factory da backend/database/connection
try:
    from backend.database.connection import get_async_engine
except ImportError:
    # Fallback per test standalone (src/ eseguito senza backend/)
    from database.connection import get_async_engine  # type: ignore

logger = logging.getLogger(__name__)

# ── Embedder singleton ────────────────────────────────────────────────────────
_EMBEDDER: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    """Lazy-load embedder (stesso modello di space_service.py)."""
    global _EMBEDDER
    if _EMBEDDER is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _EMBEDDER = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device=device)
        logger.info("Embedder loaded on %s", device)
    return _EMBEDDER


# ── Main retrieval function ───────────────────────────────────────────────────

async def retrieve_chunks_for_spaces(
    space_ids: list[str],
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Recupera i top_k chunk più rilevanti dagli spazi specificati.

    Args:
        space_ids: Lista di UUID degli spazi da cui recuperare chunk.
                   Se vuota, ritorna [].
        query:     Stringa di ricerca (es. scope della sezione).
        top_k:     Numero massimo di chunk da ritornare (default 10).

    Returns:
        Lista di dict con chiavi:
          - id: UUID del chunk (str)
          - space_id: UUID dello spazio (str)
          - source_id: UUID della fonte (str)
          - content: Testo del chunk (str)
          - distance: Distanza coseno embedding (float, più basso = più rilevante)

    Esempio:
        >>> chunks = await retrieve_chunks_for_spaces(
        ...     space_ids=["abc-123", "def-456"],
        ...     query="machine learning applications in healthcare",
        ...     top_k=5,
        ... )
        >>> len(chunks)
        5
        >>> chunks[0]["content"][:50]
        'Recent advances in ML-based diagnostics have shown...'
    """
    if not space_ids:
        logger.debug("retrieve_chunks_for_spaces: empty space_ids, returning []")
        return []

    if not query.strip():
        logger.warning("retrieve_chunks_for_spaces: empty query, returning []")
        return []

    # Genera embedding della query
    embedder = _get_embedder()
    query_vec = embedder.encode(query, normalize_embeddings=True).tolist()

    # Query pgvector (cosine distance via <=> operator)
    # Tabella: chunks (id, space_id, source_id, content, embedding vector(384))
    # Index: CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops);
    engine: AsyncEngine = get_async_engine()

    sql = text("""
        SELECT
            id::text,
            space_id::text,
            source_id::text,
            content,
            embedding <=> CAST(:query_vec AS vector) AS distance
        FROM chunks
        WHERE space_id = ANY(:space_ids)
        ORDER BY embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
    """)

    async with engine.begin() as conn:
        result = await conn.execute(
            sql,
            {
                "query_vec": query_vec,
                "space_ids": space_ids,
                "top_k": top_k,
            },
        )
        rows = result.fetchall()

    chunks = [
        {
            "id": row[0],
            "space_id": row[1],
            "source_id": row[2],
            "content": row[3],
            "distance": float(row[4]),
        }
        for row in rows
    ]

    logger.info(
        "retrieve_chunks_for_spaces: query='%s', space_ids=%s, top_k=%d → %d chunks",
        query[:60],
        space_ids,
        top_k,
        len(chunks),
    )

    return chunks
