"""Hybrid retrieval: FAISS semantic search + BM25 keyword search + RRF fusion.

Loads pre-built indexes at import time (lazy singleton) and provides a
single `retrieve(query, k)` function that returns ranked chunk metadata.
"""

from __future__ import annotations

import pickle
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from backend.config import (
    BM25_PATH,
    BM25_SEARCH_K,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    FAISS_PATH,
    FAISS_SEARCH_K,
    METADATA_PATH,
    RETRIEVAL_K,
    RRF_K,
    get_api_key,
)

# ---------------------------------------------------------------------------
# Lazy-loaded singletons
# ---------------------------------------------------------------------------
_faiss_index: Optional[faiss.IndexFlatIP] = None
_bm25_index: Optional[BM25Okapi] = None
_metadata: Optional[List[Dict[str, Any]]] = None
_genai_client = None


def _ensure_loaded() -> None:
    """Load indexes from disk on first call."""
    global _faiss_index, _bm25_index, _metadata, _genai_client

    if _faiss_index is not None:
        return

    import google.generativeai as genai

    genai.configure(api_key=get_api_key())
    _genai_client = genai

    _faiss_index = faiss.read_index(str(FAISS_PATH))
    with open(BM25_PATH, "rb") as f:
        _bm25_index = pickle.load(f)
    with open(METADATA_PATH, "rb") as f:
        _metadata = pickle.load(f)

    print(f"[RETRIEVAL] Loaded {_faiss_index.ntotal} vectors, "
          f"{len(_metadata)} metadata entries")


# ---------------------------------------------------------------------------
# Query embedding
# ---------------------------------------------------------------------------

def _embed_query(query: str) -> np.ndarray:
    """Embed a single query string for retrieval."""
    result = _genai_client.embed_content(
        model=EMBEDDING_MODEL,
        content=query,
        task_type="retrieval_query",
    )
    vec = np.array(result["embedding"], dtype=np.float32).reshape(1, -1)
    # Normalize for cosine similarity
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


# ---------------------------------------------------------------------------
# Individual search methods
# ---------------------------------------------------------------------------

def _faiss_search(query_vec: np.ndarray, k: int) -> List[Tuple[int, float]]:
    """Return (index, score) pairs from FAISS semantic search."""
    scores, indices = _faiss_index.search(query_vec, k)
    results = []
    for idx, score in zip(indices[0], scores[0]):
        if idx >= 0:  # FAISS returns -1 for missing
            results.append((int(idx), float(score)))
    return results


def _bm25_search(query: str, k: int) -> List[Tuple[int, float]]:
    """Return (index, score) pairs from BM25 keyword search."""
    tokens = query.lower().split()
    scores = _bm25_index.get_scores(tokens)
    top_indices = np.argsort(scores)[::-1][:k]
    return [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def _rrf_fuse(
    faiss_results: List[Tuple[int, float]],
    bm25_results: List[Tuple[int, float]],
    k: int = RRF_K,
) -> List[Tuple[int, float]]:
    """Fuse two ranked lists using Reciprocal Rank Fusion.

    RRF score for document d = sum over rankers r of: 1 / (k + rank_r(d))
    """
    scores: Dict[int, float] = {}

    for rank, (idx, _) in enumerate(faiss_results):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)

    for rank, (idx, _) in enumerate(bm25_results):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    k: int = RETRIEVAL_K,
    faiss_k: int = FAISS_SEARCH_K,
    bm25_k: int = BM25_SEARCH_K,
) -> List[Dict[str, Any]]:
    """Retrieve the top-k most relevant chunks for a query.

    Uses hybrid search: FAISS (semantic) + BM25 (keyword) fused with RRF.
    Returns a list of metadata dicts, each with an added 'rrf_score' key.
    """
    _ensure_loaded()

    query_vec = _embed_query(query)
    faiss_results = _faiss_search(query_vec, faiss_k)
    bm25_results = _bm25_search(query, bm25_k)
    fused = _rrf_fuse(faiss_results, bm25_results)

    results: List[Dict[str, Any]] = []
    for idx, rrf_score in fused[:k]:
        entry = dict(_metadata[idx])
        entry["rrf_score"] = rrf_score
        results.append(entry)

    return results
