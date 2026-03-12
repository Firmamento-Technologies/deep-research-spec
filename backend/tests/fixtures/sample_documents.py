"""Sample document data for testing."""

from src.models.state import SearchResult

SAMPLE_SEARCH_RESULTS = [
    SearchResult(
        title="Machine Learning Overview - Wikipedia",
        url="https://en.wikipedia.org/wiki/Machine_learning",
        snippet="Machine learning (ML) is a field of study in artificial intelligence...",
        source_type="web",
    ),
    SearchResult(
        title="Deep Learning Book",
        url="https://www.deeplearningbook.org/",
        snippet="An MIT Press book on deep learning methods and applications...",
        source_type="web",
    ),
    SearchResult(
        title="RAG: Neural Networks Fundamentals",
        url="chunk://abc123",
        snippet="Neural networks are computational models inspired by biological neurons...",
        source_type="rag",
        similarity=0.87,
        chunk_id="abc123",
    ),
    SearchResult(
        title="RAG: Backpropagation Algorithm",
        url="chunk://def456",
        snippet="Backpropagation is the key algorithm for training neural networks...",
        source_type="rag",
        similarity=0.82,
        chunk_id="def456",
    ),
]

SAMPLE_TOPIC = "Machine Learning and Neural Networks"
SAMPLE_TARGET_WORDS = 3000
