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

        # Inject province-matched score_data chunks when query asks for rank/score data.
        # Vector similarity alone is too weak to surface structured tables; explicit
        # province-keyword injection ensures the LLM sees relevant 2025 data.
        if fused and _is_score_query(query):
            fused = _inject_province_score_data(fused, self.chroma_col, query, context)

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

# Province name list for keyword injection
_PROVINCE_NAMES = [
    '北京', '天津', '上海', '重庆', '广东', '江苏', '浙江', '山东',
    '河南', '河北', '湖北', '湖南', '福建', '安徽', '江西', '辽宁',
    '四川', '陕西', '山西', '云南', '贵州', '广西', '甘肃', '吉林',
    '黑龙江', '内蒙古', '新疆', '海南', '宁夏', '青海', '西藏',
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


def _find_province(query: str, context: dict) -> str:
    """Extract province name from query or context."""
    # Check context first
    province = context.get('province', '')
    if province and province in _PROVINCE_NAMES:
        return province
    # Check query
    for p in _PROVINCE_NAMES:
        if p in query:
            return p
    return ''


def _inject_province_score_data(
    results: list[dict],
    chroma_col,
    query: str,
    context: dict,
    max_inject: int = 5,
) -> list[dict]:
    """Inject province-matched score_data chunks at the front of results.

    Vector search alone can't reliably surface structured score tables
    (character-bigram hashing doesn't capture "598分" vs "分数位次院校"
    semantic similarity).  This function directly finds score_data docs
    for the target province and prepends them.
    """
    province = _find_province(query, context)
    if not province:
        return results

    # Scan ChromaDB for province-matched score_data docs
    injected = []
    seen_ids = {r.get('id', '') for r in results}
    # Limit scan to first 60k docs for performance
    for i in range(min(len(chroma_col._documents), 60000)):
        meta = chroma_col._metadatas[i] if i < len(chroma_col._metadatas) else {}
        if not isinstance(meta, dict):
            continue
        if meta.get('content_type') != 'score_data':
            continue
        doc_text = chroma_col._documents[i] if i < len(chroma_col._documents) else ''
        if province not in doc_text:
            continue
        doc_id = chroma_col._ids[i] if i < len(chroma_col._ids) else ''
        if doc_id in seen_ids:
            continue
        injected.append({
            'id': doc_id,
            'content': doc_text,
            'metadata': meta,
        })
        seen_ids.add(doc_id)
        if len(injected) >= max_inject:
            break

    if not injected:
        return results

    # Sort: 一分一段表 docs first, then province-header docs, then others
    def _sort_key(r):
        content = r.get('content', '') or ''
        # Priority 0: explicit 一分一段表 or 分数位次对照
        if '一分一段' in content[:300] or '分数位次对照' in content[:300]:
            return 0
        # Priority 1: province in header
        if province in content[:200]:
            return 1
        return 2
    injected.sort(key=_sort_key)

    # Prepend injected score_data, then deduplicated original results
    return injected + results


def _inject_batch_line_data(
    results: list[dict],
    chroma_col,
    query: str,
    context: dict,
) -> list[dict]:
    """Inject general batch-line data when province not found."""
    # Already covered by _inject_province_score_data for most cases
    return results
