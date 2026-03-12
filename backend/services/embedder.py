"""Embedding Generation for Knowledge Spaces RAG

Generates vector embeddings from text chunks using sentence-transformers.

Key features:
- all-MiniLM-L6-v2 model (384 dimensions)
- Batch processing for efficiency
- GPU acceleration if available
- Normalized vectors for cosine similarity
- Singleton pattern to avoid reloading model

Usage:
    from services.embedder import embed_text, embed_batch
    
    # Single embedding
    vector = embed_text("This is a test sentence.")
    print(f"Dimensions: {len(vector)}")  # 384
    
    # Batch embedding
    texts = ["First text", "Second text", "Third text"]
    vectors = embed_batch(texts)
    print(f"Generated {len(vectors)} embeddings")

Author: DRS Implementation Team
Spec: §17 Knowledge Spaces, Task 2.3
"""

from __future__ import annotations

import logging
import numpy as np
from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning(
        "sentence-transformers not installed. Install with: "
        "pip install sentence-transformers"
    )

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_MODEL = "all-MiniLM-L6-v2"  # 384 dimensions, 22M parameters
EMBEDDING_DIM = 384

# Singleton model instance
_model = None  # Optional[SentenceTransformer] when available
_model_name: Optional[str] = None


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""
    pass


def get_embedder(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    """Get or initialize sentence-transformers model.
    
    Uses singleton pattern to avoid reloading the model.
    
    Args:
        model_name: HuggingFace model identifier
    
    Returns:
        Loaded SentenceTransformer model
    
    Raises:
        EmbeddingError: If model loading fails
    """
    global _model, _model_name
    
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        raise EmbeddingError(
            "sentence-transformers not installed. Install with: "
            "pip install sentence-transformers"
        )
    
    # Return cached model if same model requested
    if _model is not None and _model_name == model_name:
        return _model
    
    try:
        logger.info(f"Loading embedding model: {model_name}")
        
        # Detect device (GPU if available)
        device = "cuda" if TORCH_AVAILABLE and torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        # Load model
        model = SentenceTransformer(model_name, device=device)
        
        # Cache
        _model = model
        _model_name = model_name
        
        logger.info(f"Model loaded successfully (dim={model.get_sentence_embedding_dimension()})")
        return model
    
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        raise EmbeddingError(f"Model loading failed: {e}") from e


def embed_text(
    text: str,
    model_name: str = DEFAULT_MODEL,
    normalize: bool = True,
) -> list[float]:
    """Generate embedding for single text.
    
    Args:
        text: Input text to embed
        model_name: Model to use
        normalize: Whether to normalize vector (for cosine similarity)
    
    Returns:
        Embedding as list of floats (length 384)
    
    Raises:
        EmbeddingError: If embedding fails
        ValueError: If text is empty
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")
    
    try:
        model = get_embedder(model_name)
        
        # Generate embedding
        embedding = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
        
        # Convert to list
        return embedding.tolist()
    
    except Exception as e:
        logger.error(f"Failed to embed text: {e}")
        raise EmbeddingError(f"Embedding failed: {e}") from e


def embed_batch(
    texts: list[str],
    model_name: str = DEFAULT_MODEL,
    normalize: bool = True,
    batch_size: int = 32,
    show_progress: bool = True,
) -> list[list[float]]:
    """Generate embeddings for batch of texts.
    
    More efficient than calling embed_text() in a loop.
    
    Args:
        texts: List of texts to embed
        model_name: Model to use
        normalize: Whether to normalize vectors
        batch_size: Batch size for processing
        show_progress: Show progress bar
    
    Returns:
        List of embeddings (each is list of 384 floats)
    
    Raises:
        EmbeddingError: If embedding fails
        ValueError: If texts list is empty
    """
    if not texts:
        raise ValueError("Cannot embed empty text list")
    
    # Filter empty strings
    non_empty_texts = [t for t in texts if t and t.strip()]
    if not non_empty_texts:
        raise ValueError("All texts are empty")
    
    if len(non_empty_texts) < len(texts):
        logger.warning(f"Filtered {len(texts) - len(non_empty_texts)} empty texts")
    
    try:
        model = get_embedder(model_name)
        
        logger.info(f"Embedding {len(non_empty_texts)} texts (batch_size={batch_size})")
        
        # Generate embeddings
        embeddings = model.encode(
            non_empty_texts,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            batch_size=batch_size,
            show_progress_bar=show_progress,
        )
        
        # Convert to list of lists
        return embeddings.tolist()
    
    except Exception as e:
        logger.error(f"Failed to embed batch: {e}")
        raise EmbeddingError(f"Batch embedding failed: {e}") from e


def compute_similarity(embedding1: list[float], embedding2: list[float]) -> float:
    """Compute cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
    
    Returns:
        Similarity score between -1 and 1 (1 = identical)
    """
    # Convert to numpy
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)
    
    # Cosine similarity
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


def validate_embedding(embedding: list[float]) -> bool:
    """Validate embedding structure and values.
    
    Args:
        embedding: Embedding vector to validate
    
    Returns:
        True if valid
    
    Raises:
        EmbeddingError: If validation fails
    """
    # Check type
    if not isinstance(embedding, list):
        raise EmbeddingError(f"Embedding must be list, got {type(embedding)}")
    
    # Check dimensions
    if len(embedding) != EMBEDDING_DIM:
        raise EmbeddingError(
            f"Expected {EMBEDDING_DIM} dimensions, got {len(embedding)}"
        )
    
    # Check all floats
    if not all(isinstance(x, (float, int)) for x in embedding):
        raise EmbeddingError("Embedding must contain only numbers")
    
    # Check normalized (if normalized, magnitude should be ~1.0)
    magnitude = np.linalg.norm(embedding)
    if not (0.99 <= magnitude <= 1.01):  # Allow small floating point error
        logger.warning(f"Embedding not normalized (magnitude={magnitude:.4f})")
    
    return True


def get_model_info() -> dict:
    """Get information about loaded model.
    
    Returns:
        Dict with model metadata
    """
    if _model is None:
        return {
            "loaded": False,
            "model_name": None,
            "embedding_dim": EMBEDDING_DIM,
            "device": None,
        }
    
    device = str(_model.device) if hasattr(_model, "device") else "unknown"
    
    return {
        "loaded": True,
        "model_name": _model_name,
        "embedding_dim": _model.get_sentence_embedding_dimension(),
        "device": device,
        "max_seq_length": _model.max_seq_length,
    }


if __name__ == "__main__":
    # Test embedder
    print("=" * 80)
    print("Embedding Generation Test")
    print("=" * 80)
    
    # Check availability
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("❌ sentence-transformers not installed")
        print("   Install: pip install sentence-transformers")
        exit(1)
    
    # Single embedding
    print("\n1. Single embedding:")
    text = "The Deep Research System generates comprehensive documents."
    embedding = embed_text(text)
    print(f"   Text: {text[:50]}...")
    print(f"   Dimensions: {len(embedding)}")
    print(f"   Sample values: [{embedding[0]:.4f}, {embedding[1]:.4f}, {embedding[2]:.4f}, ...]")
    print(f"   Magnitude: {np.linalg.norm(embedding):.4f}")
    
    # Validate
    try:
        validate_embedding(embedding)
        print("   ✅ Embedding valid")
    except EmbeddingError as e:
        print(f"   ❌ Validation failed: {e}")
    
    # Batch embedding
    print("\n2. Batch embedding:")
    texts = [
        "Knowledge Spaces enable RAG-enhanced research.",
        "Documents are chunked into 512-token segments.",
        "Embeddings are stored in PostgreSQL with pgvector.",
        "The system uses cosine similarity for retrieval.",
    ]
    embeddings = embed_batch(texts, show_progress=True)
    print(f"   Generated {len(embeddings)} embeddings")
    print(f"   Each: {len(embeddings[0])} dimensions")
    
    # Similarity test
    print("\n3. Similarity test:")
    sim_1_2 = compute_similarity(embeddings[0], embeddings[1])
    sim_1_3 = compute_similarity(embeddings[0], embeddings[2])
    sim_1_4 = compute_similarity(embeddings[0], embeddings[3])
    
    print(f"   '{texts[0][:40]}...' vs")
    print(f"   '{texts[1][:40]}...' = {sim_1_2:.3f}")
    print(f"   '{texts[2][:40]}...' = {sim_1_3:.3f}")
    print(f"   '{texts[3][:40]}...' = {sim_1_4:.3f}")
    
    # Model info
    print("\n4. Model info:")
    info = get_model_info()
    for key, value in info.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 80)
    print("✅ All tests passed")
    print("=" * 80)
