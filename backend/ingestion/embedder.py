"""Batch embedding pipeline using locally-hosted SentenceTransformers."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List
import numpy as np

from backend.config import (
    CHUNKS_PATH, DATA_DIR, EMBEDDING_BATCH_SIZE, EMBEDDING_DIMS, EMBEDDING_MODEL, EMBEDDINGS_PATH,
)
from backend.ingestion.schema import Chunk

PARTIAL_PATH = DATA_DIR / "embeddings_partial.npy"
MANIFEST_PATH = DATA_DIR / "embed_manifest.json"

def _load_chunks() -> List[Chunk]:
    chunks: List[Chunk] = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(Chunk.from_dict(json.loads(line)))
    return chunks

def _embed_batch(texts: List[str], model) -> np.ndarray:
    embeddings = model.encode(texts, batch_size=len(texts), show_progress_bar=False)
    return np.array(embeddings, dtype=np.float32)

def run_embed() -> None:
    from sentence_transformers import SentenceTransformer
    chunks = _load_chunks()
    if not chunks:
        print("[EMBED] No chunks found.")
        return

    total = len(chunks)
    print(f"[EMBED] Loading local embedding model {EMBEDDING_MODEL} (might take a moment to download weights)...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    start_idx = 0
    if PARTIAL_PATH.exists():
        partial = np.load(str(PARTIAL_PATH))
        start_idx = partial.shape[0]
        all_embeddings = [partial]
    else:
        all_embeddings = []

    texts = [c.text for c in chunks]

    for i in range(start_idx, total, EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        batch_num = i // EMBEDDING_BATCH_SIZE + 1
        total_batches = (total + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE

        t0 = time.time()
        try:
            embeddings = _embed_batch(batch, model)
            all_embeddings.append(embeddings)
        except Exception as e:
            if all_embeddings:
                np.save(str(PARTIAL_PATH), np.concatenate(all_embeddings, axis=0))
            raise RuntimeError(f"Embedding failed at batch {batch_num}: {e}") from e

        elapsed = time.time() - t0
        done = min(i + EMBEDDING_BATCH_SIZE, total)
        print(f"[EMBED] batch {batch_num}/{total_batches}  ({done}/{total} chunks)  {elapsed:.1f}s")

    final = np.concatenate(all_embeddings, axis=0)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(EMBEDDINGS_PATH), final)

    manifest = {c.chunk_id: idx for idx, c in enumerate(chunks)}
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    if PARTIAL_PATH.exists():
        PARTIAL_PATH.unlink()
    print(f"[EMBED] Done — {final.shape[0]} embeddings saved.")
