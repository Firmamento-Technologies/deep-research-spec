"""Knowledge Spaces API Endpoints

REST API for managing Knowledge Spaces and sources.

Endpoints:
- POST   /spaces                        - Create space
- GET    /spaces                        - List spaces
- GET    /spaces/:id                    - Get space
- DELETE /spaces/:id                    - Delete space
- POST   /spaces/:id/sources            - Upload source file
- GET    /spaces/:id/sources            - List sources
- DELETE /spaces/:id/sources/:source_id - Delete source
- POST   /spaces/:id/reindex            - Re-index all sources
- POST   /spaces/:id/search             - Semantic search
- GET    /spaces/:id/sources/:source_id/progress - SSE progress stream

Author: DRS Implementation Team
Spec: §17 Knowledge Spaces, Task 2.6 + 3.1
"""

import logging
import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sql_func, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db_session
from database.models import Space, Source, Chunk
from services.space_indexer import SpaceIndexer, IndexingError
from services.db_inserter import get_chunk_count
from services.semantic_search import search_chunks, SearchError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spaces", tags=["Knowledge Spaces"])

# Configuration
UPLOAD_DIR = Path("/data/spaces")  # Or from env: os.getenv("SPACES_UPLOAD_DIR")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
    "text/plain",
    "text/markdown",
    "text/html",
}

# Ensure upload directory exists
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSpaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    user_id: Optional[str] = None


class SpaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    user_id: Optional[str]
    created_at: str
    updated_at: str
    source_count: int
    chunk_count: int


class SourceResponse(BaseModel):
    id: str
    space_id: str
    filename: str
    mime_type: Optional[str]
    file_size: Optional[int]
    status: str
    created_at: str
    chunk_count: int


class IndexingResultResponse(BaseModel):
    source_id: str
    chunks_created: int
    total_tokens: int
    elapsed_seconds: float
    status: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=100)
    min_similarity: float = Field(0.0, ge=0.0, le=1.0)


class SearchResultResponse(BaseModel):
    id: str
    content: str
    similarity: float
    metadata: dict
    source_id: str
    space_id: str


# ============================================================================
# Space Endpoints
# ============================================================================

