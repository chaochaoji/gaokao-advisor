"""Tests for SQLite schema initialization and FTS5 full-text search."""

import pytest
from src.knowledge.sqlite_store import get_db, init_db, fts5_search


@pytest.fixture
def db():
    """Create an in-memory SQLite database with schema and one test row."""
    import sqlite3
    import jieba

    conn = sqlite3.connect(":memory:")
    init_db(conn)
    # Pre-tokenize Chinese content with jieba so FTS5 can index it.
    # FTS5's unicode61 tokenizer skips CJK characters as separators,
    # so we segment beforehand and store space-separated words.
    raw = "计算机专业一定要看城市"
    tokenized = " ".join(jieba.cut_for_search(raw))
    conn.execute(
        "INSERT INTO corpus_fts (content, source, content_type, date) "
        "VALUES (?, ?, ?, ?)",
        (tokenized, "B站直播", "live_transcript", "2024-03-15"),
    )
    conn.commit()
    yield conn
    conn.close()


class TestFTS5Search:
    """FTS5 full-text search tests."""

    def test_chinese_keyword_search(self, db):
        """Searching for a Chinese keyword should return matching rows."""
        results = fts5_search(db, "计算机", limit=5)
        assert len(results) > 0
        assert "计算机" in results[0]["content"]

    def test_no_results_returns_empty(self, db):
        """Searching for a non-existent term should return an empty list."""
        results = fts5_search(db, "zzz不存在的词zzz", limit=5)
        assert results == []


class TestSchemaInit:
    """Schema initialization tests."""

    def test_tables_created(self, db):
        """All expected tables should exist after init_db()."""
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "universities" in tables
        assert "admission_scores" in tables
        assert "majors" in tables
        assert "employment_trends" in tables
        assert "city_industries" in tables
        assert "corpus_fts" in tables
        assert "indexing_log" in tables
