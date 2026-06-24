"""Hybrid search -- combine vector, keyword, and structured results.

Core algorithm:
    RRF (Reciprocal Rank Fusion) merges multiple ranked lists into one
    without needing calibrated scores.  Each document receives:
        score = sum(1 / (k + rank + 1)) across every list that contains it.

Provides:
    :func:`rrf_fusion` -- merge helper
    :class:`HybridSearch` -- orchestrator that calls the three retrieval
    branches, fuses results, and optionally re-ranks.
"""

from __future__ import annotations

from typing import Optional

# RRF Fusion
# ------------------------------------------------------------------


def rrf_fusion(*result_lists: list[dict], k: int = 60) -> list[dict]:
    """Fuse multiple ranked result lists with Reciprocal Rank Fusion.

    Parameters
    ----------
    *result_lists : list[dict]
        One or more lists of result dicts.  Each dict should have either an
        ``id`` or ``content`` key to serve as the dedup key.
    k : int
        RRF constant (default 60).

    Returns
    -------
    list[dict]
        Deduplicated results sorted by descending RRF score.  The first
        occurrence of each item is kept.
    """
    scores = {}
    id_to_item = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            key = item.get("id", item.get("content", "")[:50])
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
            if key not in id_to_item:
                id_to_item[key] = item
    sorted_keys = sorted(scores, key=scores.get, reverse=True)
    return [id_to_item[k] for k in sorted_keys]


class HybridSearch:
    """Orchestrate multi-strategy retrieval with RRF fusion.

    Wraps vector, keyword, and structured queries into a single
    ``search()`` call.  On any branch failure, that branch is
    skipped gracefully (logged if a logger is available).

    Parameters
    ----------
    mode : str
        ``"prod"`` or ``"mock"``.  Mock mode returns an empty list.
    embedding_svc :
        An :class:`~src.retrieval.embedding_service.EmbeddingService`
        instance for vector search.
    chroma_col :
        A chromadb-compatible collection.
    db_conn : sqlite3.Connection
        SQLite connection for keyword + structured queries.
    reranker :
        Optional :class:`~src.retrieval.reranker.RerankerService` instance.
    logger :
        Optional :class:`~src.utils.logger.AgentLogger` instance.
    """

    def __init__(self, mode="prod", embedding_svc=None, chroma_col=None,
                 db_conn=None, reranker=None, logger=None):
        self.mode = mode
        self.embedding_svc = embedding_svc
        self.chroma_col = chroma_col
        self.db_conn = db_conn
        self.reranker = reranker
        self.logger = logger

    def search(self, query, scene, context=None):
        if self.mode == "mock":
            return []

        from src.retrieval.vector_search import vector_search
        from src.retrieval.keyword_search import keyword_search
        from src.retrieval.structured_query import (
            query_admission, query_employment, query_city_clusters,
        )

        context = context or {}

        try:
            vec_results = vector_search(self.embedding_svc, self.chroma_col, query, top_k=20)
        except Exception as e:
            if self.logger:
                self.logger.log_warning("chromadb", "vector_search_failed", "skip_vector", {"error": str(e)})
            vec_results = []

        try:
            kw_results = keyword_search(self.db_conn, query, top_k=10)
        except Exception as e:
            if self.logger:
                self.logger.log_warning("sqlite", "keyword_search_failed", "skip_keyword", {"error": str(e)})
            kw_results = []

        fused = rrf_fusion(vec_results, kw_results)

        if scene == "volunteer" and context.get("score"):
            try:
                province = context.get("province", "")
                category = context.get("subject_combo", "综合")
                score = context["score"]
                year = context.get("year", 2025)

                if province:
                    structured = query_admission(
                        self.db_conn, province, year,
                        category, score - 30, score + 30,
                    )
                    # Fuse structured results into RRF instead of appending
                    if structured:
                        fused = rrf_fusion(fused, structured)
            except Exception:
                pass

        if self.reranker and fused:
            try:
                fused = self.reranker.rerank(query, fused)
            except Exception as e:
                if self.logger:
                    self.logger.log_warning("reranker", "rerank_failed", "use_original", {"error": str(e)})

        # Boost score_data results when query contains rank/score keywords
        if fused and _is_score_query(query):
            fused = _boost_score_data(fused)

        return fused[:10]


# -- Query classification helpers --

_SCORE_QUERY_PATTERNS = [
    '一分一段', '位次', '批次线', '录取分', '分数线', '投档线',
    '特招线', '本科线', '专科线', '一分一段表', '排名', '多少分',
    '几分', '估分', '分数', '省控线', '调档线', '分能上', '分左右',
    '分可以', '分够', '分报',
]


def _is_score_query(query: str) -> bool:
    """Check if query is asking about score/rank/batch-line data."""
    return any(p in query for p in _SCORE_QUERY_PATTERNS)


def _boost_score_data(results: list[dict], boost: float = 0.15) -> list[dict]:
    """Boost score_data results by adding *boost* to an implicit RRF-like score.

    Since items from RRF don't carry individual scores accessible here,
    we re-rank by pushing score_data items toward the front while
    preserving their relative order with other score_data items.
    """
    score_data_items = []
    other_items = []
    for item in results:
        meta = item.get('metadata', {}) or {}
        if meta.get('content_type') == 'score_data':
            score_data_items.append(item)
        else:
            other_items.append(item)
    # score_data first, then others — both preserving original order
    return score_data_items + other_items
