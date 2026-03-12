"""Database Batch Insert for Knowledge Spaces Chunks

Efficiently inserts chunks with embeddings into PostgreSQL.

Key features:
- Bulk insert with SQLAlchemy Core (faster than ORM)
- Transaction handling (all-or-nothing)
- Upsert support (ON CONFLICT DO UPDATE)
- Progress tracking for large batches
- Automatic source status update

Usage:
    from services.db_inserter import batch_insert_chunks
    
    chunks_data = [
        {
            "space_id": "space-123",
            "source_id": "source-456",
            "content": "chunk text...",
            "embedding": [0.1, 0.2, ...],  # 384 dims
            "metadata": {"chunk_idx": 0, "token_count": 487},
        },
        # ... more chunks
    ]
    
    inserted_ids = await batch_insert_chunks(db_session, chunks_data)
    print(f"Inserted {len(inserted_ids)} chunks")

Author: DRS Implementation Team
Spec: §17 Knowledge Spaces, Task 2.4
"""

import logging
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import insert, update, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Chunk, Source

logger = logging.getLogger(__name__)


class BatchInsertError(Exception):
    """Raised when batch insert fails."""
    pass


async def batch_insert_chunks(
    session: AsyncSession,
    chunks_data: list[dict],
    batch_size: int = 1000,
    on_conflict: str = "skip",  # "skip", "update", or "error"
    update_source_status: bool = True,
) -> list[str]:
    """Insert chunks with embeddings in bulk.
    
    Args:
        session: Async database session
        chunks_data: List of chunk dicts with keys:
            - space_id (str): Space ID
            - source_id (str): Source ID
            - content (str): Chunk text
            - embedding (list[float]): 384-dim vector
            - metadata (dict, optional): Chunk metadata
        batch_size: Insert batch size (default 1000)
        on_conflict: Conflict resolution:
            - "skip": Skip existing chunks (DO NOTHING)
            - "update": Update existing chunks (DO UPDATE)
            - "error": Raise error on conflict
        update_source_status: Update source.status to "indexed" after insert
    
    Returns:
        List of inserted chunk IDs
    
    Raises:
        BatchInsertError: If insert fails
        ValueError: If chunks_data is invalid
    """
    if not chunks_data:
        logger.warning("No chunks to insert")
        return []
    
    # Validate chunks
    _validate_chunks_data(chunks_data)
    
    inserted_ids = []
    total_chunks = len(chunks_data)
    
    try:
        logger.info(f"Inserting {total_chunks} chunks in batches of {batch_size}")
        
        # Process in batches
        for i in range(0, total_chunks, batch_size):
            batch = chunks_data[i:i + batch_size]
            
            # Prepare batch data
            batch_records = []
            for chunk_data in batch:
                chunk_id = str(uuid.uuid4())
                
                record = {
                    "id": chunk_id,
                    "space_id": chunk_data["space_id"],
                    "source_id": chunk_data["source_id"],
                    "content": chunk_data["content"],
                    "embedding": chunk_data["embedding"],
                    "metadata": chunk_data.get("metadata"),
                    "created_at": datetime.utcnow(),
                }
                batch_records.append(record)
                inserted_ids.append(chunk_id)
            
            # Insert batch
            if on_conflict == "skip":
                # INSERT ... ON CONFLICT DO NOTHING
                stmt = pg_insert(Chunk.__table__).values(batch_records)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["id"]  # Conflict on primary key
                )
                await session.execute(stmt)
            
            elif on_conflict == "update":
                # INSERT ... ON CONFLICT DO UPDATE
                stmt = pg_insert(Chunk.__table__).values(batch_records)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "content": stmt.excluded.content,
                        "embedding": stmt.excluded.embedding,
                        "metadata": stmt.excluded.metadata,
                    },
                )
                await session.execute(stmt)
            
            else:  # on_conflict == "error"
                # Regular INSERT (will fail on duplicate)
                stmt = insert(Chunk.__table__).values(batch_records)
                await session.execute(stmt)
            
            logger.info(f"Inserted batch {i // batch_size + 1}/{(total_chunks + batch_size - 1) // batch_size}")
        
        # Update source status
        if update_source_status and chunks_data:
            source_id = chunks_data[0]["source_id"]
            await _update_source_status(session, source_id, "indexed")
        
        # Commit transaction
        await session.commit()
        
        logger.info(f"Successfully inserted {len(inserted_ids)} chunks")
        return inserted_ids
    
    except Exception as e:
        await session.rollback()
        logger.error(f"Batch insert failed: {e}")
        raise BatchInsertError(f"Failed to insert chunks: {e}") from e


