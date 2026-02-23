"""Test Memvid RAG connector for local knowledge retrieval.

All tests use mocks so they run without FlagEmbedding / langchain-memvid
installed.  The integration test with real deps is gated behind
``scripts/build_memvid_kb.py``.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.connectors.memvid_connector import MemvidConnector


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_chunk(doc_id: str, chunk_id: int, content: str, title: str = "Test Doc") -> SimpleNamespace:
    """Create a fake LangChain Document chunk."""
    return SimpleNamespace(
        page_content=content,
        metadata={
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "title": title,
            "url": None,
        },
    )


def _run(coro):
    """Tiny helper to run an async function synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Tests ────────────────────────────────────────────────────────────────────

class TestMemvidConnector:
    """Test suite for MemvidConnector."""

    def test_connector_class_attributes(self):
        """Verify connector_id, source_type, reliability_base."""
        connector = MemvidConnector(knowledge_path="dummy.mp4")
        assert connector.connector_id == "memvid_local"
        assert connector.source_type == "upload"
        assert connector.reliability_base == 0.90
        assert connector.enabled is True

    @patch("src.connectors.memvid_connector.MemvidConnector._get_store")
    def test_search_returns_correct_source_dicts(self, mock_get_store):
        """search() returns list[dict] with all RankedSource-compatible fields."""
        fake_chunks = [
            _make_chunk("readme.md", 0, "LoRA is a low-rank adaptation technique"),
            _make_chunk("shine.md", 1, "SHINE generates LoRA in one forward pass"),
        ]
        mock_store = MagicMock()
        mock_store.similarity_search.return_value = fake_chunks
        mock_get_store.return_value = mock_store

        connector = MemvidConnector(knowledge_path="test.mp4")
        results = _run(connector.search("What is LoRA?", max_results=5))

        assert len(results) == 2
        for src in results:
            # Required RankedSource-compatible fields
            assert "source_id" in src
            assert "title" in src
            assert src["source_type"] == "upload"
            assert src["reliability_score"] == 0.90
            assert "full_text_snippet" in src
            assert "abstract" in src
            assert src["http_verified"] is False

        # Content check
        assert "LoRA" in results[0]["abstract"]
        assert "SHINE" in results[1]["abstract"]

    def test_fallback_when_kb_missing(self):
        """search() returns [] when knowledge base file is missing."""
        connector = MemvidConnector(knowledge_path="nonexistent_kb.mp4")
        # _get_store will raise FileNotFoundError (no mock) → graceful []
        with patch.object(connector, "_get_store", side_effect=FileNotFoundError):
            results = _run(connector.search("anything"))
        assert results == []

    def test_fallback_when_deps_missing(self):
        """search() returns [] when langchain-memvid not installed."""
        connector = MemvidConnector(knowledge_path="test.mp4")
        with patch.object(connector, "_get_store", side_effect=ImportError):
            results = _run(connector.search("anything"))
        assert results == []

    @patch("src.connectors.memvid_connector.MemvidConnector._get_store")
    @patch("src.connectors.memvid_connector.MemvidConnector._get_encoder")
    def test_health_check_success(self, mock_encoder, mock_store):
        """health_check() returns True when deps and KB are available."""
        connector = MemvidConnector(knowledge_path="test.mp4")
        assert _run(connector.health_check()) is True

    def test_health_check_failure(self):
        """health_check() returns False when KB is missing."""
        connector = MemvidConnector(knowledge_path="nonexistent.mp4")
        with patch.object(connector, "_get_store", side_effect=FileNotFoundError):
            assert _run(connector.health_check()) is False

    @patch("src.connectors.memvid_connector.MemvidConnector._get_store")
    def test_source_id_deterministic(self, mock_get_store):
        """Same doc_id + chunk_id always produce the same source_id."""
        chunk = _make_chunk("doc.md", 42, "content")
        mock_store = MagicMock()
        mock_store.similarity_search.return_value = [chunk, chunk]
        mock_get_store.return_value = mock_store

        connector = MemvidConnector(knowledge_path="test.mp4")
        results = _run(connector.search("query"))

        assert len(results) == 2
        assert results[0]["source_id"] == results[1]["source_id"]

    @patch("src.connectors.memvid_connector.MemvidConnector._get_store")
    def test_empty_results(self, mock_get_store):
        """search() handles empty results gracefully."""
        mock_store = MagicMock()
        mock_store.similarity_search.return_value = []
        mock_get_store.return_value = mock_store

        connector = MemvidConnector(knowledge_path="test.mp4")
        results = _run(connector.search("obscure query"))
        assert results == []

    @patch("src.connectors.memvid_connector.MemvidConnector._get_store")
    def test_max_results_passed_to_store(self, mock_get_store):
        """max_results parameter is forwarded to Memvid similarity_search."""
        mock_store = MagicMock()
        mock_store.similarity_search.return_value = []
        mock_get_store.return_value = mock_store

        connector = MemvidConnector(knowledge_path="test.mp4")
        _run(connector.search("query", max_results=3))

        mock_store.similarity_search.assert_called_once_with("query", k=3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
