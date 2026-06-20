"""Vector search module -- semantic retrieval over the Chroma collection.

Provides :func:`vector_search` which embeds a query string and returns the
top-k most similar chunks from a :class:`NumpyCollection` (or any
chromadb-compatible collection that supports ``.query()`` via
``query_texts``).
"""

from __future__ import annotations

from typing import Optional


def vector_search(
    embedding_svc,
    chroma_col,
    query: str,
    top_k: int = 10,
) -> list[dict]:
    """Semantic search over the vector store.

    Parameters
    ----------
    embedding_svc :
        An :class:`EmbeddingService` instance.  Kept in the signature for
        callers that need to pre-embed; the collection itself handles
        embedding via ``query_texts`` when ``embedding_svc`` was wired in
        at construction time.
    chroma_col :
        A chromadb-compatible collection (e.g. :class:`NumpyCollection`).
        Must support ``.query(query_texts=..., n_results=..., include=...)``.
    query : str
        Natural-language query string.
    top_k : int
        Number of results to return (default 10).

    Returns
    -------
    list[dict]
        Each dict has keys ``id``, ``content``, ``metadata``, ``score``.
        *score* is the cosine similarity (1 -- angular distance).  The
        list is sorted by descending score.  Returns an empty list when
        the collection is empty.
    """
    results = chroma_col.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    if not results["ids"] or not results["ids"][0]:
        return []

    return [
        {
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i] or {},
            "score": 1.0 - results["distances"][0][i],
        }
        for i in range(len(results["ids"][0]))
    ]
