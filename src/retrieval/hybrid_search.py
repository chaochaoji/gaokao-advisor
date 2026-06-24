"""Hybrid search -- combine BM25, vector, keyword, and structured results.

Core algorithm:
    RRF (Reciprocal Rank Fusion) merges multiple ranked lists into one
    without needing calibrated scores.  Each document receives:
        score = sum(1 / (k + rank + 1)) across every list that contains it.

Search branches:
    1. BM25 keyword (primary — exact province/score/rank matching)
    2. Vector similarity (semantic fallback for natural-language queries)
    3. SQLite FTS5 (full-text search on corpus)
    4. Structured queries (admission/employment/city data for volunteer scene)

Provides:
    :func:`rrf_fusion` -- merge helper
    :class:`HybridSearch` -- orchestrator that calls four retrieval
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

    Wraps BM25, vector, keyword, and structured queries into a single
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
    bm25_index :
        Optional :class:`~src.retrieval.bm25_search.BM25Index` instance.
    reranker :
        Optional :class:`~src.retrieval.reranker.RerankerService` instance.
    logger :
        Optional :class:`~src.utils.logger.AgentLogger` instance.
    """

    def __init__(self, mode="prod", embedding_svc=None, chroma_col=None,
                 db_conn=None, bm25_index=None, reranker=None, logger=None):
        self.mode = mode
        self.embedding_svc = embedding_svc
        self.chroma_col = chroma_col
        self.db_conn = db_conn
        self.bm25_index = bm25_index
        self.reranker = reranker
        self.logger = logger

    def search(self, query, scene, context=None):
        """Run all retrieval branches and fuse with RRF.

        Returns the top 10 results after fusion and optional re-ranking.
        """
        if self.mode == "mock":
            return []

        from src.retrieval.vector_search import vector_search
        from src.retrieval.keyword_search import keyword_search
        from src.retrieval.bm25_search import bm25_search
        from src.retrieval.structured_query import (
            query_admission, query_employment, query_city_clusters,
        )

        context = context or {}
        chroma_docs = self.chroma_col._documents if self.chroma_col else []

        # Branch 1: BM25 keyword (primary — exact matching)
        try:
            bm25_results = bm25_search(
                self.bm25_index, chroma_docs, query, top_k=15,
                metadatas=(self.chroma_col._metadatas if self.chroma_col else None),
                ids=(self.chroma_col._ids if self.chroma_col else None),
            )
        except Exception as e:
            if self.logger:
                self.logger.log_warning("bm25", "search_failed", "skip_bm25", {"error": str(e)})
            bm25_results = []

        # Branch 2: Vector similarity (semantic fallback)
        try:
            vec_results = vector_search(
                self.embedding_svc, self.chroma_col, query, top_k=15,
            )
        except Exception as e:
            if self.logger:
                self.logger.log_warning("chromadb", "vector_search_failed", "skip_vector", {"error": str(e)})
            vec_results = []

        # Branch 3: SQLite FTS5 full-text search
        try:
            kw_results = keyword_search(self.db_conn, query, top_k=10)
        except Exception as e:
            if self.logger:
                self.logger.log_warning("sqlite", "keyword_search_failed", "skip_keyword", {"error": str(e)})
            kw_results = []

        # Fuse BM25 + vector + FTS5
        # BM25 carries the strongest signal for Chinese keyword queries —
        # it appears first in RRF so its ranks dominate when there's consensus.
        # BM25 2x weight: it carries the strongest signal for Chinese keyword
        # queries (exact province/score matching). Without doubling, rank-2 BM25
        # (1/63) can lose to rank-1 vector (1/62) after RRF fusion.
        fused = rrf_fusion(bm25_results, bm25_results, vec_results, kw_results)

        # Safety net: when the fused top-5 has no score_data, inject province-
        # matched score_data docs directly.  BM25 bigram tokenization can miss
        # numeric matches ("598" vs "598分"), so this guarantees the LLM always
        # sees relevant 2025 data.
        _top5_cts = [
            (r.get('metadata', {}) or {}).get('content_type', '')
            for r in fused[:5]
        ]
        if 'score_data' not in _top5_cts:
            injected = _find_score_data_for_context(self.chroma_col, query, context, max_results=5)
            if injected:
                # Prepend injected docs, dedup by content prefix
                seen = {_dedup_key(r) for r in fused}
                for inj in injected:
                    if _dedup_key(inj) not in seen:
                        fused.insert(0, inj)
                        seen.add(_dedup_key(inj))
                # Trim to 25 max before re-ranker
                fused = fused[:25]

        # Branch 4: Structured SQL queries (volunteer scene only)
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

        # Optional re-ranking
        if self.reranker and fused:
            try:
                fused = self.reranker.rerank(query, fused)
            except Exception as e:
                if self.logger:
                    self.logger.log_warning("reranker", "rerank_failed", "use_original", {"error": str(e)})

        return fused[:10]


# -- Safety-net injection helpers -----------------------------------------

_SCORE_DATA_SCAN_LIMIT = 60000


def _dedup_key(item: dict) -> str:
    """Generate a deduplication key from a search result item."""
    content = item.get('content', '') or ''
    return content[:80].strip()


def _find_score_data_for_context(
    chroma_col, query: str, context: dict, max_results: int = 5,
) -> list[dict]:
    """Find score_data docs relevant to the user's province.

    Used as a safety net when BM25+vector fusion fails to surface any
    score_data in the top results. Scans ChromaDB in-memory (~5ms for
    60k docs, no I/O).
    """
    province = context.get('province', '')
    if not province:
        for p in ['北京', '天津', '上海', '广东', '江苏', '浙江', '山东',
                   '河南', '河北', '湖北', '湖南', '福建', '安徽', '江西',
                   '辽宁', '四川', '陕西', '山西', '云南', '贵州', '广西',
                   '甘肃', '吉林', '黑龙江', '内蒙古', '新疆', '海南', '宁夏',
                   '青海', '西藏', '重庆']:
            if p in query:
                province = p
                break
    if not province:
        return []

    results = []
    limit = min(len(chroma_col._documents), _SCORE_DATA_SCAN_LIMIT)
    for i in range(limit):
        meta = chroma_col._metadatas[i] if i < len(chroma_col._metadatas) else {}
        if not isinstance(meta, dict):
            continue
        if meta.get('content_type') != 'score_data':
            continue
        doc = chroma_col._documents[i] if i < len(chroma_col._documents) else ''
        if province not in doc:
            continue
        priority = 0 if ('一分一段' in doc[:300] or '分数位次对照' in doc[:300]) else 1
        results.append({
            'id': chroma_col._ids[i] if i < len(chroma_col._ids) else str(i),
            'content': doc,
            'metadata': meta,
            '_priority': priority,
        })
        if len(results) >= max_results * 2:
            break

    results.sort(key=lambda r: r.get('_priority', 1))
    for r in results:
        r.pop('_priority', None)
    return results[:max_results]
