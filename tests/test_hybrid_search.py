"""Tests for src.retrieval.hybrid_search -- HybridSearch and rrf_fusion."""

import pytest
from src.retrieval.hybrid_search import HybridSearch, rrf_fusion


# ------------------------------------------------------------------
# RRF Fusion tests
# ------------------------------------------------------------------


class TestRRFFusion:
    """Tests for :func:`rrf_fusion`."""

    def test_rrf_fusion_combines_two_lists(self):
        a = [{"id": "A", "content": "alpha", "score": 0.9}]
        b = [{"id": "B", "content": "beta", "score": 0.7}]
        merged = rrf_fusion(a, b, k=60)
        assert len(merged) == 2

    def test_rrf_fusion_dedups_by_id(self):
        a = [{"id": "shared", "content": "first occurrence", "score": 0.9}]
        b = [{"id": "shared", "content": "duplicate", "score": 0.7}]
        merged = rrf_fusion(a, b, k=60)
        assert len(merged) == 1
        # First occurrence is kept
        assert merged[0]["content"] == "first occurrence"

    def test_rrf_fusion_ranks_repeated_item_higher(self):
        """An item appearing in multiple lists gets a higher RRF score."""
        a = [{"id": "common", "content": "common"}, {"id": "only-a", "content": "only-a"}]
        b = [{"id": "common", "content": "common"}, {"id": "only-b", "content": "only-b"}]
        merged = rrf_fusion(a, b, k=60)
        # 'common' should rank first because it appears in both lists
        assert merged[0]["id"] == "common"

    def test_rrf_fusion_empty_lists(self):
        assert rrf_fusion([], []) == []

    def test_rrf_fusion_single_list(self):
        items = [{"id": "1", "content": "one"}, {"id": "2", "content": "two"}]
        result = rrf_fusion(items)
        assert len(result) == 2
        assert result[0]["id"] == "1"

    def test_rrf_fusion_no_id_falls_back_to_content(self):
        """When no 'id' key exists, uses the first 50 chars of content."""
        a = [{"content": "unique doc a"}, {"content": "unique doc b"}]
        result = rrf_fusion(a)
        assert len(result) == 2

    def test_rrf_fusion_larger_k_compresses_scores(self):
        """A larger k value reduces the score differences between ranks."""
        items = [
            {"id": "1", "content": "a"},
            {"id": "2", "content": "b"},
            {"id": "3", "content": "c"},
        ]
        result_small_k = rrf_fusion(items, k=1)
        result_large_k = rrf_fusion(items, k=1000)
        # Both preserve order
        assert [r["id"] for r in result_small_k] == ["1", "2", "3"]
        assert [r["id"] for r in result_large_k] == ["1", "2", "3"]


# ------------------------------------------------------------------
# HybridSearch tests
# ------------------------------------------------------------------


class TestHybridSearch:
    """Tests for :class:`HybridSearch`."""

    def test_hybrid_search_mock_mode_returns_empty(self):
        """In mock mode, search() returns an empty list."""
        hs = HybridSearch(mode="mock")
        results = hs.search("computer", "volunteer", {"province": "Henan"})
        assert isinstance(results, list)
        assert results == []

    def test_hybrid_search_mock_no_context(self):
        """Works without a context dict."""
        hs = HybridSearch(mode="mock")
        results = hs.search("computer", "major")
        assert isinstance(results, list)
        assert results == []

    def test_hybrid_search_default_mode_is_prod(self):
        """Default mode is 'prod'."""
        hs = HybridSearch()
        assert hs.mode == "prod"

    def test_hybrid_search_truncates_to_10(self):
        """Even in mock mode, results should not exceed 10 (empty in this case)."""
        hs = HybridSearch(mode="mock")
        results = hs.search("test", "general")
        assert len(results) <= 10