@router.post("", response_model=SpaceResponse, status_code=201)
async def create_space(
    request: CreateSpaceRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new Knowledge Space."""
    space = Space(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        user_id=request.user_id,
    )
    
    session.add(space)
    await session.commit()
    await session.refresh(space)
    
    logger.info(f"Created space {space.id}: {space.name}")
    
    return SpaceResponse(
        id=space.id,
        name=space.name,
        description=space.description,
        user_id=space.user_id,
        created_at=space.created_at.isoformat(),
        updated_at=space.updated_at.isoformat(),
        source_count=0,
        chunk_count=0,
    )


@router.get("", response_model=list[SpaceResponse])
async def list_spaces(
    user_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
):
    """List all Knowledge Spaces (optionally filtered by user)."""
    stmt = select(Space)
    
    if user_id:
        stmt = stmt.where(Space.user_id == user_id)
    
    stmt = stmt.order_by(Space.created_at.desc())
    
    result = await session.execute(stmt)
    spaces = result.scalars().all()
    
    # Get counts for each space
    response = []
    for space in spaces:
        source_count_stmt = select(sql_func.count(Source.id)).where(Source.space_id == space.id)
        source_count = (await session.execute(source_count_stmt)).scalar() or 0
        
        chunk_count = await get_chunk_count(session, space_id=space.id)
        
        response.append(SpaceResponse(
            id=space.id,
            name=space.name,
            description=space.description,
            user_id=space.user_id,
            created_at=space.created_at.isoformat(),
            updated_at=space.updated_at.isoformat(),
            source_count=source_count,
            chunk_count=chunk_count,
        ))
    
    return response


@router.get("/{space_id}", response_model=SpaceResponse)
async def get_space(
    space_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get a specific Knowledge Space."""
    stmt = select(Space).where(Space.id == space_id)
    result = await session.execute(stmt)
    space = result.scalar_one_or_none()
    
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    
    # Get counts
    source_count_stmt = select(sql_func.count(Source.id)).where(Source.space_id == space.id)
    source_count = (await session.execute(source_count_stmt)).scalar() or 0
    
    chunk_count = await get_chunk_count(session, space_id=space.id)
    
    return SpaceResponse(
        id=space.id,
        name=space.name,
        description=space.description,
        user_id=space.user_id,
        created_at=space.created_at.isoformat(),
        updated_at=space.updated_at.isoformat(),
        source_count=source_count,
        chunk_count=chunk_count,
    )


@router.delete("/{space_id}", status_code=204)
async def delete_space(
    space_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a Knowledge Space (cascades to sources and chunks)."""
    stmt = select(Space).where(Space.id == space_id)
    result = await session.execute(stmt)
    space = result.scalar_one_or_none()
    
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    
    await session.delete(space)
    await session.commit()
    
    logger.info(f"Deleted space {space_id}")
    
    return


# ============================================================================
# Source Endpoints
# ============================================================================

@router.post("/{space_id}/sources", response_model=IndexingResultResponse, status_code=201)
async def upload_source(
    space_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
):
    """Upload a file to a Knowledge Space and trigger indexing."""
    # Validate space exists
    stmt = select(Space).where(Space.id == space_id)
    result = await session.execute(stmt)
    space = result.scalar_one_or_none()
    
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    
    # Validate file
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    # Create source
    source_id = str(uuid.uuid4())
    storage_path = UPLOAD_DIR / space_id / f"{source_id}_{file.filename}"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save file
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(content)} bytes. Max: {MAX_FILE_SIZE} bytes"
        )
    
    with open(storage_path, "wb") as f:
        f.write(content)
    
    logger.info(f"Saved file {file.filename} to {storage_path}")
    
    # Create source record
    source = Source(
        id=source_id,
        space_id=space_id,
        filename=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        storage_path=str(storage_path),
        status="pending",
    )
    
    session.add(source)
    await session.commit()
    
    # Index source
    indexer = SpaceIndexer()
    
    try:
        result = await indexer.index_source(
            session,
            source_id,
            str(storage_path),
            file.content_type,
        )
        
        return IndexingResultResponse(**result)
    
    except IndexingError as e:
        logger.error(f"Indexing failed for source {source_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@router.get("/{space_id}/sources", response_model=list[SourceResponse])
async def list_sources(
    space_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """List all sources in a Knowledge Space."""
    # Validate space
    stmt = select(Space).where(Space.id == space_id)
    result = await session.execute(stmt)
    space = result.scalar_one_or_none()
    
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    
    # Get sources
    stmt = select(Source).where(Source.space_id == space_id).order_by(Source.created_at.desc())
    result = await session.execute(stmt)
    sources = result.scalars().all()
    
    # Get chunk counts
    response = []
    for source in sources:
        chunk_count = await get_chunk_count(session, source_id=source.id)
        
        response.append(SourceResponse(
            id=source.id,
            space_id=source.space_id,
            filename=source.filename,
            mime_type=source.mime_type,
            file_size=source.file_size,
            status=source.status,
            created_at=source.created_at.isoformat(),
            chunk_count=chunk_count,
        ))
    
    return response


@router.delete("/{space_id}/sources/{source_id}", status_code=204)
async def delete_source(
    space_id: str,
    source_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a source (cascades to chunks)."""
    stmt = select(Source).where(Source.id == source_id, Source.space_id == space_id)
    result = await session.execute(stmt)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Delete file from disk
    if source.storage_path and os.path.exists(source.storage_path):
        try:
            os.remove(source.storage_path)
            logger.info(f"Deleted file {source.storage_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file {source.storage_path}: {e}")
    
    # Delete from database
    await session.delete(source)
    await session.commit()
    
    logger.info(f"Deleted source {source_id}")
    
    return


@router.post("/{space_id}/reindex", response_model=dict)
async def reindex_space(
    space_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Re-index all sources in a space."""
    # Validate space
    stmt = select(Space).where(Space.id == space_id)
    result = await session.execute(stmt)
    space = result.scalar_one_or_none()
    
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    
    # Get all sources
    stmt = select(Source).where(Source.space_id == space_id)
    result = await session.execute(stmt)
    sources = result.scalars().all()
    
    if not sources:
        return {"message": "No sources to reindex", "reindexed": 0}
    
    # Re-index each source
    indexer = SpaceIndexer()
    results = []
    
    for source in sources:
        try:
            result = await indexer.reindex_source(
                session,
                source.id,
                source.storage_path,
                source.mime_type,
            )
            results.append(result)
        except IndexingError as e:
            logger.error(f"Failed to reindex source {source.id}: {e}")
    
    return {
        "message": f"Re-indexed {len(results)} sources",
        "reindexed": len(results),
        "failed": len(sources) - len(results),
    }


# ============================================================================
# Search Endpoint
# ============================================================================

@router.post("/{space_id}/search", response_model=list[SearchResultResponse])
async def search_space(
    space_id: str,
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Search for relevant chunks in a Knowledge Space using semantic similarity."""
    # Validate space
    stmt = select(Space).where(Space.id == space_id)
    result = await session.execute(stmt)
    space = result.scalar_one_or_none()
    
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    
    # Search
    try:
        results = await search_chunks(
            session,
            query=request.query,
            space_id=space_id,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )
        
        return [
            SearchResultResponse(
                id=r["id"],
                content=r["content"],
                similarity=r["similarity"],
                metadata=r["metadata"],
                source_id=r["source_id"],
                space_id=r["space_id"],
            )
            for r in results
        ]
    
    except SearchError as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ============================================================================
# Progress Endpoint
# ============================================================================

@router.get("/{space_id}/sources/{source_id}/progress")
async def source_indexing_progress(
    space_id: str,
    source_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """SSE stream for indexing progress (for future UI integration)."""
    # Validate source
    stmt = select(Source).where(Source.id == source_id, Source.space_id == space_id)
    result = await session.execute(stmt)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    async def event_stream():
        """Generate SSE events for indexing progress."""
        # Check status periodically
        for i in range(60):  # Poll for 60 seconds
            await session.refresh(source)
            
            if source.status == "indexed":
                chunk_count = await get_chunk_count(session, source_id=source.id)
                yield f"data: {{\"status\": \"completed\", \"chunks\": {chunk_count}}}\n\n"
                break
            elif source.status == "failed":
                yield f"data: {{\"status\": \"failed\"}}\n\n"
                break
            else:
                yield f"data: {{\"status\": \"{source.status}\"}}\n\n"
            
            await asyncio.sleep(1)
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
