"""Space Indexer — Chunking + Embedding Service for Knowledge Spaces

This service processes uploaded files in a Knowledge Space and generates
vector embeddings for RAG retrieval.

Pipeline:
1. Text extraction (PDF/DOCX/TXT/MD)
2. Semantic chunking (512 tokens, 50 overlap)
3. Embedding generation (sentence-transformers/all-MiniLM-L6-v2)
4. Batch insert into chunks table with pgvector

Author: DRS Implementation Team
Spec: TH.1-3 Knowledge Spaces
Date: 2026-03-04
"""

import logging
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

import aiofiles
import pypdf
import docx
from sentence_transformers import SentenceTransformer
import tiktoken
import asyncpg


logger = logging.getLogger(__name__)


# Globals (lazy-loaded)
_embedding_model: Optional[SentenceTransformer] = None
_tokenizer: Optional[tiktoken.Encoding] = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy load sentence-transformers model."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading sentence-transformers model: all-MiniLM-L6-v2")
        _embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    return _embedding_model


def get_tokenizer() -> tiktoken.Encoding:
    """Lazy load tiktoken for chunking."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.get_encoding('cl100k_base')  # GPT-4 tokenizer
    return _tokenizer


class TextExtractor:
    """Extract text from various file formats."""
    
    @staticmethod
    async def extract_from_pdf(file_path: Path) -> str:
        """Extract text from PDF using pypdf."""
        try:
            text_parts = []
            with open(file_path, 'rb') as f:
                pdf = pypdf.PdfReader(f)
                for page in pdf.pages:
                    text_parts.append(page.extract_text())
            return '\n\n'.join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction failed for {file_path}: {e}")
            raise ValueError(f"Could not extract text from PDF: {e}")
    
    @staticmethod
    async def extract_from_docx(file_path: Path) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return '\n\n'.join(paragraphs)
        except Exception as e:
            logger.error(f"DOCX extraction failed for {file_path}: {e}")
            raise ValueError(f"Could not extract text from DOCX: {e}")
    
    @staticmethod
    async def extract_from_text(file_path: Path) -> str:
        """Extract text from plain text or markdown files."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Text extraction failed for {file_path}: {e}")
            raise ValueError(f"Could not read text file: {e}")
    
    @classmethod
    async def extract(cls, file_path: Path) -> str:
        """Route to appropriate extractor based on file extension."""
        suffix = file_path.suffix.lower()
        
        if suffix == '.pdf':
            return await cls.extract_from_pdf(file_path)
        elif suffix in ['.docx', '.doc']:
            return await cls.extract_from_docx(file_path)
        elif suffix in ['.txt', '.md', '.markdown']:
            return await cls.extract_from_text(file_path)
        else:
            raise ValueError(
                f"Unsupported file type: {suffix}. "
                f"Supported: .pdf, .docx, .txt, .md"
            )


