"""Hybrid retrieval: FAISS semantic search + BM25 keyword search + RRF fusion."""
from __future__ import annotations
import pickle
from typing import Any, Dict, List, Optional, Tuple
import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from backend.config import (
    BM25_PATH, BM25_SEARCH_K, EMBEDDING_DIMS, EMBEDDING_MODEL,
    FAISS_PATH, FAISS_SEARCH_K, METADATA_PATH, RETRIEVAL_K, RRF_K,
)

_faiss_index: Optional[faiss.IndexFlatIP] = None
_bm25_index: Optional[BM25Okapi] = None
_metadata: Optional[List[Dict[str, Any]]] = None
_local_embed_model = None

def _ensure_loaded() -> None:
    global _faiss_index, _bm25_index, _metadata, _local_embed_model
    if _faiss_index is not None:
        return

    from sentence_transformers import SentenceTransformer
    _local_embed_model = SentenceTransformer(EMBEDDING_MODEL)

    _faiss_index = faiss.read_index(str(FAISS_PATH))
    with open(BM25_PATH, "rb") as f:
        _bm25_index = pickle.load(f)
    with open(METADATA_PATH, "rb") as f:
        _metadata = pickle.load(f)
    print(f"[RETRIEVAL] Loaded {_faiss_index.ntotal} vectors, {len(_metadata)} metadata entries, model {EMBEDDING_MODEL}")

def _embed_query(query: str) -> np.ndarray:
    embeddings = _local_embed_model.encode([query], show_progress_bar=False)
    vec = np.array(embeddings[0], dtype=np.float32).reshape(1, -1)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec

def _faiss_search(query_vec: np.ndarray, k: int) -> List[Tuple[int, float]]:
    scores, indices = _faiss_index.search(query_vec, k)
    results = []
    for idx, score in zip(indices[0], scores[0]):
        if idx >= 0:
            results.append((int(idx), float(score)))
    return results

def _bm25_search(query: str, k: int) -> List[Tuple[int, float]]:
    tokens = query.lower().split()
    scores = _bm25_index.get_scores(tokens)
    top_indices = np.argsort(scores)[::-1][:k]
    return [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]

def _rrf_fuse(faiss_results: List[Tuple[int, float]], bm25_results: List[Tuple[int, float]], k: int = RRF_K) -> List[Tuple[int, float]]:
    scores: Dict[int, float] = {}
    for rank, (idx, _) in enumerate(faiss_results):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    for rank, (idx, _) in enumerate(bm25_results):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked

def retrieve(query: str, k: int = RETRIEVAL_K, faiss_k: int = FAISS_SEARCH_K, bm25_k: int = BM25_SEARCH_K) -> List[Dict[str, Any]]:
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
