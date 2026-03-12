"""SpaceIndexer: Main Indexing Pipeline for Knowledge Spaces

Orchestrates the complete indexing workflow:
1. Extract text from source file (Task 2.1)
2. Chunk text semantically (Task 2.2)
3. Generate embeddings (Task 2.3)
4. Insert to database (Task 2.4)

Usage:
    from services.space_indexer import SpaceIndexer
    
    indexer = SpaceIndexer()
    
    # Index a source
    result = await indexer.index_source(
        source_id="source-123",
        file_path="/data/spaces/doc.pdf",
        mime_type="application/pdf",
    )
    
    print(f"Indexed {result['chunks_created']} chunks")

Author: DRS Implementation Team
Spec: §17 Knowledge Spaces, Task 2.5
"""

import logging
import time
from typing import Optional, Callable
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from services.text_extractor import extract_text, TextExtractionError
from services.chunker import chunk_text, ChunkingError
from services.embedder import embed_batch, EmbeddingError
from services.db_inserter import (
    batch_insert_chunks,
    delete_chunks_by_source,
    BatchInsertError,
)
from database.models import Source
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


class IndexingError(Exception):
    """Raised when indexing fails."""
    pass


class SpaceIndexer:
    """Orchestrates the full indexing pipeline.
    
    Combines text extraction, chunking, embedding, and database insertion
    into a single workflow.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        embedding_model: str = "all-MiniLM-L6-v2",
        batch_size: int = 1000,
    ):
        """Initialize indexer with configuration.
        
        Args:
            chunk_size: Target tokens per chunk
            chunk_overlap: Overlap tokens between chunks
            embedding_model: sentence-transformers model name
            batch_size: Database insert batch size
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self.batch_size = batch_size
    
    async def index_source(
        self,
        session: AsyncSession,
        source_id: str,
        file_path: str,
        mime_type: str,
        progress_callback: Optional[Callable[[str, dict], None]] = None,
    ) -> dict:
        """Index a source file (full pipeline).
        
        Args:
            session: Database session
            source_id: Source ID from database
            file_path: Path to source file
            mime_type: MIME type (e.g., "application/pdf")
            progress_callback: Optional callback(stage, data) for progress updates
        
        Returns:
            Dict with indexing results:
                - source_id (str)
                - chunks_created (int)
                - total_tokens (int)
                - elapsed_seconds (float)
                - status (str): "success" or "failed"
        
        Raises:
            IndexingError: If any step fails
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting indexing for source {source_id}")
            
            # Get source metadata
            source = await self._get_source(session, source_id)
            if not source:
                raise IndexingError(f"Source {source_id} not found")
            
            space_id = source.space_id
            
            # Update status to indexing
            await self._update_source_status(session, source_id, "indexing")
            
            # Step 1: Extract text
            self._notify_progress(progress_callback, "extracting", {"source_id": source_id})
            
            try:
                text = extract_text(file_path, mime_type)
                logger.info(f"Extracted {len(text)} characters")
            except TextExtractionError as e:
                raise IndexingError(f"Text extraction failed: {e}") from e
            
            if not text.strip():
                raise IndexingError("Extracted text is empty")
            
            # Step 2: Chunk text
            self._notify_progress(progress_callback, "chunking", {"text_length": len(text)})
            
            try:
                chunks = chunk_text(
                    text,
                    chunk_size=self.chunk_size,
                    overlap=self.chunk_overlap,
                )
                logger.info(f"Created {len(chunks)} chunks")
            except ChunkingError as e:
                raise IndexingError(f"Chunking failed: {e}") from e
            
            if not chunks:
                raise IndexingError("No chunks created")
            
            # Step 3: Generate embeddings
            self._notify_progress(progress_callback, "embedding", {"chunk_count": len(chunks)})
            
            try:
                chunk_texts = [c['content'] for c in chunks]
                embeddings = embed_batch(
                    chunk_texts,
                    model_name=self.embedding_model,
                    batch_size=32,
                    show_progress=False,
                )
                logger.info(f"Generated {len(embeddings)} embeddings")
            except EmbeddingError as e:
                raise IndexingError(f"Embedding generation failed: {e}") from e
            
            # Step 4: Prepare chunks for database
            chunks_data = []
            total_tokens = 0
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunks_data.append({
                    "space_id": space_id,
                    "source_id": source_id,
                    "content": chunk['content'],
                    "embedding": embedding,
                    "metadata": {
                        "chunk_idx": chunk['chunk_idx'],
                        "token_count": chunk['token_count'],
                        "char_count": chunk['char_count'],
                        "char_start": chunk['char_start'],
                        "char_end": chunk['char_end'],
                    },
                })
                total_tokens += chunk['token_count']
            
            # Step 5: Insert to database
            self._notify_progress(progress_callback, "inserting", {"chunk_count": len(chunks_data)})
            
            try:
                inserted_ids = await batch_insert_chunks(
                    session,
                    chunks_data,
                    batch_size=self.batch_size,
                    on_conflict="skip",
                    update_source_status=True,
                )
                logger.info(f"Inserted {len(inserted_ids)} chunks to database")
            except BatchInsertError as e:
                raise IndexingError(f"Database insertion failed: {e}") from e
            
            # Success
            elapsed = time.time() - start_time
            
            result = {
                "source_id": source_id,
                "chunks_created": len(inserted_ids),
                "total_tokens": total_tokens,
                "elapsed_seconds": elapsed,
                "status": "success",
            }
            
            logger.info(
                f"Indexing completed: {result['chunks_created']} chunks, "
                f"{result['total_tokens']} tokens in {elapsed:.2f}s"
            )
            
            self._notify_progress(progress_callback, "completed", result)
            
            return result
        
        except IndexingError as e:
            # Update source status to failed
            await self._update_source_status(session, source_id, "failed")
            logger.error(f"Indexing failed for source {source_id}: {e}")
            
            self._notify_progress(progress_callback, "failed", {"error": str(e)})
            
            raise
        
        except Exception as e:
            # Unexpected error
            await self._update_source_status(session, source_id, "failed")
            logger.error(f"Unexpected error during indexing: {e}", exc_info=True)
            
            raise IndexingError(f"Unexpected error: {e}") from e
    
    async def reindex_source(
        self,
        session: AsyncSession,
        source_id: str,
        file_path: str,
        mime_type: str,
        progress_callback: Optional[Callable[[str, dict], None]] = None,
    ) -> dict:
        """Re-index a source (delete old chunks + index).
        
        Args:
            session: Database session
            source_id: Source ID
            file_path: Path to source file
            mime_type: MIME type
            progress_callback: Progress callback
        
        Returns:
            Indexing result dict
        """
        logger.info(f"Re-indexing source {source_id}")
        
        # Delete old chunks
        self._notify_progress(progress_callback, "deleting", {"source_id": source_id})
        
        deleted_count = await delete_chunks_by_source(session, source_id)
        logger.info(f"Deleted {deleted_count} old chunks")
        
        # Index
        result = await self.index_source(
            session,
            source_id,
            file_path,
            mime_type,
            progress_callback,
        )
        
        result["chunks_deleted"] = deleted_count
        return result
    
    async def _get_source(self, session: AsyncSession, source_id: str) -> Optional[Source]:
        """Get source from database."""
        stmt = select(Source).where(Source.id == source_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _update_source_status(self, session: AsyncSession, source_id: str, status: str):
        """Update source status."""
        stmt = update(Source).where(Source.id == source_id).values(status=status)
        await session.execute(stmt)
        await session.commit()
    
    def _notify_progress(self, callback: Optional[Callable], stage: str, data: dict):
        """Notify progress callback if provided."""
        if callback:
            try:
                callback(stage, data)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")


if __name__ == "__main__":
    # Test indexer
    import asyncio
    from database.connection import get_db_session
    from database.models import Space, Source
    import uuid
    
    async def test_indexer():
        print("=" * 80)
        print("SpaceIndexer Test")
        print("=" * 80)
        
        # Create test file
        test_file = "/tmp/test_indexer.txt"
        with open(test_file, "w") as f:
            f.write(
                "Knowledge Spaces enable RAG-enhanced document generation. "
                "The system extracts text, chunks it semantically, generates embeddings, "
                "and stores everything in PostgreSQL with pgvector. "
                "This allows the Researcher node to retrieve relevant context for queries.\n\n" * 10
            )
        
        print(f"\nCreated test file: {test_file}")
        
        # Create test space and source
        async with get_db_session() as session:
            space_id = str(uuid.uuid4())
            source_id = str(uuid.uuid4())
            
            space = Space(id=space_id, name="Test Space")
            source = Source(
                id=source_id,
                space_id=space_id,
                filename="test_indexer.txt",
                mime_type="text/plain",
                storage_path=test_file,
                status="pending",
            )
            
            session.add(space)
            session.add(source)
            await session.commit()
            
            print(f"Created space: {space_id}")
            print(f"Created source: {source_id}")
        
        # Index source
        def progress_callback(stage: str, data: dict):
            print(f"  [{stage.upper()}] {data}")
        
        indexer = SpaceIndexer(chunk_size=100, chunk_overlap=20)
        
        async with get_db_session() as session:
            result = await indexer.index_source(
                session,
                source_id,
                test_file,
                "text/plain",
                progress_callback=progress_callback,
            )
        
        print("\n" + "=" * 80)
        print("Indexing Result:")
        print(f"  Source ID: {result['source_id']}")
        print(f"  Chunks created: {result['chunks_created']}")
        print(f"  Total tokens: {result['total_tokens']}")
        print(f"  Elapsed: {result['elapsed_seconds']:.2f}s")
        print(f"  Status: {result['status']}")
        print("=" * 80)
        print("\n✅ Test completed")
    
    asyncio.run(test_indexer())