class SemanticChunker:
    """Chunk text into semantically coherent segments."""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        """
        Args:
            chunk_size: Target tokens per chunk
            overlap: Overlapping tokens between chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.tokenizer = get_tokenizer()
    
    def chunk(self, text: str) -> List[str]:
        """Split text into overlapping chunks.
        
        Returns:
            List of text chunks (strings)
        """
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # Move start forward, accounting for overlap
            if end == len(tokens):
                break
            start += self.chunk_size - self.overlap
        
        return chunks


class SpaceIndexer:
    """Main indexer service for Knowledge Spaces."""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self.extractor = TextExtractor()
        self.chunker = SemanticChunker(chunk_size=512, overlap=50)
        self.embedding_model = get_embedding_model()
    
    async def index_source(
        self,
        space_id: uuid.UUID,
        source_id: uuid.UUID,
        file_path: Path,
        reindex: bool = False,
    ) -> Dict[str, Any]:
        """Index a single source file into the Knowledge Space.
        
        Args:
            space_id: UUID of the Knowledge Space
            source_id: UUID of the source record in DB
            file_path: Path to uploaded file
            reindex: If True, delete existing chunks for this source first
        
        Returns:
            Dict with indexing stats:
                - chunks_created: int
                - total_tokens: int
                - avg_chunk_size: float
                - duration_seconds: float
        """
        start_time = datetime.now()
        
        logger.info(
            f"[SpaceIndexer] Starting indexing: "
            f"space={space_id}, source={source_id}, file={file_path.name}"
        )
        
        # Step 1: Delete old chunks if reindexing
        if reindex:
            deleted = await self._delete_chunks_for_source(source_id)
            logger.info(f"[SpaceIndexer] Deleted {deleted} old chunks (reindex)")
        
        # Step 2: Extract text
        try:
            text = await self.extractor.extract(file_path)
        except ValueError as e:
            logger.error(f"[SpaceIndexer] Extraction failed: {e}")
            raise
        
        if not text.strip():
            raise ValueError("Extracted text is empty")
        
        logger.info(f"[SpaceIndexer] Extracted {len(text)} characters")
        
        # Step 3: Chunk text
        chunks = self.chunker.chunk(text)
        
        if not chunks:
            raise ValueError("Chunking produced no results")
        
        logger.info(f"[SpaceIndexer] Created {len(chunks)} chunks")
        
        # Step 4: Generate embeddings (batch for efficiency)
        embeddings = self.embedding_model.encode(
            chunks,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        
        # Step 5: Insert into database
        await self._insert_chunks(
            space_id=space_id,
            source_id=source_id,
            chunks=chunks,
            embeddings=embeddings,
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        stats = {
            'chunks_created': len(chunks),
            'total_tokens': sum(len(self.chunker.tokenizer.encode(c)) for c in chunks),
            'avg_chunk_size': sum(len(c) for c in chunks) / len(chunks),
            'duration_seconds': duration,
        }
        
        logger.info(
            f"[SpaceIndexer] Indexing complete: "
            f"{stats['chunks_created']} chunks in {duration:.2f}s"
        )
        
        return stats
    
    async def _delete_chunks_for_source(self, source_id: uuid.UUID) -> int:
        """Delete all chunks for a given source."""
        async with self.db.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM chunks WHERE source_id = $1",
                source_id,
            )
            # Parse "DELETE N" result
            return int(result.split()[-1]) if result else 0
    
    async def _insert_chunks(
        self,
        space_id: uuid.UUID,
        source_id: uuid.UUID,
        chunks: List[str],
        embeddings: Any,  # numpy array
    ) -> None:
        """Batch insert chunks with embeddings into database."""
        # Prepare batch insert data
        records = [
            (
                space_id,
                source_id,
                chunk,
                embeddings[i].tolist(),  # pgvector expects list
                {},  # metadata (empty for now)
            )
            for i, chunk in enumerate(chunks)
        ]
        
        async with self.db.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO chunks (space_id, source_id, content, embedding, metadata)
                VALUES ($1, $2, $3, $4, $5)
                """,
                records,
            )
        
        logger.info(f"[SpaceIndexer] Inserted {len(records)} chunks into database")
    
    async def index_all_sources_in_space(
        self,
        space_id: uuid.UUID,
        reindex: bool = False,
    ) -> Dict[str, Any]:
        """Index all sources in a Knowledge Space.
        
        Args:
            space_id: UUID of the Knowledge Space
            reindex: If True, re-index all sources (delete + re-create)
        
        Returns:
            Dict with aggregate stats:
                - sources_indexed: int
                - total_chunks: int
                - errors: List[Dict] (source_id + error message)
        """
        # Fetch all sources for this space
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, file_path FROM sources 
                WHERE space_id = $1 AND status = 'active'
                """,
                space_id,
            )
        
        if not rows:
            logger.warning(f"[SpaceIndexer] No sources found for space {space_id}")
            return {'sources_indexed': 0, 'total_chunks': 0, 'errors': []}
        
        logger.info(f"[SpaceIndexer] Indexing {len(rows)} sources for space {space_id}")
        
        total_chunks = 0
        errors = []
        
        for row in rows:
            source_id = row['id']
            file_path = Path(row['file_path'])
            
            try:
                stats = await self.index_source(
                    space_id=space_id,
                    source_id=source_id,
                    file_path=file_path,
                    reindex=reindex,
                )
                total_chunks += stats['chunks_created']
            except Exception as e:
                logger.error(
                    f"[SpaceIndexer] Failed to index source {source_id}: {e}"
                )
                errors.append({'source_id': str(source_id), 'error': str(e)})
        
        return {
            'sources_indexed': len(rows) - len(errors),
            'total_chunks': total_chunks,
            'errors': errors,
        }


if __name__ == '__main__':
    # Test chunking locally (no DB required)
    print("=" * 80)
    print("Space Indexer — Local Test")
    print("=" * 80)
    
    sample_text = """
    The Deep Research System (DRS) is a multi-agent pipeline for generating
    long-form research documents. It uses a jury-based evaluation system
    where specialized AI judges score drafts across three dimensions:
    reasoning quality, factual accuracy, and stylistic appropriateness.
    
    The system implements a Mixture-of-Writers approach where three diverse
    writers generate competing first drafts. A Fusor agent then merges the
    best elements of each draft. This diversity improves first-iteration
    approval rates from 15% to 42%.
    
    Budget control is critical. The system estimates costs pre-run and tracks
    spending in real-time. If costs exceed 70% of the allocated budget, an
    alarm triggers adaptive strategies like reducing jury size or disabling
    Panel Discussion contingencies.
    """ * 5  # Repeat to test chunking
    
    chunker = SemanticChunker(chunk_size=128, overlap=20)
    chunks = chunker.chunk(sample_text)
    
    print(f"\nOriginal text: {len(sample_text)} chars")
    print(f"Number of chunks: {len(chunks)}")
    print(f"\nFirst chunk preview:")
    print("-" * 80)
    print(chunks[0][:300] + "...")
    print("-" * 80)
    
    # Test embedding (requires model download on first run)
    print("\nGenerating embeddings...")
    model = get_embedding_model()
    embeddings = model.encode(chunks[:2], show_progress_bar=False)
    print(f"Embedding shape: {embeddings.shape}")
    print(f"First embedding (first 10 dims): {embeddings[0][:10]}")
