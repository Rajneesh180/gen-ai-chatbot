"""Batch embedding pipeline using Google text-embedding-004.

Reads chunks from data/chunks.jsonl, embeds them in batches, saves:
- data/embeddings.npy  (N x 768 float32 matrix)
- data/embed_manifest.json  (chunk_id -> row index mapping)

Supports resumption: if embeddings_partial.npy exists, continues from where
it left off.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List

import numpy as np

from backend.config import (
    CHUNKS_PATH,
    DATA_DIR,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    EMBEDDING_REQUESTS_PER_MINUTE,
    EMBEDDINGS_PATH,
    get_api_key,
)
from backend.ingestion.schema import Chunk

PARTIAL_PATH = DATA_DIR / "embeddings_partial.npy"
MANIFEST_PATH = DATA_DIR / "embed_manifest.json"

# Minimum delay between batch calls to stay under rate limit
_MIN_DELAY = 60.0 / EMBEDDING_REQUESTS_PER_MINUTE


def _load_chunks() -> List[Chunk]:
    """Read chunks.jsonl into Chunk objects."""
    chunks: List[Chunk] = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(Chunk.from_dict(json.loads(line)))
    return chunks


def _embed_batch(texts: List[str], client) -> np.ndarray:
    """Embed a batch of texts using the Google Generative AI SDK."""
    result = client.embed_content(
        model=EMBEDDING_MODEL,
        content=texts,
        task_type="retrieval_document",
    )
    return np.array(result["embedding"], dtype=np.float32)


def run_embed() -> None:
    """Run the full embedding pipeline with batching and checkpointing."""
    import google.generativeai as genai

    api_key = get_api_key()
    genai.configure(api_key=api_key)

    chunks = _load_chunks()
    if not chunks:
        print("[EMBED] No chunks found — run the chunk stage first.")
        return

    total = len(chunks)
    print(f"[EMBED] {total} chunks to embed (model: {EMBEDDING_MODEL})")

    # Check for partial progress
    start_idx = 0
    if PARTIAL_PATH.exists():
        partial = np.load(str(PARTIAL_PATH))
        start_idx = partial.shape[0]
        print(f"[EMBED] Resuming from chunk {start_idx} (partial checkpoint found)")
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
            embeddings = _embed_batch(batch, genai)
            all_embeddings.append(embeddings)
        except Exception as e:
            # Save checkpoint before failing
            if all_embeddings:
                checkpoint = np.concatenate(all_embeddings, axis=0)
                np.save(str(PARTIAL_PATH), checkpoint)
                print(f"[EMBED] Saved checkpoint at {checkpoint.shape[0]} chunks")
            raise RuntimeError(f"Embedding failed at batch {batch_num}: {e}") from e

        elapsed = time.time() - t0
        done = min(i + EMBEDDING_BATCH_SIZE, total)
        print(f"[EMBED] batch {batch_num}/{total_batches}  ({done}/{total} chunks)  {elapsed:.1f}s")

        # Rate limiting
        if elapsed < _MIN_DELAY and i + EMBEDDING_BATCH_SIZE < total:
            time.sleep(_MIN_DELAY - elapsed)

    # Concatenate and save
    final = np.concatenate(all_embeddings, axis=0)
    assert final.shape == (total, EMBEDDING_DIMS), (
        f"Shape mismatch: {final.shape} vs expected ({total}, {EMBEDDING_DIMS})"
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(EMBEDDINGS_PATH), final)

    # Save manifest: chunk_id -> row index
    manifest = {c.chunk_id: i for i, c in enumerate(chunks)}
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # Clean up partial checkpoint
    if PARTIAL_PATH.exists():
        PARTIAL_PATH.unlink()

    print(f"[EMBED] Done — {final.shape[0]} embeddings saved to {EMBEDDINGS_PATH}")
