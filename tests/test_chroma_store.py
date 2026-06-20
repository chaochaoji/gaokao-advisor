"""Tests for ChromaDB vector store (numpy-backend implementation)."""

import os
import pytest
import numpy as np
from src.knowledge.chroma_store import (
    get_chroma_collection, add_chunks, query_chunks, delete_by_source,
    NumpyCollection,
)


# ── Mock EmbeddingService ──────────────────────────────────────────────


class MockEmbeddingService:
    """Fake embedding service that returns deterministic vectors based on
    character-position weights, giving different texts different vectors
    so that semantic grouping is absent but same-text consistency holds.
    """

    DIM = 384

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = []
        for t in texts:
            vec = np.zeros(self.DIM, dtype=np.float64)
            for i, ch in enumerate(t):
                vec[i % self.DIM] += ord(ch) / 1000.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            result.append(vec.tolist())
        return result

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


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


@pytest.fixture
def mock_embedding_svc():
    return MockEmbeddingService()


# ── Tests ─────────────────────────────────────────────────────────────


class TestChromaStore:
    """Vector store CRUD tests (fallback embedding path)."""

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


class TestEmbeddingSvcPath:
    """Tests that exercise the embedding_svc code path."""

    def test_add_uses_embedding_svc(self, mock_embedding_svc):
        """When embedding_svc is set, add() should call embed() on it."""
        col = NumpyCollection("test", embedding_svc=mock_embedding_svc)
        chunks = [
            {"id": "e1", "content": "人工智能专业前景"},
            {"id": "e2", "content": "临床医学就业形势"},
        ]
        add_chunks(col, chunks)
        # Should have two entries with real embeddings (not all-zero)
        assert len(col._embeddings) == 2
        for emb in col._embeddings:
            assert emb.shape == (384,)
            assert np.linalg.norm(emb) > 0

    def test_query_uses_embed_query(self, mock_embedding_svc):
        """When embedding_svc is set, query() should use embed_query()."""
        col = NumpyCollection("test", embedding_svc=mock_embedding_svc)
        add_chunks(
            col,
            [
                {"id": "q1", "content": "计算机专业一定要看城市"},
                {"id": "q2", "content": "金融专业看学校名气"},
            ],
        )
        results = query_chunks(col, "计算机城市实习", top_k=2)
        assert len(results) >= 1
        # Both results should have the expected structure
        for r in results:
            assert "id" in r
            assert "content" in r
            assert "distance" in r

    def test_get_chroma_collection_accepts_embedding_svc(self, mock_embedding_svc):
        """get_chroma_collection should forward embedding_svc to the collection."""
        from config import Config
        config = Config(chroma_persist_dir=":memory:")
        col = get_chroma_collection(config, embedding_svc=mock_embedding_svc)
        assert col._embedding_svc is mock_embedding_svc
        assert isinstance(col, NumpyCollection)

    def test_add_without_embedding_svc_falls_back(self):
        """Without embedding_svc, add should use character-bigram hashing."""
        col = NumpyCollection("test")
        add_chunks(col, [{"id": "fb1", "content": "测试回退文本"}])
        assert len(col._embeddings) == 1
        assert np.linalg.norm(col._embeddings[0]) > 0


class TestPersistence:
    """Tests for pickle persistence (save/load round-trip)."""

    def test_save_and_load_roundtrip(self, temp_dir):
        """Data added to a collection should survive a second get_chroma_collection."""
        from config import Config
        config = Config(chroma_persist_dir=temp_dir)

        # First session: add data
        col1 = get_chroma_collection(config)
        add_chunks(col1, [
            {"id": "p1", "content": "持久化测试内容", "metadata": {"topic": "测试"}},
        ])
        assert len(col1._ids) == 1

        # Second session: load from pickle
        col2 = get_chroma_collection(config)
        assert len(col2._ids) == 1
        assert col2._ids[0] == "p1"
        assert col2._documents[0] == "持久化测试内容"
        assert col2._metadatas[0]["topic"] == "测试"

    def test_pickle_file_is_created(self, temp_dir):
        """After adding chunks, the pickle file should exist on disk."""
        from config import Config
        config = Config(chroma_persist_dir=temp_dir)

        col = get_chroma_collection(config)
        add_chunks(col, [{"id": "pf1", "content": "文件存在测试"}])

        pickle_path = os.path.join(temp_dir, "collection.pkl")
        assert os.path.isfile(pickle_path)

    def test_delete_persists(self, temp_dir):
        """Deletions should be persisted to the pickle file."""
        from config import Config
        config = Config(chroma_persist_dir=temp_dir)

        col1 = get_chroma_collection(config)
        add_chunks(col1, [
            {"id": "keep_me", "content": "保留的数据"},
            {"id": "del_me", "content": "待删除数据"},
        ])
        delete_by_source(col1, "del_")
        assert len(col1._ids) == 1

        col2 = get_chroma_collection(config)
        assert len(col2._ids) == 1
        assert col2._ids[0] == "keep_me"

    def test_embedding_svc_survives_roundtrip(self, temp_dir, mock_embedding_svc):
        """embedding_svc should be re-attached after loading from pickle."""
        from config import Config
        config = Config(chroma_persist_dir=temp_dir)

        # Add with mock embedding_svc
        col1 = get_chroma_collection(config, embedding_svc=mock_embedding_svc)
        add_chunks(col1, [
            {"id": "es1", "content": "embedding服务持久化测试"},
        ])

        # Reload with a different mock instance (identity check won't match,
        # but the embeddings from the first session are preserved in the
        # pickle and the new svc is attached for future operations).
        svc2 = MockEmbeddingService()
        col2 = get_chroma_collection(config, embedding_svc=svc2)
        assert col2._embedding_svc is svc2
        assert len(col2._ids) == 1
        assert col2._ids[0] == "es1"

        # Querying should use the newly attached svc
        results = query_chunks(col2, "embedding服务", top_k=1)
        assert len(results) == 1
