"""Semantic Text Chunking for Knowledge Spaces RAG

Splits extracted text into semantic chunks with configurable size and overlap.

Key features:
- Token-aware chunking (uses tiktoken for accurate counting)
- Semantic boundaries (paragraphs > sentences > words)
- Configurable overlap for context preservation
- Metadata tracking (chunk index, token/char counts)

Usage:
    from services.chunker import chunk_text
    
    chunks = chunk_text(
        text="Long document text...",
        chunk_size=512,  # tokens
        overlap=50,      # tokens
    )
    
    for chunk in chunks:
        print(f"Chunk {chunk['chunk_idx']}: {chunk['token_count']} tokens")
        print(chunk['content'][:100])

Author: DRS Implementation Team
Spec: §17 Knowledge Spaces, Task 2.2
"""

import logging
import re
from typing import Optional

# Token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logging.warning(
        "tiktoken not installed. Falling back to character-based chunking. "
        "Install with: pip install tiktoken"
    )

# LangChain text splitter (robust semantic boundaries)
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning(
        "langchain not installed. Using basic chunking. "
        "Install with: pip install langchain"
    )


logger = logging.getLogger(__name__)


class ChunkingError(Exception):
    """Raised when chunking fails."""
    pass


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    model: str = "gpt-3.5-turbo",
) -> list[dict]:
    """Split text into semantic chunks with token-aware splitting.
    
    Args:
        text: Input text to chunk
        chunk_size: Target chunk size in tokens (default: 512)
        overlap: Overlap between chunks in tokens (default: 50)
        model: Tokenizer model to use (default: gpt-3.5-turbo)
    
    Returns:
        List of chunk dicts with keys:
            - content: chunk text
            - chunk_idx: 0-based index
            - token_count: actual token count
            - char_count: character count
            - char_start: start position in original text
            - char_end: end position in original text
    
    Raises:
        ChunkingError: If chunking fails
    """
    if not text or not text.strip():
        return []
    
    logger.info(
        f"Chunking {len(text)} chars with chunk_size={chunk_size}, overlap={overlap}"
    )
    
    try:
        if TIKTOKEN_AVAILABLE and LANGCHAIN_AVAILABLE:
            # Best path: token-aware semantic chunking
            chunks = _chunk_with_tiktoken(text, chunk_size, overlap, model)
        elif LANGCHAIN_AVAILABLE:
            # Fallback: character-based semantic chunking
            logger.warning("tiktoken not available, using character approximation")
            chunks = _chunk_with_langchain(text, chunk_size, overlap)
        else:
            # Basic fallback: simple splitting
            logger.warning("langchain not available, using basic chunking")
            chunks = _chunk_basic(text, chunk_size, overlap)
        
        logger.info(f"Created {len(chunks)} chunks")
        return chunks
    
    except Exception as e:
        logger.error(f"Chunking failed: {e}")
        raise ChunkingError(f"Failed to chunk text: {e}") from e


def _chunk_with_tiktoken(
    text: str,
    chunk_size: int,
    overlap: int,
    model: str,
) -> list[dict]:
    """Token-aware chunking with tiktoken."""
    encoding = tiktoken.encoding_for_model(model)
    
    # Use LangChain's splitter with custom length function
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=lambda text: len(encoding.encode(text)),
        separators=[
            "\n\n",  # Paragraph breaks (highest priority)
            "\n",    # Line breaks
            ". ",    # Sentences
            "! ",
            "? ",
            "; ",
            ": ",
            ", ",    # Clauses
            " ",     # Words (lowest priority)
            "",      # Characters (last resort)
        ],
    )
    
    raw_chunks = splitter.split_text(text)
    
    # Add metadata
    chunks = []
    char_position = 0
    
    for idx, content in enumerate(raw_chunks):
        token_count = len(encoding.encode(content))
        char_count = len(content)
        
        # Find actual position in original text (accounting for overlap)
        char_start = text.find(content, char_position)
        if char_start == -1:  # Fallback if exact match not found
            char_start = char_position
        char_end = char_start + char_count
        
        chunks.append({
            "content": content,
            "chunk_idx": idx,
            "token_count": token_count,
            "char_count": char_count,
            "char_start": char_start,
            "char_end": char_end,
        })
        
        # Move position forward (accounting for overlap)
        char_position = char_start + char_count - (overlap * 4)  # ~4 chars/token heuristic
    
    return chunks


def _chunk_with_langchain(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[dict]:
    """Character-based semantic chunking (tiktoken unavailable)."""
    # Approximate tokens as chars / 4
    chunk_size_chars = chunk_size * 4
    overlap_chars = overlap * 4
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_chars,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ": ", ", ", " ", ""],
    )
    
    raw_chunks = splitter.split_text(text)
    
    # Add metadata (estimate tokens)
    chunks = []
    char_position = 0
    
    for idx, content in enumerate(raw_chunks):
        char_count = len(content)
        token_count = char_count // 4  # Rough estimate
        
        char_start = text.find(content, char_position)
        if char_start == -1:
            char_start = char_position
        char_end = char_start + char_count
        
        chunks.append({
            "content": content,
            "chunk_idx": idx,
            "token_count": token_count,
            "char_count": char_count,
            "char_start": char_start,
            "char_end": char_end,
        })
        
        char_position = char_start + char_count - overlap_chars
    
    return chunks


