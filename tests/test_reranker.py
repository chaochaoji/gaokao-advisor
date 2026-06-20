"""Tests for src.retrieval.reranker -- RerankerService."""

import pytest
from src.retrieval.reranker import RerankerService


# ------------------------------------------------------------------
# Mock Reranker for testing (simulates keyword-match priority)
# ------------------------------------------------------------------


class MockReranker(RerankerService):
    """A test-friendly reranker that promotes candidates containing the query."""

    def __init__(self):
        super().__init__(mode="mock")
        self.mode = "mock"

    def rerank(self, query, candidates):
        scored = []
        for c in candidates:
            # Use the first two chars of the query as a rough signal
            c["rerank_score"] = 1.0 if query[:2] in c.get("content", "") else 0.5
            scored.append(c)
        return sorted(scored, key=lambda x: x["rerank_score"], reverse=True)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_reranker_sorts_relevant_first():
    """Candidates containing the query keyword should rank first."""
    svc = MockReranker()
    candidates = [
        {"content": "computer science has great career prospects", "score": 0.8},
        {"content": "the weather is nice today", "score": 0.9},
        {"content": "computer city selection is important", "score": 0.7},
    ]
    results = svc.rerank("computer", candidates)
    assert "computer" in results[0]["content"]


def test_reranker_empty_list():
    """Empty candidate list returns empty list."""
    svc = MockReranker()
    assert svc.rerank("test", []) == []


def test_reranker_fallback_on_error():
    """When rerank raises, the service catches internally and returns original order."""

    class FailingReranker(RerankerService):
        def __init__(self):
            super().__init__(mode="api")

        def _api_rerank(self, query, candidates):
            raise ConnectionError("down")

    svc = FailingReranker()
    candidates = [{"content": "test", "score": 0.5}]
    # Should not raise, should return original list
    try:
        result = svc.rerank("test", candidates)
        assert len(result) == 1
    except ConnectionError:
        pytest.fail("Should have caught the error internally")


def test_reranker_mock_mode_preserves_score_order():
    """Default mock mode sorts by 'score' descending."""
    svc = RerankerService(mode="mock")
    candidates = [
        {"content": "low relevance", "score": 0.3},
        {"content": "high relevance", "score": 0.9},
        {"content": "medium relevance", "score": 0.6},
    ]
    results = svc.rerank("anything", candidates)
    assert results[0]["content"] == "high relevance"
    assert results[1]["content"] == "medium relevance"
    assert results[2]["content"] == "low relevance"


def test_reranker_adds_rerank_score():
    """Each result should carry a ``rerank_score`` after re-ranking."""
    svc = RerankerService(mode="mock")
    candidates = [
        {"content": "doc a", "score": 0.5},
        {"content": "doc b", "score": 0.8},
    ]
    results = svc.rerank("test", candidates)
    for r in results:
        assert "rerank_score" in r
        assert isinstance(r["rerank_score"], float)
