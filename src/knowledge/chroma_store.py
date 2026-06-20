"""ChromaDB-compatible vector store backed by numpy.

Provides the same interface as chromadb (Collection.add, .query, .get,
.delete) but implemented in pure Python with numpy for cosine-similarity
search.  Works when chromadb native extensions are unavailable.

Public API:
    get_chroma_collection(config) -> NumpyCollection
    add_chunks(collection, chunks: list[dict])
    query_chunks(collection, query: str, top_k: int = 10) -> list[dict]
    delete_by_source(collection, source_prefix: str)
"""

from __future__ import annotations

import hashlib
from typing import Optional

import numpy as np


# ── Embedding helper ───────────────────────────────────────────────────


def _embed_text(text: str, dim: int = 384) -> np.ndarray:
    """Produce a deterministic dense embedding via character-bigram hashing.

    Algorithm:
    1.  Slide a window of sizes 1, 2 (char / bigram) over the text.
    2.  Hash each token to an index in [0, dim).
    3.  Accumulate TF weights in a vector.
    4.  L2-normalise so cosine similarity is just a dot product.
    """
    vec = np.zeros(dim, dtype=np.float64)
    if not text:
        return vec

    # character unigrams
    for ch in text:
        idx = ord(ch) % dim
        vec[idx] += 1.0

    # character bigrams (capture word-boundary signal for CJK)
    for i in range(len(text) - 1):
        bigram = text[i : i + 2]
        idx = int(hashlib.md5(bigram.encode()).hexdigest(), 16) % dim
        vec[idx] += 0.5  # lower weight than unigrams

    # L2-normalise
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


# ── Collection wrapper ──────────────────────────────────────────────────


class NumpyCollection:
    """A chromadb.Collection-compatible vector store backed by numpy.

    Parameters
    ----------
    name : str
        Logical name for the collection.
    embedding_dim : int
        Dimensionality of the embedding vectors (default 384).
    """

    def __init__(self, name: str, embedding_dim: int = 384) -> None:
        self.name = name
        self._dim = embedding_dim
        self._ids: list[str] = []
        self._documents: list[str] = []
        self._metadatas: list[dict] = []
        self._embeddings: list[np.ndarray] = []

    # -- chromadb-compatible API -----------------------------------------

    def add(
        self,
        ids: list[str],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None,
        embeddings: Optional[list[list[float]]] = None,
    ) -> None:
        """Add records to the collection (matches chromadb.Collection.add)."""
        if not ids:
            return
        n = len(ids)
        documents = documents or [""] * n
        metadatas = metadatas or [{}] * n

        for i in range(n):
            self._ids.append(ids[i])
            self._documents.append(documents[i])
            self._metadatas.append(metadatas[i])
            if embeddings and i < len(embeddings) and embeddings[i]:
                self._embeddings.append(
                    np.array(embeddings[i], dtype=np.float64)
                )
            else:
                self._embeddings.append(_embed_text(documents[i], self._dim))

    def query(
        self,
        query_texts: list[str],
        n_results: int = 10,
        include: Optional[list[str]] = None,
    ) -> dict:
        """Query the collection (matches chromadb.Collection.query).

        Returns a dict with keys ``ids``, ``documents``, ``metadatas``,
        ``distances`` -- each a list-of-lists (one inner list per query
        text).
        """
        if include is None:
            include = ["documents", "metadatas", "distances"]

        if not self._ids:
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
            }

        # Build embedding matrix (N x dim)
        emb_matrix = np.stack(self._embeddings, axis=0)  # (N, dim)

        results_ids: list[list[str]] = []
        results_docs: list[list[str]] = []
        results_meta: list[list[dict]] = []
        results_dist: list[list[float]] = []

        for query in query_texts:
            q_vec = _embed_text(query, self._dim)
            # cosine similarity = dot product (vectors are L2-normalised)
            scores = emb_matrix @ q_vec  # (N,)
            # get top-k indices
            k = min(n_results, len(self._ids))
            if k == 0:
                top_idx: list = []
            else:
                top_idx = np.argsort(scores)[::-1][:k].tolist()

            ids_out = [self._ids[j] for j in top_idx]
            docs_out = [self._documents[j] for j in top_idx]
            meta_out = [self._metadatas[j] for j in top_idx]
            dist_out = [float(1.0 - scores[j]) for j in top_idx]

            results_ids.append(ids_out)
            results_docs.append(docs_out)
            results_meta.append(meta_out)
            results_dist.append(dist_out)

        return {
            "ids": results_ids,
            "documents": results_docs,
            "metadatas": results_meta,
            "distances": results_dist,
        }

    def get(
        self,
        ids: Optional[list[str]] = None,
        where: Optional[dict] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        include: Optional[list[str]] = None,
    ) -> dict:
        """Retrieve records (matches chromadb.Collection.get)."""
        if include is None:
            include = ["documents", "metadatas"]

        # Filter by ids if provided
        if ids is not None:
            indices = [i for i, rid in enumerate(self._ids) if rid in ids]
        else:
            indices = list(range(len(self._ids)))

        # Apply offset / limit
        if offset:
            indices = indices[offset:]
        if limit is not None:
            indices = indices[:limit]

        result: dict = {"ids": [self._ids[i] for i in indices]}
        if "documents" in include:
            result["documents"] = [self._documents[i] for i in indices]
        if "metadatas" in include:
            result["metadatas"] = [self._metadatas[i] for i in indices]
        if "embeddings" in include:
            result["embeddings"] = [
                self._embeddings[i].tolist() for i in indices
            ]
        return result

    def delete(self, ids: list[str]) -> None:
        """Delete records by id (matches chromadb.Collection.delete)."""
        delete_set = set(ids)
        keep = [
            i
            for i, rid in enumerate(self._ids)
            if rid not in delete_set
        ]
        self._ids = [self._ids[i] for i in keep]
        self._documents = [self._documents[i] for i in keep]
        self._metadatas = [self._metadatas[i] for i in keep]
        self._embeddings = [self._embeddings[i] for i in keep]


# ── Public API ─────────────────────────────────────────────────────────


def get_chroma_collection(config) -> NumpyCollection:
    """Return a NumpyCollection instance for the given config.

    Signature mirrors what a real chromadb-backed function would look like
    so callers don't need to change when the backend is swapped.
    """
    return NumpyCollection(name="zhangxuefeng_corpus")


def add_chunks(collection: NumpyCollection, chunks: list[dict]) -> None:
    """Add pre-structured chunks into the collection.

    Each chunk dict must have ``id``, ``content``, and optionally
    ``metadata``.
    """
    if not chunks:
        return
    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["content"] for c in chunks],
        metadatas=[c.get("metadata", {}) for c in chunks],
    )


def query_chunks(
    collection: NumpyCollection, query: str, top_k: int = 10
) -> list[dict]:
    """Query the collection and return a list of result dicts.

    Each dict has keys: ``id``, ``content``, ``metadata``, ``distance``.
    """
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    output: list[dict] = []
    if results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            output.append(
                {
                    "id": doc_id,
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] or {},
                    "distance": results["distances"][0][i],
                }
            )
    return output


def delete_by_source(collection: NumpyCollection, source_prefix: str) -> None:
    """Delete all chunks whose id starts with *source_prefix*."""
    existing = collection.get()
    ids_to_delete = [
        i for i in existing["ids"] if i.startswith(source_prefix)
    ]
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