def _chunk_basic(text: str, chunk_size: int, overlap: int) -> list[dict]:
    """Basic chunking fallback (no dependencies)."""
    # Approximate tokens as chars / 4
    chunk_size_chars = chunk_size * 4
    overlap_chars = overlap * 4
    
    chunks = []
    idx = 0
    position = 0
    
    while position < len(text):
        # Extract chunk
        end = position + chunk_size_chars
        content = text[position:end]
        
        # Try to break at paragraph boundary
        if end < len(text):
            last_para = content.rfind("\n\n")
            if last_para > chunk_size_chars // 2:  # At least 50% through
                content = content[:last_para + 2]
                end = position + len(content)
        
        char_count = len(content)
        token_count = char_count // 4
        
        chunks.append({
            "content": content,
            "chunk_idx": idx,
            "token_count": token_count,
            "char_count": char_count,
            "char_start": position,
            "char_end": position + char_count,
        })
        
        idx += 1
        position = end - overlap_chars
        
        if position >= len(text):
            break
    
    return chunks


def estimate_chunk_count(text: str, chunk_size: int = 512, overlap: int = 50) -> int:
    """Estimate number of chunks without actually chunking.
    
    Useful for pre-allocation and progress bars.
    """
    if not text:
        return 0
    
    # Rough estimate: 4 chars per token
    text_tokens = len(text) // 4
    effective_chunk_size = chunk_size - overlap
    
    return max(1, (text_tokens + effective_chunk_size - 1) // effective_chunk_size)


def validate_chunks(chunks: list[dict]) -> bool:
    """Validate chunk list structure and content.
    
    Returns:
        True if valid, raises ChunkingError if invalid
    """
    if not chunks:
        return True
    
    required_keys = {"content", "chunk_idx", "token_count", "char_count"}
    
    for chunk in chunks:
        # Check required keys
        if not required_keys.issubset(chunk.keys()):
            raise ChunkingError(f"Chunk missing required keys: {required_keys}")
        
        # Check types
        if not isinstance(chunk["content"], str):
            raise ChunkingError("Chunk content must be string")
        
        if not isinstance(chunk["chunk_idx"], int):
            raise ChunkingError("chunk_idx must be int")
        
        # Check content not empty
        if not chunk["content"].strip():
            raise ChunkingError(f"Chunk {chunk['chunk_idx']} has empty content")
    
    # Check sequential indices
    indices = [c["chunk_idx"] for c in chunks]
    if indices != list(range(len(chunks))):
        raise ChunkingError(f"Non-sequential chunk indices: {indices}")
    
    return True


if __name__ == "__main__":
    # Test chunker with sample text
    sample_text = """
The Deep Research System (DRS) is an advanced AI-powered document generation platform designed to produce comprehensive, well-researched documents ranging from 5,000 to 50,000 words.

The system employs a multi-agent architecture, where specialized AI agents collaborate to handle different aspects of the document creation process. These agents include the Planner, Researcher, Writer, and various Jury agents for quality assessment.

One of the key innovations in DRS is the Mixture-of-Writers (MoW) approach, which generates multiple draft versions of each section using different writing strategies. These drafts are then evaluated by a panel of jury agents and fused into a final version that combines the best elements of each approach.

The system also implements a sophisticated budget control mechanism, allowing users to specify maximum cost constraints while automatically optimizing the quality-cost tradeoff. This is achieved through regime-based parameter selection (Economy, Balanced, Premium) and real-time cost tracking.

Knowledge Spaces provide a powerful way to incorporate domain-specific information into the research process. Users can upload documents, PDFs, and other resources into dedicated spaces, which are then indexed using vector embeddings for efficient retrieval during the research phase.
    """.strip()
    
    print("=" * 80)
    print("Semantic Chunking Test")
    print("=" * 80)
    print(f"\nInput: {len(sample_text)} characters")
    print(f"Estimated chunks: {estimate_chunk_count(sample_text, 100, 20)}\n")
    
    # Chunk with small size for demo
    chunks = chunk_text(sample_text, chunk_size=100, overlap=20)
    
    print(f"\nCreated {len(chunks)} chunks:\n")
    
    for chunk in chunks:
        print(f"--- Chunk {chunk['chunk_idx']} ---")
        print(f"Tokens: {chunk['token_count']}  |  Chars: {chunk['char_count']}")
        print(f"Position: {chunk['char_start']}-{chunk['char_end']}")
        print(f"Content preview: {chunk['content'][:100]}...")
        print()
    
    # Validate
    try:
        validate_chunks(chunks)
        print("✅ All chunks valid")
    except ChunkingError as e:
        print(f"❌ Validation failed: {e}")
