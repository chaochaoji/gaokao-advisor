"""BM25 keyword search over the ChromaDB collection.

Pure-Python BM25 implementation with character-bigram tokenization.
Index is built in-memory at startup from the NumpyCollection's documents,
adding ~10 MB overhead for 57k docs and building in ~2 seconds.

Provides:
    :class:`BM25Index` — inverted-index builder and scorer
    :func:`bm25_search` — top-k retrieval entry point
"""

from __future__ import annotations

import math
from collections import defaultdict, Counter
from typing import Optional


# ── Tokenizer ────────────────────────────────────────────────────────────


def _fast_tokenize(text: str) -> list[str]:
    """Fast character-bigram tokenizer for index building.

    Extracts unigrams + bigrams from text, which works well for
    CJK matching (each character carries meaning) while being
    ~50x faster than jieba.  Jieba is used only at query time.
    """
    if not text:
        return []
    tokens = []
    # Unigrams (every character)
    for ch in text:
        if ch.strip():
            tokens.append(ch)
    # Bigrams (sliding window of 2)
    for i in range(len(text) - 1):
        bigram = text[i:i + 2]
        if bigram.strip():
            tokens.append(bigram)
    return tokens


def _tokenize_batch(texts: list[str]) -> list[list[str]]:
    """Tokenize a batch of documents for index building."""
    return [_fast_tokenize(t) for t in texts]


# ── BM25 Index ───────────────────────────────────────────────────────────


class BM25Index:
    """In-memory BM25 inverted index.

    Builds an index from a list of document strings, then scores documents
    against a query string with the standard BM25 formula.

    Parameters
    ----------
    documents : list[str]
        Corpus to index.
    tokenizer : callable, optional
        Function that takes a string and returns a list of tokens.
        Default: jieba-based tokenizer.
    k1 : float
        BM25 term-frequency saturation parameter (default 1.5).
    b : float
        BM25 length-normalisation parameter (default 0.75).
    """

    def __init__(
        self,
        documents: list[str],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b

        # Per-document state
        self._doc_tokens: list[list[str]] = []       # tokenised docs
        self._doc_len: list[int] = []                 # token count per doc
        self._avgdl: float = 0.0

        # Inverted index: token → {doc_index: term_frequency}
        self._inverted: dict[str, dict[int, int]] = defaultdict(dict)
        self._df: dict[str, int] = defaultdict(int)   # document frequency

        self._build(documents)

    # -- build -------------------------------------------------------------

    def _build(self, documents: list[str]) -> None:
        """Tokenise all documents and populate the inverted index."""
        n_docs = len(documents)
        if n_docs == 0:
            return

        # Tokenize in batch (uses multiprocessing for large corpora)
        all_tokens = _tokenize_batch(documents)

        total_len = 0
        for idx, tokens in enumerate(all_tokens):
            self._doc_tokens.append(tokens)
            dl = len(tokens)
            self._doc_len.append(dl)
            total_len += dl

            # Count term frequencies with Counter (C implementation, ~3x faster)
            tf = dict(Counter(tokens))

            for t, freq in tf.items():
                self._inverted[t][idx] = freq
                self._df[t] += 1

        self._avgdl = total_len / n_docs

    # -- rebuild after collection mutation ---------------------------------

    def rebuild(self, documents: list[str]) -> None:
        """Re-index from scratch (call after documents are added/deleted)."""
        self._doc_tokens.clear()
        self._doc_len.clear()
        self._inverted.clear()
        self._df.clear()
        self._build(documents)

    # -- search ------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Score all documents against *query*, return top *top_k* (idx, score).

        Empty corpus or query → empty list.
        """
        if not self._doc_tokens:
            return []

        query_tokens = _fast_tokenize(query)
        if not query_tokens:
            return []

        # Pre-compute IDF for each unique query token
        n_docs = len(self._doc_tokens)
        idf: dict[str, float] = {}
        for t in set(query_tokens):
            df = self._df.get(t, 0)
            # Smooth IDF: log((N - df + 0.5) / (df + 0.5) + 1)
            idf[t] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

        # Score candidates (only docs that match at least one query token)
        doc_scores: dict[int, float] = defaultdict(float)
        for t in set(query_tokens):
            qt_idf = idf.get(t, 0.0)
            if qt_idf == 0.0:
                continue
            for doc_idx, tf in self._inverted.get(t, {}).items():
                dl = self._doc_len[doc_idx]
                # BM25 term score
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * dl / self._avgdl)
                doc_scores[doc_idx] += qt_idf * numerator / denominator

        # Sort by descending score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_docs[:top_k]

    # -- stats -------------------------------------------------------------

    @property
    def doc_count(self) -> int:
        return len(self._doc_tokens)

    @property
    def vocab_size(self) -> int:
        return len(self._inverted)


# ── Public API ───────────────────────────────────────────────────────────


def bm25_search(
    bm25_index: Optional[BM25Index],
    documents: list[str],
    query: str,
    top_k: int = 10,
    metadatas: Optional[list[dict]] = None,
    ids: Optional[list[str]] = None,
) -> list[dict]:
    """Search the BM25 index and return result dicts compatible with
    the existing vector/keyword search format.

    Parameters
    ----------
    bm25_index : BM25Index or None
        Pre-built index.  If None, returns an empty list.
    documents : list[str]
        Original document texts (used to fill the ``content`` field).
    query : str
        Search query.
    top_k : int
        Number of results to return.
    metadatas : list[dict], optional
        Per-document metadata from the ChromaDB collection.
    ids : list[str], optional
        Per-document IDs from the ChromaDB collection.

    Returns
    -------
    list[dict]
        Each dict has ``id``, ``content``, ``metadata``, ``score``.
    """
    if bm25_index is None or not query:
        return []

    hits = bm25_index.search(query, top_k=top_k)

    results = []
    for idx, score in hits:
        item = {
            "id": ids[idx] if ids and idx < len(ids) else str(idx),
            "content": documents[idx] if idx < len(documents) else "",
            "score": score,
        }
        if metadatas and idx < len(metadatas):
            item["metadata"] = metadatas[idx] or {}
        else:
            item["metadata"] = {}
        results.append(item)
    return results