async def delete_chunks_by_source(
    session: AsyncSession,
    source_id: str,
) -> int:
    """Delete all chunks for a source (for re-indexing).
    
    Args:
        session: Async database session
        source_id: Source ID
    
    Returns:
        Number of deleted chunks
    
    Raises:
        BatchInsertError: If delete fails
    """
    try:
        logger.info(f"Deleting chunks for source {source_id}")
        
        # Count before delete
        count_stmt = select(Chunk).where(Chunk.source_id == source_id)
        result = await session.execute(count_stmt)
        count = len(result.scalars().all())
        
        # Delete
        from sqlalchemy import delete
        stmt = delete(Chunk).where(Chunk.source_id == source_id)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Deleted {count} chunks")
        return count
    
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete chunks: {e}")
        raise BatchInsertError(f"Failed to delete chunks: {e}") from e


async def get_chunk_count(
    session: AsyncSession,
    space_id: Optional[str] = None,
    source_id: Optional[str] = None,
) -> int:
    """Get chunk count for space or source.
    
    Args:
        session: Async database session
        space_id: Filter by space (optional)
        source_id: Filter by source (optional)
    
    Returns:
        Chunk count
    """
    from sqlalchemy import func as sql_func
    
    stmt = select(sql_func.count(Chunk.id))
    
    if source_id:
        stmt = stmt.where(Chunk.source_id == source_id)
    elif space_id:
        stmt = stmt.where(Chunk.space_id == space_id)
    
    result = await session.execute(stmt)
    return result.scalar() or 0


def _validate_chunks_data(chunks_data: list[dict]) -> None:
    """Validate chunk data structure.
    
    Args:
        chunks_data: List of chunk dicts
    
    Raises:
        ValueError: If validation fails
    """
    if not chunks_data:
        raise ValueError("chunks_data cannot be empty")
    
    required_keys = {"space_id", "source_id", "content", "embedding"}
    
    for i, chunk in enumerate(chunks_data):
        # Check keys
        missing = required_keys - set(chunk.keys())
        if missing:
            raise ValueError(
                f"Chunk {i} missing required keys: {missing}"
            )
        
        # Check types
        if not isinstance(chunk["space_id"], str):
            raise ValueError(f"Chunk {i}: space_id must be string")
        
        if not isinstance(chunk["source_id"], str):
            raise ValueError(f"Chunk {i}: source_id must be string")
        
        if not isinstance(chunk["content"], str):
            raise ValueError(f"Chunk {i}: content must be string")
        
        if not chunk["content"].strip():
            raise ValueError(f"Chunk {i}: content cannot be empty")
        
        # Check embedding
        if not isinstance(chunk["embedding"], list):
            raise ValueError(f"Chunk {i}: embedding must be list")
        
        if len(chunk["embedding"]) != 384:
            raise ValueError(
                f"Chunk {i}: embedding must have 384 dimensions, "
                f"got {len(chunk['embedding'])}"
            )
        
        if not all(isinstance(x, (float, int)) for x in chunk["embedding"]):
            raise ValueError(f"Chunk {i}: embedding must contain only numbers")


async def _update_source_status(
    session: AsyncSession,
    source_id: str,
    status: str,
) -> None:
    """Update source status.
    
    Args:
        session: Async database session
        source_id: Source ID
        status: New status (e.g., "indexed", "failed")
    """
    stmt = (
        update(Source)
        .where(Source.id == source_id)
        .values(status=status)
    )
    await session.execute(stmt)
    logger.info(f"Updated source {source_id} status to '{status}'")


if __name__ == "__main__":
    # Test batch insert
    import asyncio
    from database.connection import get_db_session
    
    async def test_batch_insert():
        print("=" * 80)
        print("Batch Insert Test")
        print("=" * 80)
        
        # Prepare test data
        chunks_data = [
            {
                "space_id": "test-space",
                "source_id": "test-source",
                "content": f"Test chunk {i}: Lorem ipsum dolor sit amet.",
                "embedding": [0.1 * (i % 10)] * 384,  # Dummy embedding
                "metadata": {"chunk_idx": i, "token_count": 50},
            }
            for i in range(10)
        ]
        
        print(f"\nPrepared {len(chunks_data)} test chunks")
        print(f"Sample chunk 0: {chunks_data[0]['content'][:50]}...")
        print(f"Sample embedding dims: {len(chunks_data[0]['embedding'])}")
        
        # Insert
        async with get_db_session() as session:
            try:
                inserted_ids = await batch_insert_chunks(
                    session,
                    chunks_data,
                    batch_size=5,  # Small batch for demo
                    on_conflict="skip",
                )
                
                print(f"\n✅ Inserted {len(inserted_ids)} chunks")
                print(f"   First ID: {inserted_ids[0]}")
                print(f"   Last ID: {inserted_ids[-1]}")
                
                # Get count
                count = await get_chunk_count(session, source_id="test-source")
                print(f"\n   Total chunks for source: {count}")
            
            except BatchInsertError as e:
                print(f"\n❌ Insert failed: {e}")
        
        print("\n" + "=" * 80)
        print("✅ Test completed")
        print("=" * 80)
    
    asyncio.run(test_batch_insert())
