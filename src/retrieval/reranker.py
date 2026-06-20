"""Reranker service -- reorder search results by relevance to query.

Provides :class:`RerankerService` with three modes:

- ``api``: calls SiliconFlow rerank API (requires ZXF_EMBEDDING_API_KEY env var)
- ``local``: uses FlagEmbedding BGE reranker model locally
- ``mock``: sorts by existing ``score`` field (no-op pass-through)

All modes catch exceptions internally and fall back to score-sorted order,
so callers never see a raw exception from this layer.
"""

from __future__ import annotations

import os


class RerankerService:
    """Re-rank a list of candidate documents against a query.

    Parameters
    ----------
    mode : str
        ``"api"``, ``"local"``, or ``"mock"``.
    model : str
        Re-ranker model name used for API or local inference.
    """

    LOCAL_MODEL_DIR = os.path.join(
        os.path.dirname(__file__), "..", "..", "models", "BAAI", "bge-reranker-v2-m3"
    )

    def __init__(self, mode: str = "auto", model: str = "BAAI/bge-reranker-v2-m3"):
        if mode == "auto":
            mode = self._detect_best_mode()
        self.mode = mode
        self.model = model
        self._local_model = None
        if mode == "local":
            self._init_local()
        if mode == "local":
            self._init_local()

    @staticmethod
    def _detect_best_mode():
        if os.path.exists(RerankerService.LOCAL_MODEL_DIR):
            return "local"
        if os.getenv("ZXF_EMBEDDING_API_KEY"):
            return "api"
        return "mock"

    def _init_local(self):
        from FlagEmbedding import FlagReranker
        import torch
        path = self.LOCAL_MODEL_DIR if os.path.exists(self.LOCAL_MODEL_DIR) else self.model
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._local_model = FlagReranker(path, use_fp16=(device == "cuda"), device=device)
        self.mode = "local"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """Re-rank *candidates* by relevance to *query*.

        Parameters
        ----------
        query : str
            The search query.
        candidates : list[dict]
            Candidate results. Each dict must have at least a ``content`` key
            and may carry a ``score`` key from the original retrieval step.

        Returns
        -------
        list[dict]
            The input list sorted by descending relevance, with a new
            ``rerank_score`` key added to each dict.  On failure the
            original order (sorted by ``score``) is returned untouched.
        """
        if not candidates:
            return []

        try:
            if self.mode == "api":
                return self._api_rerank(query, candidates)
            elif self.mode == "local":
                return self._local_rerank(query, candidates)
            else:
                return self._mock_rerank(candidates)
        except Exception:
            # Graceful fallback: sort by existing score and add rerank_score
            for c in candidates:
                c["rerank_score"] = c.get("score", 0)
            return sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )

    # ------------------------------------------------------------------
    # Private backends
    # ------------------------------------------------------------------

    def _api_rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        import requests

        api_key = os.getenv("ZXF_EMBEDDING_API_KEY", "")
        resp = requests.post(
            "https://api.siliconflow.cn/v1/rerank",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": self.model,
                "query": query,
                "documents": [c["content"] for c in candidates],
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()["results"]
        for r in results:
            candidates[r["index"]]["rerank_score"] = r["relevance_score"]
        return sorted(
            candidates, key=lambda x: x.get("rerank_score", 0), reverse=True
        )

    def _local_rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        pairs = [[query, c["content"]] for c in candidates]
        scores = self._local_model.compute_score(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        return sorted(
            candidates, key=lambda x: x.get("rerank_score", 0), reverse=True
        )

    def _mock_rerank(self, candidates: list[dict]) -> list[dict]:
        for c in candidates:
            c["rerank_score"] = c.get("score", 0)
        return sorted(
            candidates, key=lambda x: x.get("rerank_score", 0), reverse=True
        )
