"""Build FAISS vector index and BM25 keyword index from embedded chunks.

Reads:
- data/embeddings.npy  (N x 768 float32)
- data/chunks.jsonl    (chunk metadata)

Produces:
- data/faiss.index     (FAISS IndexFlatIP with normalized vectors)
- data/bm25.pkl        (rank_bm25.BM25Okapi fitted on chunk texts)
- data/metadata.pkl    (list of chunk metadata dicts for result mapping)
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from backend.config import (
    BM25_PATH,
    CHUNKS_PATH,
    DATA_DIR,
    EMBEDDINGS_PATH,
    FAISS_PATH,
    METADATA_PATH,
)
from backend.ingestion.schema import Chunk


def _load_chunks() -> List[Chunk]:
    chunks: List[Chunk] = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(Chunk.from_dict(json.loads(line)))
    return chunks


def _tokenize_for_bm25(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer for BM25."""
    return text.lower().split()


def build_faiss_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """Build a FAISS inner-product index from L2-normalized embeddings."""
    # Normalize for cosine similarity via inner product
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normalized = embeddings / norms

    dim = normalized.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(normalized)
    return index


def build_bm25_index(chunks: List[Chunk]) -> BM25Okapi:
    """Build a BM25 keyword index from chunk texts."""
    tokenized = [_tokenize_for_bm25(c.text) for c in chunks]
    return BM25Okapi(tokenized)


def build_metadata(chunks: List[Chunk]) -> List[Dict[str, Any]]:
    """Extract metadata dicts for result mapping (one per chunk, same order)."""
    return [
        {
            "chunk_id": c.chunk_id,
            "source_url": c.source_url,
            "page_title": c.page_title,
            "heading_path": c.heading_path,
            "source_type": c.source_type,
            "section": c.section,
            "token_count": c.token_count,
            "text": c.text,
        }
        for c in chunks
    ]


def run_index() -> None:
    """Run the full indexing pipeline."""
    chunks = _load_chunks()
    embeddings = np.load(str(EMBEDDINGS_PATH))

    assert len(chunks) == embeddings.shape[0], (
        f"Chunk count ({len(chunks)}) != embedding count ({embeddings.shape[0]})"
    )

    print(f"[INDEX] Building FAISS index from {embeddings.shape[0]} vectors...")
    faiss_index = build_faiss_index(embeddings)
    faiss.write_index(faiss_index, str(FAISS_PATH))
    print(f"[INDEX] FAISS index saved to {FAISS_PATH}")

    print(f"[INDEX] Building BM25 index from {len(chunks)} chunks...")
    bm25 = build_bm25_index(chunks)
    with open(BM25_PATH, "wb") as f:
        pickle.dump(bm25, f)
    print(f"[INDEX] BM25 index saved to {BM25_PATH}")

    print("[INDEX] Saving metadata...")
    metadata = build_metadata(chunks)
    with open(METADATA_PATH, "wb") as f:
        pickle.dump(metadata, f)
    print(f"[INDEX] Metadata saved to {METADATA_PATH} ({len(metadata)} entries)")

    print("[INDEX] Done — all indexes built.")
