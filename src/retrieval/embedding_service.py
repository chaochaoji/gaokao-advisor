"""Unified embedding service with API and local backend abstraction.

Provides a single :class:`EmbeddingService` facade that selects between
:class:`APIEmbeddingBackend` (SiliconFlow) and :class:`LocalEmbeddingBackend`
(BGE-M3 via FlagEmbedding) based on configuration.
"""

import os


# ── Facade ──────────────────────────────────────────────────────────────


class EmbeddingService:
    """Unified embedding service that delegates to API or local backend.

    Parameters
    ----------
    mode : str
        ``"api"`` or ``"local"``.
    api_key : str
        API key for the embedding provider (SiliconFlow).
    model : str
        Model name (used for API mode, and as default local model path).
    local_path : str
        Filesystem path to the local BGE-M3 model directory.
    """

    def __init__(
        self,
        mode: str = "api",
        api_key: str = "",
        model: str = "BAAI/bge-m3",
        local_path: str = "",
    ):
        self.mode = mode
        if mode == "api":
            self.backend: object = APIEmbeddingBackend(api_key, model)
        else:
            self.backend: object = LocalEmbeddingBackend(
                local_path or model
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Parameters
        ----------
        texts : list[str]
            Input texts to embed.

        Returns
        -------
        list[list[float]]
            One embedding vector per input text.
        """
        return self.backend.encode(texts)

    def embed_query(self, text: str) -> list[float]:
        """Generate a single embedding for a query.

        If the backend provides ``encode_query``, it is used directly;
        otherwise the call falls back to ``embed([text])[0]``.

        Parameters
        ----------
        text : str
            The query text.

        Returns
        -------
        list[float]
            Embedding vector for the query.
        """
        if hasattr(self.backend, "encode_query"):
            return self.backend.encode_query(text)
        return self.embed([text])[0]


# ── API Backend ─────────────────────────────────────────────────────────


class APIEmbeddingBackend:
    """Embedding backend that calls a remote API (SiliconFlow).

    Parameters
    ----------
    api_key : str
        API key.  Falls back to the ``ZXF_EMBEDDING_API_KEY`` environment
        variable when empty.
    model : str
        Model identifier sent to the API.
    """

    def __init__(self, api_key: str = "", model: str = "BAAI/bge-m3"):
        self.api_key: str = api_key or os.getenv("ZXF_EMBEDDING_API_KEY", "")
        self.model: str = model
        self.base_url: str = "https://api.siliconflow.cn/v1"

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Send *texts* to the embeddings API and return dense vectors.

        Parameters
        ----------
        texts : list[str]
            Texts to embed.

        Returns
        -------
        list[list[float]]
            Embedding vectors sorted by the API response index.
        """
        import requests

        resp = requests.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            d["embedding"]
            for d in sorted(data["data"], key=lambda x: x["index"])
        ]

    def encode_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Parameters
        ----------
        text : str
            The query text.

        Returns
        -------
        list[float]
            Embedding vector.
        """
        return self.encode([text])[0]


# ── Local Backend ───────────────────────────────────────────────────────


class LocalEmbeddingBackend:
    """Embedding backend that runs BGE-M3 via FlagEmbedding locally.

    The model is loaded lazily on the first call to :meth:`encode` or
    :meth:`encode_query`, so construction is always cheap.

    Parameters
    ----------
    model_path : str
        Filesystem path to the BGE-M3 model directory.
    """

    def __init__(self, model_path: str):
        self.model_path: str = model_path
        self._model = None  # lazy – loaded on first use

    def _load_model(self):
        """Lazy-import and instantiate the BGE-M3 model."""
        from FlagEmbedding import BGEM3FlagModel

        self._model = BGEM3FlagModel(self.model_path, use_fp16=True)

    @property
    def model(self):
        """The underlying ``BGEM3FlagModel`` instance (lazy-loaded)."""
        if self._model is None:
            self._load_model()
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode *texts* with the local BGE-M3 model.

        Parameters
        ----------
        texts : list[str]
            Texts to embed.

        Returns
        -------
        list[list[float]]
            Dense embedding vectors.
        """
        if self._model is None:
            self._load_model()
        result = self._model.encode(texts, batch_size=32)
        return result["dense_vecs"].tolist()

    def encode_query(self, text: str) -> list[float]:
        """Embed a single query with the local model.

        Parameters
        ----------
        text : str
            The query text.

        Returns
        -------
        list[float]
            Embedding vector.
        """
        return self.encode([text])[0]
