"""RAG Retriever — Vector Search for Knowledge Spaces

This service performs semantic search over private document chunks
stored in Knowledge Spaces.

Usage:
    retriever = RAGRetriever(db_pool)
    sources = await retriever.retrieve(
        query="What are the budget control mechanisms?",
        space_ids=[uuid.UUID("..."), ...],
        top_k=5,
    )

Author: DRS Implementation Team
Spec: TH.1-3 Knowledge Spaces, §5.2 Researcher
Date: 2026-03-04
"""

import logging
import uuid
import hashlib
from typing import List, Optional
from dataclasses import dataclass

import asyncpg
from sentence_transformers import SentenceTransformer

from services.space_indexer import get_embedding_model


logger = logging.getLogger(__name__)


@dataclass
class Source:
    """Source schema per DocumentState (§4.6)."""
    id: str
    type: str  # "knowledge_space_chunk"
    url: Optional[str]
    title: str
    content: str
    reliability: float  # 0.95 for Knowledge Spaces
    timestamp: str
    metadata: dict


class RAGRetriever:
    """Vector similarity search over Knowledge Space chunks."""
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embedding_model: Optional[SentenceTransformer] = None,
    ):
        """
        Args:
            db_pool: AsyncPG connection pool
            embedding_model: Optional pre-loaded model (else lazy-load)
        """
        self.db = db_pool
        self.embedding_model = embedding_model or get_embedding_model()
    
    async def retrieve(
        self,
        query: str,
        space_ids: List[uuid.UUID],
        top_k: int = 5,
        similarity_threshold: float = 0.70,
    ) -> List[Source]:
        """Retrieve top-K relevant chunks from Knowledge Spaces.
        
        Args:
            query: User query or section context
            space_ids: List of Knowledge Space UUIDs to search in
            top_k: Maximum number of chunks to retrieve
            similarity_threshold: Minimum cosine similarity (0-1)
        
        Returns:
            List of Source objects with type="knowledge_space_chunk"
            Sorted by similarity score (highest first)
        
        Raises:
            ValueError: If space_ids is empty or query is blank
        """
        if not space_ids:
            logger.warning("[RAGRetriever] No space_ids provided, returning empty")
            return []
        
        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        logger.info(
            f"[RAGRetriever] Retrieving from {len(space_ids)} spaces: "
            f"query='{query[:50]}...', top_k={top_k}"
        )
        
        # Step 1: Embed query
        query_embedding = self.embedding_model.encode(
            [query],
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        
        # Step 2: Vector similarity search via pgvector
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    c.id,
                    c.content,
                    c.created_at,
                    c.metadata,
                    s.filename,
                    s.space_id,
                    sp.name AS space_name,
                    1 - (c.embedding <=> $1::vector) AS similarity
                FROM chunks c
                JOIN sources s ON c.source_id = s.id
                JOIN spaces sp ON c.space_id = sp.id
                WHERE c.space_id = ANY($2::uuid[])
                  AND 1 - (c.embedding <=> $1::vector) >= $3
                ORDER BY similarity DESC
                LIMIT $4
                """,
                query_embedding.tolist(),  # pgvector expects list
                space_ids,
                similarity_threshold,
                top_k,
            )
        
        if not rows:
            logger.info(
                f"[RAGRetriever] No chunks found above threshold {similarity_threshold}"
            )
            return []
        
        logger.info(
            f"[RAGRetriever] Retrieved {len(rows)} chunks "
            f"(similarity range: {rows[-1]['similarity']:.3f} - {rows[0]['similarity']:.3f})"
        )
        
        # Step 3: Convert to Source objects
        sources = []
        seen_hashes = set()  # Deduplication
        
        for row in rows:
            # Deduplicate by content hash
            content_hash = hashlib.md5(row['content'].encode()).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            
            source = Source(
                id=f"ks_chunk_{row['id']}",
                type="knowledge_space_chunk",
                url=None,  # Chunks don't have URLs
                title=f"{row['space_name']} — {row['filename']}",
                content=row['content'],
                reliability=0.95,  # High reliability for user's own documents
                timestamp=row['created_at'].isoformat(),
                metadata={
                    'chunk_id': str(row['id']),
                    'space_id': str(row['space_id']),
                    'space_name': row['space_name'],
                    'filename': row['filename'],
                    'similarity': round(row['similarity'], 3),
                },
            )
            sources.append(source)
        
        return sources
    
    async def get_chunk_by_id(self, chunk_id: uuid.UUID) -> Optional[Source]:
        """Retrieve a specific chunk by ID.
        
        Useful for fetching context around a retrieved chunk.
        
        Args:
            chunk_id: UUID of the chunk
        
        Returns:
            Source object or None if not found
        """
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    c.id,
                    c.content,
                    c.created_at,
                    c.metadata,
                    s.filename,
                    s.space_id,
                    sp.name AS space_name
                FROM chunks c
                JOIN sources s ON c.source_id = s.id
                JOIN spaces sp ON c.space_id = sp.id
                WHERE c.id = $1
                """,
                chunk_id,
            )
        
        if not row:
            return None
        
        return Source(
            id=f"ks_chunk_{row['id']}",
            type="knowledge_space_chunk",
            url=None,
            title=f"{row['space_name']} — {row['filename']}",
            content=row['content'],
            reliability=0.95,
            timestamp=row['created_at'].isoformat(),
            metadata={
                'chunk_id': str(row['id']),
                'space_id': str(row['space_id']),
                'space_name': row['space_name'],
                'filename': row['filename'],
            },
        )
    
    async def count_chunks_in_spaces(self, space_ids: List[uuid.UUID]) -> int:
        """Get total number of indexed chunks across spaces.
        
        Useful for pre-flight checks.
        
        Args:
            space_ids: List of Knowledge Space UUIDs
        
        Returns:
            Total chunk count
        """
        if not space_ids:
            return 0
        
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) FROM chunks WHERE space_id = ANY($1::uuid[])",
                space_ids,
            )
        
        return row['count'] if row else 0


# Convenience function for Researcher node
async def retrieve_chunks_for_spaces(
    query: str,
    space_ids: List[uuid.UUID],
    db_pool: asyncpg.Pool,
    top_k: int = 5,
) -> List[Source]:
    """Convenience wrapper for Researcher node integration.
    
    Usage in researcher_node:
        from services.rag_retriever import retrieve_chunks_for_spaces
        
        rag_sources = await retrieve_chunks_for_spaces(
            query=state['current_section']['query'],
            space_ids=state['config']['space_ids'],
            db_pool=db,
        )
        
        state['current_sources'].extend(rag_sources)
    
    Args:
        query: Section query or research question
        space_ids: Knowledge Spaces to search
        db_pool: Database connection pool
        top_k: Maximum chunks to retrieve
    
    Returns:
        List of Source objects (empty if no spaces or no matches)
    """
    if not space_ids:
        return []
    
    retriever = RAGRetriever(db_pool)
    return await retriever.retrieve(
        query=query,
        space_ids=space_ids,
        top_k=top_k,
        similarity_threshold=0.70,
    )


if __name__ == '__main__':
    # Test embedding locally (no DB required)
    print("=" * 80)
    print("RAG Retriever — Local Test")
    print("=" * 80)
    
    from services.space_indexer import get_embedding_model
    
    model = get_embedding_model()
    
    # Sample queries
    queries = [
        "What are the budget control mechanisms?",
        "How does the jury system work?",
        "Mixture-of-Writers implementation details",
    ]
    
    print("\nGenerating embeddings for sample queries...\n")
    
    for query in queries:
        embedding = model.encode([query], show_progress_bar=False)[0]
        print(f"Query: {query}")
        print(f"Embedding shape: {embedding.shape}")
        print(f"First 5 dims: {embedding[:5]}")
        print("-" * 80)
