"""Semantic Search for Knowledge Spaces

Retrieves relevant chunks from a Knowledge Space using semantic similarity.

Key features:
- Query embedding generation
- Cosine similarity search with pgvector
- Top-K results ranking
- Filter by space or source

Usage:
    from services.semantic_search import search_chunks
    
    results = await search_chunks(
        session,
        query="What is RAG?",
        space_id="space-123",
        top_k=5,
    )
    
    for result in results:
        print(f"Similarity: {result['similarity']:.3f}")
        print(f"Content: {result['content'][:100]}...")

Author: DRS Implementation Team
Spec: §17 Knowledge Spaces, Task 3.1
"""

import logging
from typing import Optional

from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Chunk
from services.embedder import embed_text, EmbeddingError

logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Raised when semantic search fails."""
    pass


async def search_chunks(
    session: AsyncSession,
    query: str,
    space_id: Optional[str] = None,
    source_id: Optional[str] = None,
    top_k: int = 5,
    min_similarity: float = 0.0,
) -> list[dict]:
    """Search for relevant chunks using semantic similarity.
    
    Args:
        session: Database session
        query: Search query text
        space_id: Filter by space (optional)
        source_id: Filter by source (optional)
        top_k: Number of results to return (default 5)
        min_similarity: Minimum similarity threshold 0-1 (default 0.0)
    
    Returns:
        List of dicts with keys:
            - id (str): Chunk ID
            - content (str): Chunk text
            - similarity (float): Cosine similarity score (0-1)
            - metadata (dict): Chunk metadata
            - source_id (str): Source ID
            - space_id (str): Space ID
    
    Raises:
        SearchError: If search fails
        ValueError: If query is empty or top_k invalid
    """
    # Validate inputs
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    
    if not (0 <= min_similarity <= 1):
        raise ValueError("min_similarity must be between 0 and 1")
    
    try:
        # 1. Generate query embedding
        logger.info(f"Searching for: '{query[:50]}...'")
        
        try:
            query_embedding = embed_text(query)
        except EmbeddingError as e:
            raise SearchError(f"Failed to embed query: {e}") from e
        
        # 2. Build SQL query with pgvector cosine similarity
        # <=> operator computes cosine distance (1 - cosine_similarity)
        # We convert to similarity for easier interpretation
        
        # Base query
        sql = """
            SELECT 
                id,
                space_id,
                source_id,
                content,
                metadata,
                1 - (embedding <=> :query_embedding) AS similarity
            FROM chunks
            WHERE embedding IS NOT NULL
        """
        
        params = {"query_embedding": query_embedding}
        
        # Add filters
        if space_id:
            sql += " AND space_id = :space_id"
            params["space_id"] = space_id
        
        if source_id:
            sql += " AND source_id = :source_id"
            params["source_id"] = source_id
        
        if min_similarity > 0:
            sql += " AND (1 - (embedding <=> :query_embedding)) >= :min_similarity"
            params["min_similarity"] = min_similarity
        
        # Order by similarity and limit
        sql += """
            ORDER BY embedding <=> :query_embedding
            LIMIT :top_k
        """
        params["top_k"] = top_k
        
        # 3. Execute query
        result = await session.execute(sql_text(sql), params)
        rows = result.fetchall()
        
        # 4. Format results
        results = []
        for row in rows:
            results.append({
                "id": row.id,
                "space_id": row.space_id,
                "source_id": row.source_id,
                "content": row.content,
                "similarity": float(row.similarity),
                "metadata": row.metadata or {},
            })
        
        logger.info(f"Found {len(results)} chunks (top_k={top_k})")
        
        return results
    
    except SearchError:
        raise
    
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise SearchError(f"Search failed: {e}") from e


async def get_chunk_by_id(
    session: AsyncSession,
    chunk_id: str,
) -> Optional[dict]:
    """Get a specific chunk by ID.
    
    Args:
        session: Database session
        chunk_id: Chunk ID
    
    Returns:
        Chunk dict or None if not found
    """
    stmt = select(Chunk).where(Chunk.id == chunk_id)
    result = await session.execute(stmt)
    chunk = result.scalar_one_or_none()
    
    if not chunk:
        return None
    
    return {
        "id": chunk.id,
        "space_id": chunk.space_id,
        "source_id": chunk.source_id,
        "content": chunk.content,
        "metadata": chunk.metadata or {},
        "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
    }


if __name__ == "__main__":
    # Test semantic search
    import asyncio
    from database.connection import get_db_session
    from database.models import Space, Source
    from services.space_indexer import SpaceIndexer
    import uuid
    
    async def test_semantic_search():
        print("=" * 80)
        print("Semantic Search Test")
        print("=" * 80)
        
        # Create test space and index documents
        async with get_db_session() as session:
            space_id = str(uuid.uuid4())
            
            space = Space(id=space_id, name="Test Space")
            session.add(space)
            await session.commit()
            
            print(f"\nCreated space: {space_id}")
        
        # Create test documents
        docs = [
            (
                "rag_intro.txt",
                "Retrieval-Augmented Generation (RAG) is a technique that combines "
                "information retrieval with large language models. It retrieves relevant "
                "documents from a knowledge base and uses them as context for generation."
            ),
            (
                "embeddings.txt",
                "Embeddings are dense vector representations of text. Sentence transformers "
                "like all-MiniLM-L6-v2 convert text into 384-dimensional vectors that capture "
                "semantic meaning."
            ),
            (
                "pgvector.txt",
                "pgvector is a PostgreSQL extension for vector similarity search. It supports "
                "cosine distance, L2 distance, and inner product. The ivfflat index enables "
                "fast approximate nearest neighbor search."
            ),
        ]
        
        indexer = SpaceIndexer(chunk_size=200, chunk_overlap=20)
        
        for filename, content in docs:
            # Save to temp file
            filepath = f"/tmp/{filename}"
            with open(filepath, "w") as f:
                f.write(content)
            
            # Create source and index
            async with get_db_session() as session:
                source = Source(
                    id=str(uuid.uuid4()),
                    space_id=space_id,
                    filename=filename,
                    mime_type="text/plain",
                    storage_path=filepath,
                    status="pending",
                )
                session.add(source)
                await session.commit()
                
                await indexer.index_source(
                    session, source.id, filepath, "text/plain"
                )
                
                print(f"  Indexed: {filename}")
        
        print("\n" + "=" * 80)
        print("Search Queries")
        print("=" * 80)
        
        # Test queries
        queries = [
            "What is RAG?",
            "How do embeddings work?",
            "Tell me about vector databases",
        ]
        
        async with get_db_session() as session:
            for query in queries:
                print(f"\n🔍 Query: '{query}'")
                print("-" * 80)
                
                results = await search_chunks(
                    session,
                    query=query,
                    space_id=space_id,
                    top_k=3,
                )
                
                if not results:
                    print("   No results found.")
                else:
                    for i, result in enumerate(results, 1):
                        print(f"\n   {i}. Similarity: {result['similarity']:.3f}")
                        print(f"      Content: {result['content'][:100]}...")
                        print(f"      Source: {result['source_id']}")
        
        print("\n" + "=" * 80)
        print("✅ Test completed")
        print("=" * 80)
    
    asyncio.run(test_semantic_search())
