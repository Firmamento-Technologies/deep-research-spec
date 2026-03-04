"""API Endpoints for Knowledge Spaces Management

Provides REST API for:
- Uploading files to spaces
- Triggering indexing (chunking + embedding)
- Listing sources and chunk counts
- Re-indexing and deletion

Author: DRS Implementation Team
Spec: TH.1-3 Knowledge Spaces
Date: 2026-03-04
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    BackgroundTasks,
    status,
)
from pydantic import BaseModel, Field
import asyncpg

from services.space_indexer import SpaceIndexer
from core.sse import emit_event
from core.database import get_db_pool


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/spaces', tags=['Knowledge Spaces'])


# Pydantic schemas
class SourceUploadResponse(BaseModel):
    source_id: uuid.UUID
    space_id: uuid.UUID
    filename: str
    file_size: int
    status: str = "indexing"
    message: str = "File uploaded, indexing in progress"


class SourceDetail(BaseModel):
    id: uuid.UUID
    space_id: uuid.UUID
    filename: str
    file_size: int
    chunk_count: int
    status: str
    created_at: str
    indexed_at: Optional[str]


class ReindexResponse(BaseModel):
    space_id: uuid.UUID
    sources_indexed: int
    total_chunks: int
    errors: list[dict]
    status: str


# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.md', '.markdown'}
UPLOAD_DIR = Path("/app/data/knowledge_spaces")  # Container path


async def save_uploaded_file(
    file: UploadFile,
    space_id: uuid.UUID,
    source_id: uuid.UUID,
) -> Path:
    """Save uploaded file to disk.
    
    Returns:
        Path to saved file
    
    Raises:
        HTTPException: If validation fails or save error
    """
    # Validate extension
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {suffix}. "
                   f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    
    # Validate size (read in chunks to avoid loading entire file)
    file_size = 0
    chunks = []
    while chunk := await file.read(8192):
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {MAX_FILE_SIZE // (1024*1024)} MB limit",
            )
        chunks.append(chunk)
    
    # Create directory structure: /app/data/knowledge_spaces/{space_id}/
    space_dir = UPLOAD_DIR / str(space_id)
    space_dir.mkdir(parents=True, exist_ok=True)
    
    # Save with source_id as filename (preserve extension)
    file_path = space_dir / f"{source_id}{suffix}"
    
    with open(file_path, 'wb') as f:
        for chunk in chunks:
            f.write(chunk)
    
    logger.info(f"[API] Saved file: {file_path} ({file_size} bytes)")
    return file_path


async def background_index_source(
    space_id: uuid.UUID,
    source_id: uuid.UUID,
    file_path: Path,
    db_pool: asyncpg.Pool,
):
    """Background task: index a source file.
    
    Emits SSE events for progress tracking.
    """
    try:
        emit_event(
            str(space_id),
            "SOURCE_INDEXING_START",
            {"source_id": str(source_id), "filename": file_path.name},
        )
        
        indexer = SpaceIndexer(db_pool)
        stats = await indexer.index_source(
            space_id=space_id,
            source_id=source_id,
            file_path=file_path,
            reindex=False,
        )
        
        # Update source status in DB
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sources 
                SET status = 'indexed', indexed_at = NOW()
                WHERE id = $1
                """,
                source_id,
            )
        
        emit_event(
            str(space_id),
            "SOURCE_INDEXING_COMPLETE",
            {
                "source_id": str(source_id),
                "chunks_created": stats['chunks_created'],
                "duration_seconds": stats['duration_seconds'],
            },
        )
        
    except Exception as e:
        logger.error(f"[API] Indexing failed for source {source_id}: {e}")
        
        # Update source status to failed
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE sources 
                SET status = 'failed', error_message = $2
                WHERE id = $1
                """,
                source_id,
                str(e),
            )
        
        emit_event(
            str(space_id),
            "SOURCE_INDEXING_FAILED",
            {"source_id": str(source_id), "error": str(e)},
        )


@router.post(
    "/{space_id}/sources",
    response_model=SourceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_source_to_space(
    space_id: uuid.UUID,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: asyncpg.Pool = Depends(get_db_pool),
):
    """Upload a file to a Knowledge Space and trigger indexing.
    
    The file is saved to disk and indexing runs asynchronously in the background.
    Progress can be tracked via SSE events.
    
    Args:
        space_id: UUID of the Knowledge Space
        file: Uploaded file (PDF/DOCX/TXT/MD, max 50MB)
    
    Returns:
        SourceUploadResponse with source_id and indexing status
    
    Raises:
        404: Space not found
        400: Invalid file type
        413: File too large
    """
    # Verify space exists
    async with db.acquire() as conn:
        space = await conn.fetchrow(
            "SELECT id, name FROM spaces WHERE id = $1",
            space_id,
        )
    
    if not space:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Space {space_id} not found",
        )
    
    # Create source record
    source_id = uuid.uuid4()
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sources (id, space_id, filename, status)
            VALUES ($1, $2, $3, 'uploading')
            """,
            source_id,
            space_id,
            file.filename,
        )
    
    # Save file to disk
    try:
        file_path = await save_uploaded_file(file, space_id, source_id)
    except HTTPException:
        # Delete source record on failure
        async with db.acquire() as conn:
            await conn.execute("DELETE FROM sources WHERE id = $1", source_id)
        raise
    
    # Update source with file_path and size
    file_size = file_path.stat().st_size
    async with db.acquire() as conn:
        await conn.execute(
            """
            UPDATE sources 
            SET file_path = $2, file_size = $3, status = 'indexing'
            WHERE id = $1
            """,
            source_id,
            str(file_path),
            file_size,
        )
    
    # Trigger background indexing
    background_tasks.add_task(
        background_index_source,
        space_id,
        source_id,
        file_path,
        db,
    )
    
    logger.info(
        f"[API] Source upload queued: space={space_id}, "
        f"source={source_id}, file={file.filename}"
    )
    
    return SourceUploadResponse(
        source_id=source_id,
        space_id=space_id,
        filename=file.filename,
        file_size=file_size,
    )


@router.get("/{space_id}/sources", response_model=list[SourceDetail])
async def list_sources_in_space(
    space_id: uuid.UUID,
    db: asyncpg.Pool = Depends(get_db_pool),
):
    """List all sources in a Knowledge Space with chunk counts.
    
    Returns:
        List of SourceDetail with chunk_count aggregated from chunks table
    """
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                s.id,
                s.space_id,
                s.filename,
                s.file_size,
                s.status,
                s.created_at,
                s.indexed_at,
                COALESCE(COUNT(c.id), 0) AS chunk_count
            FROM sources s
            LEFT JOIN chunks c ON c.source_id = s.id
            WHERE s.space_id = $1
            GROUP BY s.id
            ORDER BY s.created_at DESC
            """,
            space_id,
        )
    
    return [
        SourceDetail(
            id=row['id'],
            space_id=row['space_id'],
            filename=row['filename'],
            file_size=row['file_size'] or 0,
            chunk_count=row['chunk_count'],
            status=row['status'],
            created_at=row['created_at'].isoformat(),
            indexed_at=row['indexed_at'].isoformat() if row['indexed_at'] else None,
        )
        for row in rows
    ]


@router.post("/{space_id}/reindex", response_model=ReindexResponse)
async def reindex_space(
    space_id: uuid.UUID,
    db: asyncpg.Pool = Depends(get_db_pool),
):
    """Re-index all sources in a Knowledge Space.
    
    Deletes existing chunks and regenerates embeddings for all sources.
    Useful after upgrading embedding model or fixing indexing bugs.
    
    Args:
        space_id: UUID of the Knowledge Space
    
    Returns:
        ReindexResponse with aggregate stats
    
    Raises:
        404: Space not found
    """
    # Verify space exists
    async with db.acquire() as conn:
        space = await conn.fetchrow(
            "SELECT id FROM spaces WHERE id = $1",
            space_id,
        )
    
    if not space:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Space {space_id} not found",
        )
    
    logger.info(f"[API] Re-indexing space {space_id}")
    
    indexer = SpaceIndexer(db)
    result = await indexer.index_all_sources_in_space(
        space_id=space_id,
        reindex=True,
    )
    
    return ReindexResponse(
        space_id=space_id,
        sources_indexed=result['sources_indexed'],
        total_chunks=result['total_chunks'],
        errors=result['errors'],
        status="completed" if not result['errors'] else "partial",
    )


@router.delete("/{space_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    space_id: uuid.UUID,
    source_id: uuid.UUID,
    db: asyncpg.Pool = Depends(get_db_pool),
):
    """Delete a source and all its chunks.
    
    Args:
        space_id: UUID of the Knowledge Space
        source_id: UUID of the source to delete
    
    Raises:
        404: Source not found or doesn't belong to space
    """
    async with db.acquire() as conn:
        # Verify source exists and belongs to space
        source = await conn.fetchrow(
            "SELECT id, file_path FROM sources WHERE id = $1 AND space_id = $2",
            source_id,
            space_id,
        )
        
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found in space {space_id}",
            )
        
        # Delete from DB (cascade deletes chunks)
        await conn.execute("DELETE FROM sources WHERE id = $1", source_id)
    
    # Delete file from disk
    if source['file_path']:
        file_path = Path(source['file_path'])
        if file_path.exists():
            file_path.unlink()
            logger.info(f"[API] Deleted file: {file_path}")
    
    logger.info(f"[API] Deleted source {source_id} and chunks")
