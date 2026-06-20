"""SQLite storage layer with FTS5 full-text search.

Provides schema initialization and jieba-tokenized FTS5 search over
the corpus_fts virtual table.
"""

import sqlite3
import os
from config import Config


def get_db(config: Config) -> sqlite3.Connection:
    """Open (or create) the SQLite database with safe defaults.

    Parameters
    ----------
    config : Config
        Application configuration; ``config.sqlite_path`` is used as
        the database file path.  Pass ``":memory:"`` for testing.

    Returns
    -------
    sqlite3.Connection
        A connection with ``row_factory = sqlite3.Row``, WAL journal
        mode, and foreign-key enforcement enabled.
    """
    conn = sqlite3.connect(config.sqlite_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection):
    """Create all tables and indexes by executing ``schema.sql``.

    Idempotent -- every statement uses ``IF NOT EXISTS`` so the
    function is safe to call on an already-initialized database.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open SQLite connection.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()


def fts5_search(
    conn: sqlite3.Connection, query: str, limit: int = 10
) -> list[dict]:
    """Full-text search over the ``corpus_fts`` table using jieba tokenization.

    The input *query* is segmented with jieba and the resulting tokens
    are joined with spaces to form an FTS5 MATCH expression.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open SQLite connection (schema must already be initialized).
    query : str
        Raw Chinese (or mixed) search query.
    limit : int
        Maximum number of rows to return (default 10).

    Returns
    -------
    list[dict]
        Matching rows as dictionaries.  Returns an empty list when
        no rows match or when the FTS5 query is invalid.
    """
    import jieba

    # jieba segments Chinese into words.  Content is stored pre-tokenized
    # (space-separated jieba tokens) so FTS5's unicode61 tokenizer can
    # index each word.  We mirror that here by segmenting the query the
    # same way so tokens align.
    # cut_for_search is used to produce finer-grained tokens that improve
    # recall for compound words.
    tokenized = " ".join(jieba.cut_for_search(query))
    try:
        cursor = conn.execute(
            "SELECT content, source, content_type, date, topic, stance, "
            "source_url, rank FROM corpus_fts "
            "WHERE corpus_fts MATCH ? ORDER BY rank LIMIT ?",
            (tokenized, limit),
        )
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []
