"""Tests for ChromaDB vector store (numpy-backend implementation)."""

import pytest
from src.knowledge.chroma_store import (
    get_chroma_collection, add_chunks, query_chunks, delete_by_source,
    NumpyCollection,
)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def chroma_collection():
    """Create an ephemeral NumpyCollection pre-loaded with two chunks."""
    col = NumpyCollection("test_corpus")
    chunks = [
        {
            "id": "doc_001_chunk_0",
            "content": "计算机专业一定要看城市，实习机会差太多了",
            "metadata": {
                "source": "B站直播",
                "date": "2024-03-15",
                "content_type": "live_transcript",
                "topic": "计算机",
            },
        },
        {
            "id": "doc_002_chunk_0",
            "content": "医学是长线投资，临床和口腔是两条路",
            "metadata": {
                "source": "公众号",
                "date": "2025-01-10",
                "content_type": "social_post",
                "topic": "医学",
            },
        },
    ]
    add_chunks(col, chunks)
    return col


# ── Tests ─────────────────────────────────────────────────────────────


class TestChromaStore:
    """Vector store CRUD tests."""

    def test_add_and_query(self, chroma_collection):
        """Querying for a topic should return relevant chunks."""
        results = query_chunks(chroma_collection, "计算机专业怎么选", top_k=2)
        assert len(results) > 0
        assert "计算机" in results[0]["content"]

    def test_query_returns_metadata(self, chroma_collection):
        """Query results should include complete metadata."""
        results = query_chunks(chroma_collection, "医学", top_k=1)
        assert results[0]["metadata"]["topic"] == "医学"
        assert results[0]["metadata"]["source"] == "公众号"

    def test_delete_by_source(self, chroma_collection):
        """Deleting by source prefix should remove chunks from results."""
        delete_by_source(chroma_collection, "doc_001")
        results = query_chunks(chroma_collection, "计算机", top_k=5)
        ids = [r["id"] for r in results]
        assert not any(i.startswith("doc_001") for i in ids)

    def test_get_chroma_collection_returns_numpy_collection(self):
        """get_chroma_collection should return a NumpyCollection instance."""
        from config import Config
        config = Config(chroma_persist_dir=":memory:")
        col = get_chroma_collection(config)
        assert isinstance(col, NumpyCollection)
        assert col.name == "zhangxuefeng_corpus"
