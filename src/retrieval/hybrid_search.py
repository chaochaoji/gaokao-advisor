"""Hybrid search -- combine vector, keyword, and structured results.

Core algorithm:
    RRF (Reciprocal Rank Fusion) merges multiple ranked lists into one
    without needing calibrated scores.

Search branches:
    1. Vector similarity (character-bigram hashing)
    2. SQLite FTS5 (full-text search on corpus)
    3. Structured queries (admission/employment/city data for volunteer scene)

Score data injection:
    When the query contains rank/score keywords, province-matched
    score_data chunks are injected directly into the result set to
    compensate for the vector search's weak numeric matching.

Provides:
    :func:`rrf_fusion` -- merge helper
    :class:`HybridSearch` -- orchestrator
"""

from __future__ import annotations

from typing import Optional


def rrf_fusion(*result_lists: list[dict], k: int = 60) -> list[dict]:
    """Fuse multiple ranked result lists with Reciprocal Rank Fusion."""
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
    """Multi-strategy retrieval with RRF fusion + score_data injection."""

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

        # Branch 1: Vector similarity
        try:
            vec_results = vector_search(
                self.embedding_svc, self.chroma_col, query, top_k=20,
            )
        except Exception as e:
            if self.logger:
                self.logger.log_warning("chromadb", "vector_search_failed", "skip_vector", {"error": str(e)})
            vec_results = []

        # Branch 2: SQLite FTS5
        try:
            kw_results = keyword_search(self.db_conn, query, top_k=10)
        except Exception as e:
            if self.logger:
                self.logger.log_warning("sqlite", "keyword_search_failed", "skip_keyword", {"error": str(e)})
            kw_results = []

        fused = rrf_fusion(vec_results, kw_results)

        # Branch 3: Structured SQL queries (volunteer scene)
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
                    if structured:
                        fused = rrf_fusion(fused, structured)
            except Exception:
                pass

        # Inject province-matched score_data when vector search can't surface them.
        # Character-bigram hashing is too weak for exact numeric matching ("598分"
        # vs "598 | 10,984" in a score table).  This scan guarantees the LLM sees
        # relevant 2025 batch-line / 分数位次 / 一分一段 data.
        fused = _inject_score_data(fused, self.chroma_col, query, context)

        # Branch 4: Web search fallback.  Triggered only when local RAG is
        # insufficient — saves unnecessary DuckDuckGo calls on every query.
        # Conditions:
        #   - Volunteer scene with no score_data in top 5 (missing 一分一段)
        #   - Total fused results < 3 (local RAG returned almost nothing)
        if _should_web_search(fused, scene):
            try:
                from src.retrieval.web_search import web_search
                web_results = web_search(query, max_results=3)
                if web_results:
                    fused = fused + web_results  # append, don't RRF-fuse
                    if self.logger:
                        self.logger.log_info("web_search", "results_appended",
                            {"count": len(web_results), "query": query[:60]})
            except Exception:
                pass

        # Optional re-ranking
        if self.reranker and fused:
            try:
                fused = self.reranker.rerank(query, fused)
            except Exception as e:
                if self.logger:
                    self.logger.log_warning("reranker", "rerank_failed", "use_original", {"error": str(e)})

        return fused[:10]


# -- Web search gating ------------------------------------------------------


def _should_web_search(fused: list, scene: str) -> bool:
    """Return True if local RAG results are insufficient for this query.

    Triggers web search when:
    - Volunteer scene with zero score_data in top 5 (missing 一分一段表)
    - Fewer than 3 total results (local RAG returned almost nothing)
    """
    if len(fused) < 3:
        return True

    if scene == "volunteer":
        top5_cts = [
            (r.get("metadata", {}) or {}).get("content_type", "")
            for r in fused[:5]
        ]
        if "score_data" not in top5_cts:
            return True

    return False


# -- Score-data injection helpers -----------------------------------------

_PROVINCE_NAMES = [
    '北京', '天津', '上海', '重庆', '广东', '江苏', '浙江', '山东',
    '河南', '河北', '湖北', '湖南', '福建', '安徽', '江西', '辽宁',
    '四川', '陕西', '山西', '云南', '贵州', '广西', '甘肃', '吉林',
    '黑龙江', '内蒙古', '新疆', '海南', '宁夏', '青海', '西藏',
]
_SCAN_LIMIT = 60000


def _find_province(query: str, context: dict) -> str:
    p = context.get('province', '')
    if p in _PROVINCE_NAMES:
        return p
    for p in _PROVINCE_NAMES:
        if p in query:
            return p
    return ''


def _inject_score_data(results, chroma_col, query, context,
                       max_inject=5) -> list:
    """Inject province-matched score_data chunks at the front of results."""
    province = _find_province(query, context)
    if not province:
        return results

    collected = []
    seen = {r.get('id', '') for r in results}
    limit = min(len(chroma_col._documents), _SCAN_LIMIT)

    for i in range(limit):
        meta = chroma_col._metadatas[i] if i < len(chroma_col._metadatas) else {}
        if not isinstance(meta, dict) or meta.get('content_type') != 'score_data':
            continue
        doc = chroma_col._documents[i] if i < len(chroma_col._documents) else ''
        if province not in doc:
            continue
        doc_id = chroma_col._ids[i] if i < len(chroma_col._ids) else str(i)
        if doc_id in seen:
            continue
        priority = 0 if ('一分一段' in doc[:300] or '分数位次对照' in doc[:300]) else 1
        collected.append({
            'id': doc_id,
            'content': doc,
            'metadata': meta,
            'score': 0.99,  # high score so reranker keeps them at top
            '_pri': priority,
        })
        seen.add(doc_id)

    if not collected:
        return results

    collected.sort(key=lambda r: r.get('_pri', 1))
    for r in collected:
        r.pop('_pri', None)
    return collected[:max_inject] + results
