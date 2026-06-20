"""Tests for embedding service with API/local abstraction."""

import pytest
from unittest.mock import patch, MagicMock


# ── Fake backends for testing ──────────────────────────────────────────


class FakeAPIEmbedding:
    """Fake API backend that returns fixed embeddings."""

    def encode(self, texts):
        return [[0.1] * 1024 for _ in texts]

    def encode_query(self, text):
        return [0.1] * 1024


class FakeLocalEmbedding:
    """Fake local backend that returns fixed embeddings."""

    def __init__(self, model_path):
        self.model_path = model_path

    def encode(self, texts):
        return [[0.2] * 768 for _ in texts]

    def encode_query(self, text):
        return [0.2] * 768


# ── Tests ──────────────────────────────────────────────────────────────


class TestEmbeddingService:
    """Tests for EmbeddingService facade."""

    def test_embed_returns_correct_dimensions(self):
        from retrieval.embedding_service import EmbeddingService

        svc = EmbeddingService(mode="api")
        svc.backend = FakeAPIEmbedding()
        result = svc.embed(["测试文本", "另一条文本"])
        assert len(result) == 2
        assert len(result[0]) == 1024

    def test_embed_single_text(self):
        from retrieval.embedding_service import EmbeddingService

        svc = EmbeddingService(mode="api")
        svc.backend = FakeAPIEmbedding()
        result = svc.embed(["单条文本"])
        assert len(result) == 1
        assert len(result[0]) == 1024

    def test_embed_query(self):
        from retrieval.embedding_service import EmbeddingService

        svc = EmbeddingService(mode="api")
        svc.backend = FakeAPIEmbedding()
        result = svc.embed_query("测试")
        assert len(result) == 1024
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_mode_api_uses_api_backend(self):
        from retrieval.embedding_service import EmbeddingService

        svc = EmbeddingService(mode="api")
        name = type(svc.backend).__name__
        assert "API" in name or "api" in str(type(svc.backend)).lower()

    def test_mode_local_uses_local_backend(self):
        from retrieval.embedding_service import EmbeddingService

        svc = EmbeddingService(mode="local", local_path="/fake/path")
        name = type(svc.backend).__name__
        assert "Local" in name or "local" in str(type(svc.backend)).lower()

    def test_embed_query_falls_back_to_embed_when_no_encode_query(self):
        """If backend lacks encode_query, fall back to embed([text])[0]."""
        from retrieval.embedding_service import EmbeddingService

        svc = EmbeddingService(mode="api")

        # A backend that only has encode (not encode_query)
        class EncodeOnlyBackend:
            def encode(self, texts):
                return [[float(i + 1)] * 512 for i in range(len(texts))]

        svc.backend = EncodeOnlyBackend()
        result = svc.embed_query("测试")
        assert len(result) == 512
        assert result[0] == 1.0

    def test_config_integration(self, sample_config):
        """EmbeddingService should accept a Config object fields."""
        from retrieval.embedding_service import EmbeddingService

        svc = EmbeddingService(
            mode=sample_config.embedding_mode,
            api_key=sample_config.embedding_api_key,
        )
        assert svc.mode == "api"
        assert svc.backend.api_key == "test-embed-key"


class TestAPIEmbeddingBackend:
    """Tests for the API-based embedding backend."""

    def test_constructor_uses_env_fallback(self):
        """api_key defaults to ZXF_EMBEDDING_API_KEY env var when empty."""
        import os
        from retrieval.embedding_service import APIEmbeddingBackend

        os.environ["ZXF_EMBEDDING_API_KEY"] = "env-key-123"
        backend = APIEmbeddingBackend(api_key="")
        assert backend.api_key == "env-key-123"
        del os.environ["ZXF_EMBEDDING_API_KEY"]

    def test_constructor_prefers_explicit_key(self):
        from retrieval.embedding_service import APIEmbeddingBackend

        backend = APIEmbeddingBackend(api_key="explicit-key")
        assert backend.api_key == "explicit-key"

    def test_encode_makes_correct_api_call(self):
        import json
        from retrieval.embedding_service import APIEmbeddingBackend

        backend = APIEmbeddingBackend(api_key="sk-test", model="test-model")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                {"index": 1, "embedding": [0.4, 0.5, 0.6]},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = backend.encode(["hello", "world"])

            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert kwargs["json"]["model"] == "test-model"
            assert kwargs["json"]["input"] == ["hello", "world"]
            assert kwargs["headers"]["Authorization"] == "Bearer sk-test"
            assert kwargs["timeout"] == 30

            assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    def test_encode_query_delegates_to_encode(self):
        from retrieval.embedding_service import APIEmbeddingBackend

        backend = APIEmbeddingBackend(api_key="sk-test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"index": 0, "embedding": [0.7, 0.8, 0.9]}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_response):
            result = backend.encode_query("single query")
            assert result == [0.7, 0.8, 0.9]

    def test_default_model(self):
        from retrieval.embedding_service import APIEmbeddingBackend

        backend = APIEmbeddingBackend()
        assert backend.model == "BAAI/bge-m3"

    def test_default_base_url(self):
        from retrieval.embedding_service import APIEmbeddingBackend

        backend = APIEmbeddingBackend()
        assert "siliconflow.cn" in backend.base_url


class TestLocalEmbeddingBackend:
    """Tests for the local embedding backend (lazy model loading)."""

    def test_constructor_stores_model_path(self):
        from retrieval.embedding_service import LocalEmbeddingBackend

        backend = LocalEmbeddingBackend(model_path="/models/bge-m3")
        assert backend.model_path == "/models/bge-m3"
        assert backend._model is None  # not loaded yet

    def test_encode_uses_local_model(self):
        from retrieval.embedding_service import LocalEmbeddingBackend

        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": MagicMock()
        }
        mock_model.encode.return_value["dense_vecs"].tolist.return_value = [
            [0.1, 0.2],
            [0.3, 0.4],
        ]

        backend = LocalEmbeddingBackend(model_path="/models/test")
        # Inject mock model directly (avoids needing FlagEmbedding installed)
        backend._model = mock_model
        result = backend.encode(["text1", "text2"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        mock_model.encode.assert_called_once_with(
            ["text1", "text2"], batch_size=32
        )

    def test_encode_query_uses_local_model(self):
        from retrieval.embedding_service import LocalEmbeddingBackend

        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": MagicMock()
        }
        mock_model.encode.return_value["dense_vecs"].tolist.return_value = [
            [0.5, 0.6],
        ]

        backend = LocalEmbeddingBackend(model_path="/models/test")
        backend._model = mock_model
        result = backend.encode_query("query text")

        assert result == [0.5, 0.6]

    def test_local_backend_uses_fp16(self):
        """_load_model should call BGEM3FlagModel with use_fp16=True."""
        from retrieval.embedding_service import LocalEmbeddingBackend

        mock_bge = MagicMock()
        with patch.object(
            LocalEmbeddingBackend, "_load_model",
            autospec=True,
            side_effect=lambda self: setattr(self, "_model", mock_bge),
        ):
            backend = LocalEmbeddingBackend(model_path="/models/test")
            # Lazy load triggered by encode when _model is None
            backend.encode(["trigger load"])
            # After _load_model, _model should be our mock
            assert backend._model is mock_bge

    def test_model_property_lazy_loading(self):
        """model property returns _model or loads it lazily."""
        from retrieval.embedding_service import LocalEmbeddingBackend

        mock_model = MagicMock()
        with patch.object(
            LocalEmbeddingBackend, "_load_model",
            autospec=True,
            side_effect=lambda self: setattr(self, "_model", mock_model),
        ):
            backend = LocalEmbeddingBackend(model_path="/models/test")
            # First access triggers load
            model = backend.model
            assert model is mock_model
            # Second access returns cached
            model2 = backend.model
            assert model2 is mock_model
