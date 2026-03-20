"""Central configuration for the GitLab Knowledge Chatbot."""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPOS_DIR = DATA_DIR / "repos"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
FAISS_PATH = DATA_DIR / "faiss.index"
BM25_PATH = DATA_DIR / "bm25.pkl"
METADATA_PATH = DATA_DIR / "metadata.pkl"

# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMS = 768
EMBEDDING_BATCH_SIZE = 100
EMBEDDING_REQUESTS_PER_MINUTE = 90  # stay under 100 free-tier limit

LLM_MODEL = "gemini-2.0-flash"
LLM_TEMPERATURE = 0.3
LLM_MAX_OUTPUT_TOKENS = 2048

# ---------------------------------------------------------------------------
# Chunking tunables (mirrored from chunker.py for reference)
# ---------------------------------------------------------------------------
CHUNK_TARGET_MIN = 350
CHUNK_TARGET_MAX = 500
CHUNK_HARD_CAP = 700

# ---------------------------------------------------------------------------
# Retrieval tunables
# ---------------------------------------------------------------------------
RETRIEVAL_K = 5               # top-k chunks returned to the LLM
FAISS_SEARCH_K = 20           # FAISS overretrieve before fusion
BM25_SEARCH_K = 20            # BM25 overretrieve before fusion
RRF_K = 60                    # reciprocal rank fusion constant

# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------
def get_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("GOOGLE_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("\"'")
                    break
    if not key:
        raise SystemExit(
            "GOOGLE_API_KEY not set. Add it to .env or export it."
        )
    return key
