"""Keyword (full-text) search module backed by SQLite FTS5 + jieba.

Provides :func:`keyword_search` which tokenizes a Chinese query with
jieba, matches against the ``corpus_fts`` virtual table, and returns
results ordered by FTS5 relevance rank.
"""

from __future__ import annotations

import sqlite3


def keyword_search(
    db_conn: sqlite3.Connection,
    query: str,
    top_k: int = 10,
) -> list[dict]:
    """Full-text keyword search over the corpus.

    Segments *query* with :func:`jieba.cut_for_search` so the tokens
    align with the pre-tokenized content stored in ``corpus_fts``.

    Parameters
    ----------
    db_conn : sqlite3.Connection
        Open SQLite connection (schema must already be initialized).
    query : str
        Raw Chinese (or mixed) search query.
    top_k : int
        Maximum number of results (default 10).

    Returns
    -------
    list[dict]
        Matching rows as dicts with keys: ``content``, ``source``,
        ``content_type``, ``date``, ``topic``, ``source_url``, ``rank``.
        Empty list when nothing matches or the query is un-parseable.
    """
    import jieba

    # cut_for_search produces finer-grained tokens that match the
    # pre-tokenized content stored by fts5_search / indexing pipeline.
    tokenized = " ".join(jieba.cut_for_search(query))
    try:
        cursor = db_conn.execute(
            "SELECT content, source, content_type, date, topic, source_url, "
            "rank FROM corpus_fts WHERE corpus_fts MATCH ? ORDER BY rank "
            "LIMIT ?",
            (tokenized, top_k),
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []
